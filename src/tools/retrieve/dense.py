import json
import logging
from typing import List, Dict, Optional
from langchain_core.tools import tool

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

@tool
def dense_retrieve_tool(query: str, documents: Optional[str] = None, top_k: int = 3) -> List[Dict]:
    """Placeholder tool for dense retrieval (M3).
    Currently returns an empty list.

    Args:
        query: The search query to match against the documents.
        documents: A JSON string containing a list of dictionaries, each with 'text' and 'metadata' keys.
        top_k: The number of top relevant paragraphs to return.

    Returns:
        A list of the most relevant document dictionaries.
    """
    logging.info(f"[Dense Retrieve Tool Placeholder] Query: {query}, top_k: {top_k}")
    return []
