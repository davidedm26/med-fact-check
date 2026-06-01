import os

dense_path = "b:/Workspace/Unina-MSc/BIG-DATA/med-fact-check/src/tools/retrieve/dense.py"
sparse_path = "b:/Workspace/Unina-MSc/BIG-DATA/med-fact-check/src/tools/retrieve/sparse.py"
chunking_path = "b:/Workspace/Unina-MSc/BIG-DATA/med-fact-check/src/tools/retrieve/chunking.py"
retrieval_path = "b:/Workspace/Unina-MSc/BIG-DATA/med-fact-check/src/stages/retrieval_team.py"

with open(dense_path, "r", encoding="utf-8") as f:
    dense_content = f.read()

# Extract from dense.py: imports, SourceMetadata, IndexedChunk, RetrievedText, BiomedicalChunker
import_block = """from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple
"""

source_meta_block = dense_content.split("@dataclass\nclass SourceMetadata:")[1].split("@dataclass\nclass IndexedChunk:")[0]
indexed_chunk_block = dense_content.split("@dataclass\nclass IndexedChunk:")[1].split("@dataclass\nclass RetrievedText:")[0]
retrieved_text_block = dense_content.split("@dataclass\nclass RetrievedText:")[1].split("@dataclass\nclass BiomedicalChunker:")[0]
chunker_block = dense_content.split("@dataclass\nclass BiomedicalChunker:")[1].split("class BiomedicalEmbedder:")[0]

chunking_content = import_block + "\n@dataclass\nclass SourceMetadata:" + source_meta_block + "@dataclass\nclass IndexedChunk:" + indexed_chunk_block + "@dataclass\nclass RetrievedText:" + retrieved_text_block + "@dataclass\nclass BiomedicalChunker:" + chunker_block

with open(chunking_path, "w", encoding="utf-8") as f:
    f.write(chunking_content)

# Re-write dense.py
new_dense_imports = """from __future__ import annotations
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

"""

embedder_and_store_and_retriever = "class BiomedicalEmbedder:" + dense_content.split("class BiomedicalEmbedder:")[1].split("_DEFAULT_DENSE_RETRIEVER: Optional[DenseRetriever] = None")[0]

bottom_dense = """
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
    \"\"\"Dense retrieval using a single biomedical embedding model and cosine similarity.\"\"\"
    if not chunks:
        return []
    return _get_default_dense_retriever().retrieve(query=query, chunks=chunks, top_k=top_k)
"""

with open(dense_path, "w", encoding="utf-8") as f:
    f.write(new_dense_imports + embedder_and_store_and_retriever + bottom_dense)

# Re-write sparse.py
with open(sparse_path, "r", encoding="utf-8") as f:
    sparse_content = f.read()

sparse_content = sparse_content.replace(
    "from tools.retrieve.core.chunking import SemanticChunker",
    "from tools.retrieve.chunking import BiomedicalChunker"
)
sparse_content = sparse_content.replace(
    "chunk_size = config.get(\"retrieval.dense.chunk_size\", 300)",
    "chunk_size = config.get(\"retrieval.chunking.chunk_size\", 300)"
)
sparse_content = sparse_content.replace(
    "chunk_overlap = config.get(\"retrieval.dense.overlap\", 50)",
    "chunk_overlap = config.get(\"retrieval.chunking.overlap\", 50)"
)
sparse_content = sparse_content.replace(
    "chunker = SemanticChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)",
    "chunker = BiomedicalChunker(chunk_size=chunk_size, overlap=chunk_overlap)"
)
sparse_content = sparse_content.replace(
    "chunks = chunker.chunk(text, meta)",
    "from tools.retrieve.chunking import SourceMetadata\n        source_meta = SourceMetadata.from_dict(meta)\n        chunks = chunker.chunk(text, source_meta)"
)

with open(sparse_path, "w", encoding="utf-8") as f:
    f.write(sparse_content)

# Re-write retrieval_team.py to rename universal to hybrid
with open(retrieval_path, "r", encoding="utf-8") as f:
    team_content = f.read()

team_content = team_content.replace("universal_retriever_node", "hybrid_retriever_node")
team_content = team_content.replace("universal_retriever start", "hybrid_retriever start")
team_content = team_content.replace("universal_retriever using alpha", "hybrid_retriever using alpha")
team_content = team_content.replace("universal_retriever extracted", "hybrid_retriever extracted")
team_content = team_content.replace("universal_retriever", "hybrid_retriever")
team_content = team_content.replace("retrieval.universal.top_k", "retrieval.hybrid.top_k")

with open(retrieval_path, "w", encoding="utf-8") as f:
    f.write(team_content)

print("Refactor completed successfully!")
