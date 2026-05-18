import logging
import re
from typing import List, Dict
from rank_bm25 import BM25Okapi

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

def tokenize_text(text: str) -> List[str]:
    return re.findall(r'\b\w+\b', text.lower())

def extract_relevant_paragraphs(query: str, paragraphs_with_metadata: List[Dict], top_k: int = 3) -> List[Dict]:
    """
    Receives a list of dictionaries (text + metadata).
    Returns the top_k dictionaries intact, preserving traceability.
    """
    if not paragraphs_with_metadata:
        logging.warning("[BM25] No paragraphs provided as input.")
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
    
    logging.info(f"[BM25] Extracted {len(top_results)} most relevant paragraphs for query '{query}'.")
    return top_results