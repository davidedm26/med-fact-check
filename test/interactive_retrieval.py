"""
Interactive Retrieval Tester
============================
REPL that lets you manually feed a subclaim to the retrieval subgraph
and inspect the full output (coins, queries, chunks).

Usage:
    python test/interactive_retrieval.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _PROJECT_ROOT / "src"

_src_str = str(_SRC_DIR)
if _src_str in sys.path:
    sys.path.remove(_src_str)
sys.path.insert(0, _src_str)

import types as _types

for _mod in list(sys.modules):
    if _mod == "utils" or _mod.startswith("utils."):
        del sys.modules[_mod]

_utils_pkg = _types.ModuleType("utils")
_utils_pkg.__path__ = [str(_SRC_DIR / "utils")]
_utils_pkg.__package__ = "utils"
sys.modules["utils"] = _utils_pkg

from dotenv import load_dotenv

load_dotenv(_PROJECT_ROOT / ".env")

os.environ["MONGO_LOGGING_ENABLED"] = "false"

# pyrefly: ignore [missing-import]
from utils.config import config
# pyrefly: ignore [missing-import]
from utils.llm_factory import get_llm_with_tools
# pyrefly: ignore [missing-import]
from prompts.retrieve import (
    retrieval_source_selection_schema,
)
# pyrefly: ignore [missing-import]
from stages.retrieval_team import build_retrieval_graph

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------

class C:
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    CYAN    = "\033[96m"
    MAGENTA = "\033[95m"
    RESET   = "\033[0m"

# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def print_header():
    print(f"\n{C.CYAN}{'=' * 66}")
    print(f"       INTERACTIVE RETRIEVAL TESTER")
    print(f"{'=' * 66}{C.RESET}\n")

def print_results(response: dict, elapsed: float):
    source = response.get("retrieval_source", {})
    queries_by_source = response.get("queries_by_source", {})
    all_queries = [q for qs in queries_by_source.values() for q in qs]
    downloaded_chunks = response.get("downloaded_chunks", [])
    chunks = response.get("retrieved_chunks", [])
    alpha = config.get("retrieval.hybrid.alpha", 0.5)

    # ── Source Allocation ──
    print(f"\n{C.CYAN}{'-' * 66}")
    print(f"  STEP 1 — Source Selection")
    print(f"{'-' * 66}{C.RESET}")
    for src, coins in source.items():
        color = C.GREEN if coins > 0 else C.DIM
        print(f"  {color}{src}: {coins} coins{C.RESET}")
    print()

    # ── Query Generation & Download ──
    print(f"{C.CYAN}{'-' * 66}")
    print(f"  STEP 2 — Queries & Downloading")
    print(f"{'-' * 66}{C.RESET}")
    print(f"  {C.BOLD}Generated queries by source:{C.RESET}")
    for src, queries in queries_by_source.items():
        if queries:
            print(f"    {C.BOLD}{src}:{C.RESET}")
            for i, q in enumerate(queries, 1):
                print(f"      {C.YELLOW}{i}. {q}{C.RESET}")
    print(f"\n  {C.DIM}Downloaded {len(downloaded_chunks)} distinct chunks from sources.{C.RESET}")
    print()

    # ── Universal Retriever ──
    print(f"{C.CYAN}{'-' * 66}")
    print(f"  STEP 3 — Universal RRF Retriever (alpha={alpha})")
    print(f"{'-' * 66}{C.RESET}")
    if not chunks:
        print(f"  {C.RED}No chunks retrieved.{C.RESET}")
    else:
        for i, chunk in enumerate(chunks, 1):
            text = chunk.get("text", "")
            meta = chunk.get("metadata", {})
            doc_id = meta.get("id", "Unknown")
            print(f"  {C.BOLD}[Rank {i}] From Doc ID: {doc_id}{C.RESET}")
            print(f"  {text}\n")

    # ── Summary ──
    print(f"{C.CYAN}{'-' * 66}")
    print(f"  SUMMARY")
    print(f"{'─' * 66}{C.RESET}")
    print(f"  Queries generated:       {C.BOLD}{len(all_queries)}{C.RESET}")
    print(f"  Chunks downloaded:       {C.BOLD}{len(downloaded_chunks)}{C.RESET}")
    print(f"  Chunks retrieved:        {C.GREEN}{len(chunks)}{C.RESET}")
    print(f"  Time:                    {elapsed:.1f}s")
    print(f"{C.CYAN}{'-' * 66}{C.RESET}\n")

# ---------------------------------------------------------------------------
# Main REPL
# ---------------------------------------------------------------------------

def main():
    print_header()

    # ── Init LLM ──
    provider = config.get("llm.provider", "google")
    provider_settings = config.get(f"llm.providers.{provider}", {})
    model_name = provider_settings.get(
        "model_name", config.get("llm.model_name", "gemma-4-26b-a4b-it")
    )
    temperature = config.get("llm.temperature", 0.2)
    base_url = provider_settings.get("base_url")

    print(f"  {C.DIM}Provider:{C.RESET}    {provider}")
    print(f"  {C.DIM}Model:{C.RESET}       {model_name}")
    print(f"  {C.DIM}Temperature:{C.RESET} {temperature}")
    print(f"\n  Initializing LLMs...", end=" ", flush=True)

    base_llm = get_llm_with_tools(
        [],
        provider=provider,
        model_name=model_name,
        temperature=temperature,
        base_url=base_url,
        allow_tools=False,
    )

    source_selector_agent = base_llm.with_structured_output(
        retrieval_source_selection_schema, method="function_calling"
    )

    retrieval_graph = build_retrieval_graph(source_selector_agent, base_llm)

    print(f"{C.GREEN}Ready!{C.RESET}\n")
    print(f"  Type a subclaim and press Enter. Empty input or Ctrl+C to quit.\n")

    # ── REPL loop ──
    while True:
        try:
            subclaim = input(f"{C.MAGENTA}> Subclaim:{C.RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{C.DIM}Bye!{C.RESET}")
            break

        if not subclaim:
            print(f"{C.DIM}Bye!{C.RESET}")
            break

        print(f"\n  {C.DIM}Processing...{C.RESET}", flush=True)

        t0 = time.time()
        try:
            response = retrieval_graph.invoke(
                {
                    "subclaim_id": "interactive_test",
                    "subclaim": subclaim,
                    "messages": [("user", subclaim)]
                }
            )
        except Exception as exc:
            print(f"\n  {C.RED}ERROR: {exc}{C.RESET}\n")
            continue

        elapsed = time.time() - t0
        print_results(response, elapsed)

if __name__ == "__main__":
    main()
