from typing import List, Literal
from langchain_core.tools import tool
from tools.retrieve.core.ingestion import IngestionNode


VALID_TARGET_SOURCES = {"systematic_reviews", "knowledge_base", "literature"}


def _download_from_source(sub_id: str, search_queries: List[str], target_source: str) -> dict:
    if target_source not in VALID_TARGET_SOURCES:
        raise ValueError(
            f"Invalid target_source: {target_source}. Must be one of {sorted(VALID_TARGET_SOURCES)}"
        )
    ingestion_node = IngestionNode()
    chunks, stats = ingestion_node.prepare_data(sub_id, search_queries, target_source)
    return {"chunks": chunks, "stats": stats}

@tool
def download_documents(
    sub_id: str,
    search_queries: List[str],
    target_source: Literal["systematic_reviews", "knowledge_base", "literature"],
) -> dict:
    """Downloads medical documents from various sources based on generated queries.

    Args:
        sub_id: A unique identifier for the subclaim (e.g. 'sub_01').
        search_queries: A list of specific search queries to use.
        target_source: The selected database source (must be one of 'systematic_reviews', 'knowledge_base', 'literature').

    Returns:
        A dictionary containing "chunks" (list of dictionaries representing the downloaded document chunks) and "stats" (dictionary with download statistics).
    """
    return _download_from_source(sub_id, search_queries, target_source)
