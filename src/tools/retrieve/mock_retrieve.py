from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, List

from langchain_core.tools import tool


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _build_document(source: str, title: str, summary: str, chunks: List[str]) -> Dict[str, object]:
    return {
        "source": source,
        "title": title,
        "summary": summary,
        "chunks": chunks,
    }


def _download_wikipedia_documents(query: str, limit: int = 4) -> List[Dict[str, object]]:
    return [
        _build_document(
            "wikipedia",
            f"Wikipedia overview for {query}",
            "General background and entity context.",
            [
                f"{query} is described in encyclopedic terms.",
                "This mock source provides high-level background information.",
            ],
        )
    ][:limit]


@tool
def download_wikipedia_documents(query: str, limit: int = 4) -> List[Dict[str, object]]:
    """Mock tool that downloads Wikipedia documents for a query."""
    return _download_wikipedia_documents(query, limit)


def _download_pubmed_documents(query: str, limit: int = 4) -> List[Dict[str, object]]:
    return [
        _build_document(
            "pubmed",
            f"PubMed evidence for {query}",
            "Clinical and biomedical literature mock document.",
            [
                f"Clinical studies related to {query}.",
                "This mock record simulates an abstract with biomedical terms.",
                "Additional evidence lines for downstream ranking.",
            ],
        ),
        _build_document(
            "pubmed",
            f"PubMed review on {query}",
            "A review-style mock document.",
            [
                f"Review evidence discussing {query}.",
                "This mock record gives a second biomedical candidate.",
            ],
        ),
    ][:limit]


@tool
def download_pubmed_documents(query: str, limit: int = 4) -> List[Dict[str, object]]:
    """Mock tool that downloads PubMed documents for a query."""
    return _download_pubmed_documents(query, limit)


def _download_news_documents(query: str, limit: int = 4) -> List[Dict[str, object]]:
    return [
        _build_document(
            "news",
            f"News report about {query}",
            "Recent reporting mock document.",
            [
                f"A news article mentions {query}.",
                "This mock source simulates current reporting.",
            ],
        )
    ][:limit]


@tool
def download_news_documents(query: str, limit: int = 4) -> List[Dict[str, object]]:
    """Mock tool that downloads news documents for a query."""
    return _download_news_documents(query, limit)


def _download_guidelines_documents(query: str, limit: int = 4) -> List[Dict[str, object]]:
    return [
        _build_document(
            "guidelines",
            f"Guideline excerpt for {query}",
            "Practice guideline mock document.",
            [
                f"Guideline language relevant to {query}.",
                "This mock source simulates a policy or practice recommendation.",
            ],
        )
    ][:limit]


@tool
def download_guidelines_documents(query: str, limit: int = 4) -> List[Dict[str, object]]:
    """Mock tool that downloads guideline documents for a query."""
    return _download_guidelines_documents(query, limit)


def download_documents_for_source(source: str, query: str, limit: int = 4) -> List[Dict[str, object]]:
    source_map = {
        "wikipedia": _download_wikipedia_documents,
        "pubmed": _download_pubmed_documents,
        "news": _download_news_documents,
        "guidelines": _download_guidelines_documents,
    }
    if source not in source_map:
        raise ValueError(f"Unsupported retrieval source: {source}")
    return source_map[source](query, limit=limit)


def _score_chunk(query_tokens: Counter, chunk_text: str) -> float:
    chunk_tokens = Counter(_tokenize(chunk_text))
    overlap = sum(min(query_tokens[token], chunk_tokens[token]) for token in query_tokens)
    coverage = overlap / max(len(query_tokens), 1)
    length_penalty = 1.0 / (1.0 + math.log(max(len(chunk_text.split()), 1)))
    return coverage + length_penalty


def sparse_retrieve_chunks(documents: List[Dict[str, object]], query: str, top_k: int = 3) -> List[Dict[str, object]]:
    query_tokens = Counter(_tokenize(query))
    scored_chunks: List[Dict[str, object]] = []

    for document in documents:
        chunks = document.get("chunks", []) if isinstance(document, dict) else []
        for chunk in chunks:
            score = _score_chunk(query_tokens, str(chunk))
            scored_chunks.append(
                {
                    "source": document.get("source"),
                    "title": document.get("title"),
                    "chunk": chunk,
                    "score": round(score, 4),
                    "retriever": "sparse",
                }
            )

    scored_chunks.sort(key=lambda item: item["score"], reverse=True)
    return scored_chunks[:top_k]


def dense_retrieve_chunks(documents: List[Dict[str, object]], query: str, top_k: int = 3) -> List[Dict[str, object]]:
    query_tokens = set(_tokenize(query))
    scored_chunks: List[Dict[str, object]] = []

    for document in documents:
        chunks = document.get("chunks", []) if isinstance(document, dict) else []
        for chunk in chunks:
            chunk_tokens = set(_tokenize(str(chunk)))
            shared = len(query_tokens & chunk_tokens)
            density = shared / max(len(chunk_tokens), 1)
            source_bonus = 0.15 if document.get("source") == "pubmed" else 0.05
            score = density + source_bonus
            scored_chunks.append(
                {
                    "source": document.get("source"),
                    "title": document.get("title"),
                    "chunk": chunk,
                    "score": round(score, 4),
                    "retriever": "dense",
                }
            )

    scored_chunks.sort(key=lambda item: item["score"], reverse=True)
    return scored_chunks[:top_k]