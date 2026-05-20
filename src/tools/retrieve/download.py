from typing import List, Dict
from langchain_core.tools import tool
from tools.retrieve.core.ingestion import IngestionNode


def _download_from_source(sub_id: str, search_queries: List[str], target_source: str) -> List[dict]:
    ingestion_node = IngestionNode()
    return ingestion_node.prepare_data(sub_id, search_queries, target_source)

@tool
def download_documents(sub_id: str, search_queries: List[str], target_source: str) -> List[dict]:
    """Downloads medical documents from various sources based on generated queries.

    Args:
        sub_id: A unique identifier for the subclaim (e.g. 'sub_01').
        search_queries: A list of specific search queries to use.
        target_source: The selected database source (must be one of 'clinical_trials', 'knowledge_base', 'literature').

    Returns:
        A list of dictionaries representing the downloaded document chunks, including text and metadata.
    """
    return _download_from_source(sub_id, search_queries, target_source)


@tool
def download_from_literature(sub_id: str, search_queries: List[str]) -> List[dict]:
    """Downloads literature documents based on generated queries."""
    return _download_from_source(sub_id, search_queries, "literature")


@tool
def download_from_clinical_trials(sub_id: str, search_queries: List[str]) -> List[dict]:
    """Downloads clinical-trials documents based on generated queries."""
    return _download_from_source(sub_id, search_queries, "clinical_trials")


@tool
def download_from_kb(sub_id: str, search_queries: List[str]) -> List[dict]:
    """Downloads knowledge-base documents based on generated queries."""
    return _download_from_source(sub_id, search_queries, "knowledge_base")
