from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
from langchain_core.tools import tool

from utils.logger import get_logger
log = get_logger("MedFactCheck.DenseRetriever")


@dataclass
class SourceMetadata:
    id: str = ""
    title: str = ""
    type: str = "Scientific Literature"
    date: str = "N/A"
    url: str = ""
    extra_info: Dict[str, Any] = field(default_factory=dict)

    @property
    def target_source(self) -> str:
        return {
            "Scientific Literature": "literature",
            "Clinical Trial": "clinical_trials",
            "Protein Knowledge": "knowledge_base",
        }.get(self.type, "literature")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "date": self.date,
            "url": self.url,
            "extra_info": self.extra_info,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SourceMetadata":
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            type=data.get("type", "Scientific Literature"),
            date=data.get("date", "N/A"),
            url=data.get("url", ""),
            extra_info=data.get("extra_info") or {},
        )


@dataclass
class IndexedChunk:
    chunk_id: str
    text: str
    chunk_index: int
    section: str
    source: SourceMetadata

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "chunk_index": self.chunk_index,
            "section": self.section,
            "source": self.source.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IndexedChunk":
        return cls(
            chunk_id=data["chunk_id"],
            text=data["text"],
            chunk_index=data["chunk_index"],
            section=data["section"],
            source=SourceMetadata.from_dict(data["source"]),
        )


@dataclass
class RetrievedText:
    text_content: str
    source_metadata: SourceMetadata
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text_content": self.text_content,
            "source_metadata": self.source_metadata.to_dict(),
            "score": self.score,
        }


@dataclass
class BiomedicalChunker:
    chunk_size: int = 300
    overlap: int = 50

    _SECTION_RE_PARTS = (
        r"Abstract", r"Introduction", r"Background",
        r"Methods?", r"Materials?\s+and\s+Methods?",
        r"Results?", r"Discussion", r"Conclusions?",
        r"References?", r"Eligibility", r"Summary",
        r"Outcomes?", r"Interventions?",
    )

    def __post_init__(self) -> None:
        self._section_pat = re.compile(
            r"^(?:" + "|".join(self._SECTION_RE_PARTS) + r")[\s:]*$",
            re.IGNORECASE | re.MULTILINE,
        )

    def chunk(self, text: str, source: SourceMetadata) -> List[IndexedChunk]:
        chunks: List[IndexedChunk] = []
        idx = 0

        for section_label, section_text in self._split_sections(text):
            if section_label == "References":
                continue

            words = section_text.split()
            start = 0
            while start < len(words):
                end = min(start + self.chunk_size, len(words))
                chunk_text = " ".join(words[start:end]).strip()

                if len(chunk_text) >= 40:
                    chunks.append(
                        IndexedChunk(
                            chunk_id=self._make_id(source.id, idx),
                            text=chunk_text,
                            chunk_index=idx,
                            section=section_label,
                            source=source,
                        )
                    )
                    idx += 1

                if end == len(words):
                    break
                start = end - self.overlap

        return chunks

    def _split_sections(self, text: str) -> List[Tuple[str, str]]:
        sections: List[Tuple[str, str]] = []
        current_label = "Body"
        current_lines: List[str] = []

        for line in text.split("\n"):
            if self._section_pat.match(line.strip()):
                if current_lines:
                    sections.append((current_label, "\n".join(current_lines)))
                current_label = self._normalise_section(line.strip())
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            sections.append((current_label, "\n".join(current_lines)))

        return sections or [("Body", text)]

    @staticmethod
    def _normalise_section(raw: str) -> str:
        mapping = {
            "abstract": "Abstract",
            "introduction": "Introduction",
            "background": "Background",
            "results": "Results",
            "discussion": "Discussion",
            "references": "References",
            "conclusion": "Conclusion",
            "conclusions": "Conclusion",
            "eligibility": "Eligibility",
            "summary": "Summary",
        }
        for key, label in mapping.items():
            if key in raw.lower():
                return label
        if "method" in raw.lower():
            return "Methods"
        return "Body"

    @staticmethod
    def _make_id(doc_id: str, idx: int) -> str:
        return hashlib.md5(f"{doc_id}__{idx}".encode()).hexdigest()[:14]


class BiomedicalEmbedder:
    """Single-model biomedical embedder used by the dense retriever."""

    def __init__(self, model_name: str = "medcpt", device: Optional[str] = None):
        if model_name != "medcpt":
            raise ValueError("Dense retriever currently supports only 'medcpt'.")

        self.name = model_name
        self.device = device or self._auto_device()
        self.dim = 768

        self._query_model_name = "ncbi/MedCPT-Query-Encoder"
        self._article_model_name = "ncbi/MedCPT-Article-Encoder"
        self._query_maxlen = 64
        self._article_maxlen = 256

        log.info(f"Loading dense embedder '{self.name}' on {self.device}")
        self._load()

    @staticmethod
    def _auto_device() -> str:
        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _load(self) -> None:
        try:
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:
            raise ImportError("Dense retriever requires 'transformers'.") from exc

        self._q_tok = AutoTokenizer.from_pretrained(self._query_model_name)
        self._q_model = AutoModel.from_pretrained(self._query_model_name).to(self.device).eval()
        self._a_tok = AutoTokenizer.from_pretrained(self._article_model_name)
        self._a_model = AutoModel.from_pretrained(self._article_model_name).to(self.device).eval()

    def embed_query(self, query: str) -> np.ndarray:
        with torch.no_grad():
            inputs = self._q_tok(
                query,
                return_tensors="pt",
                truncation=True,
                max_length=self._query_maxlen,
                padding=True,
            ).to(self.device)
            output = self._q_model(**inputs).last_hidden_state[:, 0, :]
            return self._normalize(output.cpu().numpy())

    def embed_passages(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dim), dtype="float32")

        batches: List[np.ndarray] = []
        with torch.no_grad():
            for start in range(0, len(texts), batch_size):
                batch = texts[start : start + batch_size]
                inputs = self._a_tok(
                    batch,
                    return_tensors="pt",
                    truncation=True,
                    max_length=self._article_maxlen,
                    padding=True,
                ).to(self.device)
                output = self._a_model(**inputs).last_hidden_state[:, 0, :]
                batches.append(self._normalize(output.cpu().numpy()))

        return np.vstack(batches).astype("float32")

    @staticmethod
    def _normalize(vectors: np.ndarray) -> np.ndarray:
        return vectors / (np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-9)


class DenseVectorStore:
    def __init__(self, dim: int):
        self.dim = dim
        self._embeddings: Optional[np.ndarray] = None
        self._chunks: List[Dict[str, Any]] = []

    def add(self, embeddings: np.ndarray, chunks: List[IndexedChunk]) -> None:
        if embeddings.size == 0 or not chunks:
            return
        if self._embeddings is None:
            self._embeddings = embeddings.astype("float32")
        else:
            self._embeddings = np.vstack([self._embeddings, embeddings.astype("float32")])
        self._chunks.extend([chunk.to_dict() for chunk in chunks])

    def search(self, query_vec: np.ndarray, top_k: int) -> List[Tuple[float, IndexedChunk]]:
        if self._embeddings is None or not self._chunks:
            log.warning("Dense index is empty.")
            return []

        similarities = self._embeddings @ query_vec.astype("float32").T
        scores = similarities[:, 0]
        order = np.argsort(scores)[::-1][: min(top_k, len(scores))]

        results: List[Tuple[float, IndexedChunk]] = []
        for idx in order:
            results.append((float(scores[idx]), IndexedChunk.from_dict(self._chunks[idx])))
        return results


class DenseRetriever:
    def __init__(self, model_name: str = "medcpt", chunk_size: int = 300, overlap: int = 50):
        self.embedder = BiomedicalEmbedder(model_name=model_name)
        self.chunker = BiomedicalChunker(chunk_size=chunk_size, overlap=overlap)
        self.store = DenseVectorStore(dim=self.embedder.dim)

    @staticmethod
    def _load_documents(documents: str) -> List[Tuple[str, SourceMetadata]]:
        try:
            payload = json.loads(documents)
        except Exception as exc:
            log.error(f"[dense_retrieve_tool] Failed to parse documents JSON: {exc}")
            return []

        if not isinstance(payload, list):
            log.error(f"[dense_retrieve_tool] Expected a JSON list, got {type(payload).__name__}")
            return []

        records: List[Tuple[str, SourceMetadata]] = []
        seen_ids: set[str] = set()

        for item in payload:
            if not isinstance(item, dict):
                continue
            text = (item.get("text") or "").strip()
            raw_meta = item.get("metadata") or {}
            doc_id = raw_meta.get("id", "")

            if not text or doc_id in seen_ids:
                continue
            seen_ids.add(doc_id)
            records.append((text, SourceMetadata.from_dict(raw_meta)))

        return records

    def retrieve(self, query: str, documents: str, top_k: int = 3) -> List[Dict[str, Any]]:
        records = self._load_documents(documents)
        if not records:
            return []

        chunks: List[IndexedChunk] = []
        for text, metadata in records:
            chunks.extend(self.chunker.chunk(text, metadata))

        if not chunks:
            return []

        embeddings = self.embedder.embed_passages([chunk.text for chunk in chunks])
        store = DenseVectorStore(dim=self.embedder.dim)
        store.add(embeddings, chunks)

        query_vec = self.embedder.embed_query(query)
        ranked = store.search(query_vec, top_k=top_k)

        results: List[Dict[str, Any]] = []
        for score, chunk in ranked:
            results.append(
                {
                    "text": chunk.text,
                    "metadata": chunk.source.to_dict(),
                    "score": score,
                }
            )
        log.info(f"[Dense] Extracted {len(results)} relevant paragraphs for query '{query}'")
        return results


_DEFAULT_DENSE_RETRIEVER: Optional[DenseRetriever] = None


def _get_default_dense_retriever() -> DenseRetriever:
    global _DEFAULT_DENSE_RETRIEVER
    if _DEFAULT_DENSE_RETRIEVER is None:
        _DEFAULT_DENSE_RETRIEVER = DenseRetriever()
    return _DEFAULT_DENSE_RETRIEVER


@tool
def dense_retrieve_tool(query: str, documents: Optional[str] = None, top_k: int = 3) -> List[Dict[str, Any]]:
    """Dense retrieval using a single biomedical embedding model and cosine similarity."""
    if not documents:
        return []
    return _get_default_dense_retriever().retrieve(query=query, documents=documents, top_k=top_k)
