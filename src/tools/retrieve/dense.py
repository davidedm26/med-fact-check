from __future__ import annotations
import json
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
from langchain_core.tools import tool

from utils.logger import get_logger
from utils.config import config
from tools.retrieve.chunking import SourceMetadata, IndexedChunk, BiomedicalChunker

log = get_logger("MedFactCheck.DenseRetriever")

def _get_hf_token() -> Optional[str]:
    return os.getenv("HF_TOKEN")

class BiomedicalEmbedder:
    """Biomedical embedder used by the dense retriever."""

    def __init__(self, model_name: str = "medcpt", device: Optional[str] = None):
        self.name = model_name
        self.device = device or self._auto_device()
        self.dim = 768

        if self.name == "medcpt":
            self._query_model_name = "ncbi/MedCPT-Query-Encoder"
            self._article_model_name = "ncbi/MedCPT-Article-Encoder"
        else:
            self._single_model_name = self.name

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

        hf_token = _get_hf_token()
        token_kwargs = {"token": hf_token} if hf_token else {}

        if self.name == "medcpt":
            self._q_tok = AutoTokenizer.from_pretrained(self._query_model_name, **token_kwargs)
            self._q_model = AutoModel.from_pretrained(self._query_model_name, **token_kwargs).to(self.device).eval()
            self._a_tok = AutoTokenizer.from_pretrained(self._article_model_name, **token_kwargs)
            self._a_model = AutoModel.from_pretrained(self._article_model_name, **token_kwargs).to(self.device).eval()
            
            if self.device == "cpu":
                log.info("Applying INT8 dynamic quantization to MedCPT models...")
                self._q_model = torch.quantization.quantize_dynamic(self._q_model, {torch.nn.Linear}, dtype=torch.qint8)
                self._a_model = torch.quantization.quantize_dynamic(self._a_model, {torch.nn.Linear}, dtype=torch.qint8)
        else:
            self._tok = AutoTokenizer.from_pretrained(self._single_model_name, **token_kwargs)
            self._model = AutoModel.from_pretrained(self._single_model_name, **token_kwargs).to(self.device).eval()
            
            if self.device == "cpu":
                log.info(f"Applying INT8 dynamic quantization to {self._single_model_name}...")
                self._model = torch.quantization.quantize_dynamic(self._model, {torch.nn.Linear}, dtype=torch.qint8)

    def embed_query(self, query: str) -> np.ndarray:
        tok = self._q_tok if self.name == "medcpt" else self._tok
        model = self._q_model if self.name == "medcpt" else self._model

        with torch.no_grad():
            inputs = tok(
                query,
                return_tensors="pt",
                truncation=True,
                max_length=self._query_maxlen,
                padding=True,
            ).to(self.device)
            output = model(**inputs).last_hidden_state[:, 0, :]
            return self._normalize(output.cpu().numpy())

    def embed_passages(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dim), dtype="float32")

        tok = self._a_tok if self.name == "medcpt" else self._tok
        model = self._a_model if self.name == "medcpt" else self._model

        batches: List[np.ndarray] = []
        with torch.no_grad():
            for start in range(0, len(texts), batch_size):
                batch = texts[start : start + batch_size]
                inputs = tok(
                    batch,
                    return_tensors="pt",
                    truncation=True,
                    max_length=self._article_maxlen,
                    padding=True,
                ).to(self.device)
                output = model(**inputs).last_hidden_state[:, 0, :]
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
    def _load_chunks(chunks: str) -> List[Tuple[str, SourceMetadata]]:
        try:
            payload = json.loads(chunks)
        except Exception as exc:
            log.error(f"[dense_retrieve_tool] Failed to parse chunks JSON: {exc}")
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

            if not text:
                continue
            
            # We must NOT filter by doc_id here, because EuropePMC returns multiple different <p> paragraphs
            # for the same doc_id. Filtering by doc_id destroys 90% of the article context!
            records.append((text, SourceMetadata.from_dict(raw_meta)))

        return records

    def retrieve(self, query: str, chunks: str, top_k: int = 3) -> List[Dict[str, Any]]:
        records = self._load_chunks(chunks)
        if not records:
            return []

        chunks_list: List[IndexedChunk] = []
        for text, metadata in records:
            chunks_list.extend(self.chunker.chunk(text, metadata))

        if not chunks_list:
            return []

        embeddings = self.embedder.embed_passages([chunk.text for chunk in chunks_list])
        store = DenseVectorStore(dim=self.embedder.dim)
        store.add(embeddings, chunks_list)

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
        chunk_size = config.get("retrieval.chunking.chunk_size", 300)
        overlap = config.get("retrieval.chunking.overlap", 50)
        model_name = config.get("retrieval.dense.model_name", "medcpt")
        _DEFAULT_DENSE_RETRIEVER = DenseRetriever(model_name=model_name, chunk_size=chunk_size, overlap=overlap)
    return _DEFAULT_DENSE_RETRIEVER


@tool
def dense_retrieve_tool(query: str, chunks: Optional[str] = None, top_k: int = 3) -> List[Dict[str, Any]]:
    """Dense retrieval using a single biomedical embedding model and cosine similarity."""
    if not chunks:
        return []
    return _get_default_dense_retriever().retrieve(query=query, chunks=chunks, top_k=top_k)
