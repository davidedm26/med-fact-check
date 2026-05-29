"""
Interactive Decompose Tester
============================
REPL that lets you manually feed claims to the decompose subgraph
and inspect the full output (predicates, classification, filter).

Usage:
    python tests/interactive_decompose.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup (same as test_decompose_stage.py)
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
from prompts.decompose import claim_decomposition, claim_classification
# pyrefly: ignore [missing-import]
from stages.decomposing_team import build_decompose_graph

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
    print(f"       INTERACTIVE DECOMPOSE TESTER")
    print(f"{'=' * 66}{C.RESET}\n")


def print_results(response: dict, elapsed: float):
    predicates = response.get("predicates") or []
    predicate_type_dict = response.get("predicate_type_dict") or []
    verifiable_subclaims = response.get("verifiable_subclaims") or []

    # ── Extracted predicates ──
    print(f"\n{C.CYAN}{'-' * 66}")
    print(f"  STEP 1 — Decomposition   ({len(predicates)} predicates extracted)")
    print(f"{'-' * 66}{C.RESET}")

    for i, p in enumerate(predicates, 1):
        if isinstance(p, dict):
            rel = p.get("relation", "?")
            subj = p.get("subject", "?")
            obj = p.get("object", "?")
            query = p.get("search_query", "")
            print(f"  {C.BOLD}[{i}]{C.RESET} {C.DIM}relation:{C.RESET} {rel}")
            print(f"      {C.DIM}subject:{C.RESET}  {subj}")
            print(f"      {C.DIM}object:{C.RESET}   {obj}")
            print(f"      {C.DIM}query:{C.RESET}    {C.YELLOW}{query}{C.RESET}")
        else:
            print(f"  {C.BOLD}[{i}]{C.RESET} {p}")
        print()

    # ── Classification ──
    print(f"{C.CYAN}{'-' * 66}")
    print(f"  STEP 2 — Classification")
    print(f"{'-' * 66}{C.RESET}")

    for i, entry in enumerate(predicate_type_dict, 1):
        if isinstance(entry, dict):
            q = entry.get("query", "?")
            t = entry.get("type", "?")
            color = C.GREEN if t == "verifiable" else C.RED
            label = f"{color}{t.upper()}{C.RESET}"
            print(f"  {C.BOLD}[{i}]{C.RESET} {label}  {q}")
        else:
            print(f"  {C.BOLD}[{i}]{C.RESET} {entry}")
    print()

    # ── Final verifiable subclaims ──
    print(f"{C.CYAN}{'-' * 66}")
    print(f"  STEP 3 — Filter   ({len(verifiable_subclaims)} verifiable subclaims)")
    print(f"{'-' * 66}{C.RESET}")

    if verifiable_subclaims:
        for i, sc in enumerate(verifiable_subclaims, 1):
            print(f"  {C.GREEN}[OK]{C.RESET} {sc}")
    else:
        print(f"  {C.RED}[X] No verifiable subclaims survived the filter.{C.RESET}")
    print()

    # ── Summary ──
    print(f"{C.CYAN}{'-' * 66}")
    print(f"  SUMMARY")
    print(f"{'─' * 66}{C.RESET}")
    n_pred = len(predicates)
    n_verif = len(verifiable_subclaims)
    n_dropped = len(predicate_type_dict) - n_verif
    print(f"  Predicates extracted:    {C.BOLD}{n_pred}{C.RESET}")
    print(f"  Verifiable (kept):       {C.GREEN}{n_verif}{C.RESET}")
    print(f"  Non-verifiable (dropped):{C.RED} {n_dropped}{C.RESET}")
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
    print(f"\n  Initializing LLM...", end=" ", flush=True)

    base_llm = get_llm_with_tools(
        [],
        provider=provider,
        model_name=model_name,
        temperature=temperature,
        base_url=base_url,
        allow_tools=False,
    )

    decomposition_agent = base_llm.with_structured_output(
        claim_decomposition, method="function_calling"
    )
    classification_agent = base_llm.with_structured_output(
        claim_classification, method="function_calling"
    )

    decompose_graph = build_decompose_graph(decomposition_agent, classification_agent)

    print(f"{C.GREEN}Ready!{C.RESET}\n")
    print(f"  Type a claim and press Enter. Empty input or Ctrl+C to quit.\n")

    # ── REPL loop ──
    while True:
        try:
            claim = input(f"{C.MAGENTA}> Claim:{C.RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{C.DIM}Bye!{C.RESET}")
            break

        if not claim:
            print(f"{C.DIM}Bye!{C.RESET}")
            break

        print(f"\n  {C.DIM}Processing...{C.RESET}", flush=True)

        t0 = time.time()
        try:
            response = decompose_graph.invoke(
                {"messages": [("user", claim)]}
            )
        except Exception as exc:
            print(f"\n  {C.RED}ERROR: {exc}{C.RESET}\n")
            continue

        elapsed = time.time() - t0
        print_results(response, elapsed)


if __name__ == "__main__":
    main()
