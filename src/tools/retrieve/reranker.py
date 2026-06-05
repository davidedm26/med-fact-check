import os
from typing import Any, Dict, List, Optional
import torch
import numpy as np

from utils.logger import get_logger
from utils.config import config

log = get_logger("MedFactCheck.Reranker")

def _get_hf_token() -> Optional[str]:
    return os.getenv("HF_TOKEN")

class BiomedicalReranker:
    """Biomedical cross-encoder reranker used by the hybrid retriever."""

    def __init__(self, model_name: str = "ncbi/MedCPT-Cross-Encoder", device: Optional[str] = None):
        self.name = model_name
        self.device = device or self._auto_device()
        self._max_length = 512

        log.info(f"Loading reranker '{self.name}' on {self.device}")
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
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise ImportError("Reranker requires 'transformers'.") from exc

        hf_token = _get_hf_token()
        token_kwargs = {"token": hf_token} if hf_token else {}

        self._tok = AutoTokenizer.from_pretrained(self.name, **token_kwargs)
        self._model = AutoModelForSequenceClassification.from_pretrained(self.name, **token_kwargs).to(self.device).eval()

        if self.device == "cpu":
            log.info(f"Applying INT8 dynamic quantization to {self.name}...")
            self._model = torch.quantization.quantize_dynamic(self._model, {torch.nn.Linear}, dtype=torch.qint8)

    def rerank(self, query: str, chunks: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Reranks a list of chunks based on a query using the Cross-Encoder.
        Returns the top_k chunks sorted by relevance score.
        """
        if not chunks:
            return []

        # Prepare pairs: [ [query, chunk1_text], [query, chunk2_text], ... ]
        pairs = [[query, chunk.get("text", "")] for chunk in chunks]

        with torch.no_grad():
            features = self._tok(
                pairs,
                padding=True,
                truncation=True,
                return_tensors="pt",
                max_length=self._max_length
            ).to(self.device)
            
            outputs = self._model(**features)
            scores = outputs.logits.squeeze(-1) # shape: (batch_size,) if num_labels=1
            
            # If the model has multiple labels, take the logit of the positive class
            if scores.ndim > 1:
                scores = scores[:, 1]
                
            scores = scores.cpu().numpy().tolist()

        # If a single item is passed, scores might be a float
        if not isinstance(scores, list):
            scores = [scores]

        # Attach reranker scores to chunks
        for i, chunk in enumerate(chunks):
            chunk["reranker_score"] = scores[i]

        # Sort descending by reranker_score
        sorted_chunks = sorted(chunks, key=lambda x: x["reranker_score"], reverse=True)
        return sorted_chunks[:top_k]

_DEFAULT_RERANKER: Optional[BiomedicalReranker] = None

def get_default_reranker() -> BiomedicalReranker:
    global _DEFAULT_RERANKER
    if _DEFAULT_RERANKER is None:
        model_name = config.get("retrieval.reranker.model_name", "ncbi/MedCPT-Cross-Encoder")
        _DEFAULT_RERANKER = BiomedicalReranker(model_name=model_name)
    return _DEFAULT_RERANKER

