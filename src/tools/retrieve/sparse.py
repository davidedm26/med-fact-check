import json
import re
from typing import List, Dict, Optional
from langchain_core.tools import tool
from rank_bm25 import BM25Okapi

from utils.logger import get_logger
log = get_logger("MedFactCheck.SparseRetriever")

from tools.retrieve.chunking import BiomedicalChunker
from utils.config import config

def tokenize_text(text: str) -> List[str]:
    return re.findall(r'\b\w+\b', text.lower())

def extract_relevant_paragraphs(query: str, paragraphs_with_metadata: List[Dict], top_k: int = 3) -> List[Dict]:
    """
    Receives a list of dictionaries (text + metadata).
    Returns the top_k dictionaries intact, preserving traceability.
    """
    if not paragraphs_with_metadata:
        log.warning("[BM25] No paragraphs provided as input.")
        return []

    # Initialize the same chunker used by dense retriever
    chunk_size = config.get("retrieval.chunking.chunk_size", 300)
    chunk_overlap = config.get("retrieval.chunking.overlap", 50)
    chunker = BiomedicalChunker(chunk_size=chunk_size, overlap=chunk_overlap)

    # Chunk the raw paragraphs into semantic chunks
    chunked_corpus = []
    for p in paragraphs_with_metadata:
        text = p.get("text", "")
        meta = p.get("metadata", {})
        if not text:
            continue
        from tools.retrieve.chunking import SourceMetadata
        source_meta = SourceMetadata.from_dict(meta)
        chunks = chunker.chunk(text, source_meta)
        for c in chunks:
            chunked_corpus.append({
                "text": c.text,
                "metadata": c.source.to_dict()
            })

    if not chunked_corpus:
        log.warning("[BM25] No valid chunks extracted.")
        return []

    # 1. Extract and tokenize only the 'text' key from each chunk
    tokenized_corpus = [tokenize_text(p["text"]) for p in chunked_corpus]
    
    # 2. Initialize the BM25 engine
    bm25 = BM25Okapi(tokenized_corpus)
    
    # 3. Tokenize the query
    tokenized_query = tokenize_text(query)
    
    # 4. Get the best chunks
    top_results = bm25.get_top_n(tokenized_query, chunked_corpus, n=top_k)
    
    log.info(f"[BM25] Extracted {len(top_results)} most relevant paragraphs for query '{query}'.")
    return top_results

@tool
def sparse_retrieve_tool(query: str, chunks: Optional[str] = None, top_k: int = 3) -> List[Dict]:
    """Retrieves the most relevant paragraphs from a list of chunks using BM25 sparse retrieval.

    Args:
        query: The search query to match against the chunks.
        chunks: A JSON string containing a list of dictionaries, each with 'text' and 'metadata' keys representing the chunks to search.
        top_k: The number of top relevant paragraphs to return.

    Returns:
        A list of the most relevant document dictionaries.
    """
    if not chunks:
        return []

    try:
        chunks_list = json.loads(chunks)
    except Exception as e:
        log.error(f"[sparse_retrieve_tool] Failed to parse chunks JSON: {e}")
        return []

    return extract_relevant_paragraphs(query, chunks_list, top_k)
