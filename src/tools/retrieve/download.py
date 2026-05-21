from typing import List, Literal
from langchain_core.tools import tool
from tools.retrieve.core.ingestion import IngestionNode


VALID_TARGET_SOURCES = {"clinical_trials", "knowledge_base", "literature"}


def _download_from_source(sub_id: str, search_queries: List[str], target_source: str) -> List[dict]:
    if target_source not in VALID_TARGET_SOURCES:
        raise ValueError(
            f"Invalid target_source: {target_source}. Must be one of {sorted(VALID_TARGET_SOURCES)}"
        )
    ingestion_node = IngestionNode()
    return ingestion_node.prepare_data(sub_id, search_queries, target_source)

@tool
def download_documents(
    sub_id: str,
    search_queries: List[str],
    target_source: Literal["clinical_trials", "knowledge_base", "literature"],
) -> List[dict]:
    """Downloads medical documents from various sources based on generated queries.

    Args:
        sub_id: A unique identifier for the subclaim (e.g. 'sub_01').
        search_queries: A list of specific search queries to use.
        target_source: The selected database source (must be one of 'clinical_trials', 'knowledge_base', 'literature').

    Returns:
        A list of dictionaries representing the downloaded document chunks, including text and metadata.
    """
    return _download_from_source(sub_id, search_queries, target_source)
