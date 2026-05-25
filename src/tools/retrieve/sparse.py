import json
import re
from typing import List, Dict, Optional
from langchain_core.tools import tool
from rank_bm25 import BM25Okapi

from utils.logger import get_logger
log = get_logger("MedFactCheck.SparseRetriever")

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

    # 1. Extract and tokenize only the 'text' key from each dictionary
    tokenized_corpus = [tokenize_text(p["text"]) for p in paragraphs_with_metadata]
    
    # 2. Initialize the BM25 engine
    bm25 = BM25Okapi(tokenized_corpus)
    
    # 3. Tokenize the query
    tokenized_query = tokenize_text(query)
    
    # 4. Get the best paragraphs
    # Passing 'paragraphs_with_metadata' returns the full dictionary objects
    top_results = bm25.get_top_n(tokenized_query, paragraphs_with_metadata, n=top_k)
    
    log.info(f"[BM25] Extracted {len(top_results)} most relevant paragraphs for query '{query}'.")
    return top_results

@tool
def sparse_retrieve_tool(query: str, documents: Optional[str] = None, top_k: int = 3) -> List[Dict]:
    """Retrieves the most relevant paragraphs from a list of documents using BM25 sparse retrieval.

    Args:
        query: The search query to match against the documents.
        documents: A JSON string containing a list of dictionaries, each with 'text' and 'metadata' keys representing the documents to search.
        top_k: The number of top relevant paragraphs to return.

    Returns:
        A list of the most relevant document dictionaries.
    """
    if not documents:
        return []

    try:
        docs_list = json.loads(documents)
    except Exception as e:
        log.error(f"[sparse_retrieve_tool] Failed to parse documents JSON: {e}")
        return []

    return extract_relevant_paragraphs(query, docs_list, top_k)
