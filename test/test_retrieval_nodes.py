"""
Ablation Test -- Retrieval Nodes
================================
Tests the individual components of the Retrieval Team against a gold set.
Evaluates: Source Selector, Query Generator, and Strategy Router.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _PROJECT_ROOT / "src"

_src_str = str(_SRC_DIR)
if _src_str in sys.path:
    sys.path.remove(_src_str)
sys.path.insert(0, _src_str)

import importlib
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
    get_retrieval_query_generation_schema
)
from langchain_core.messages import HumanMessage
# pyrefly: ignore [missing-import]
from tools.retrieve.dense import BiomedicalEmbedder
import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GOLD_SET_PATH = _PROJECT_ROOT / "test" / "data" / "retrieval_gold.json"
REPORTS_DIR = _PROJECT_ROOT / "test" / "reports"

print("Loading BiomedicalEmbedder for semantic test...")
_embedder = BiomedicalEmbedder(model_name="medcpt", device="cpu")
print("Embedder loaded.")

def _cosine_sim(vec1: np.ndarray, vec2: np.ndarray) -> float:
    return float(np.dot(vec1, vec2))

def _best_match_overlap(
    predicted_queries: list[str],
    expected_queries: list[str],
) -> float:
    if not expected_queries:
        return 1.0
    if not predicted_queries:
        return 0.0

    pred_vecs = _embedder.embed_passages(predicted_queries)
    exp_vecs = _embedder.embed_passages(expected_queries)

    available = list(range(len(predicted_queries)))
    scores: list[float] = []

    for i in range(len(expected_queries)):
        best_score = 0.0
        best_idx = -1
        for idx in available:
            sim = _cosine_sim(exp_vecs[i], pred_vecs[idx])
            if sim > best_score:
                best_score = sim
                best_idx = idx
        if best_idx >= 0 and best_score >= 0.8:
            available.remove(best_idx)
        else:
            best_score = 0.0
        scores.append(best_score)

    return sum(scores) / len(scores)


def compute_metrics(
    pred_coins: dict[str, int], 
    pred_queries: list[str], 
    pred_strategy: str, 
    gold_entry: dict[str, Any],
    dynamic_coins: int
) -> dict[str, Any]:
    expected_source = gold_entry["expected_target_source"]
    expected_queries = gold_entry["expected_queries"]

    assigned_coins = pred_coins.get(expected_source, 0)
    source_score = assigned_coins / max(dynamic_coins, 1)
    source_score = min(1.0, max(0.0, source_score))

    semantic_overlap = _best_match_overlap(pred_queries, expected_queries)

    return {
        "subclaim_id": gold_entry["subclaim_id"],
        "subclaim": gold_entry["subclaim"],
        "expected_source": expected_source,
        "predicted_coins": pred_coins,
        "source_accuracy_score": round(source_score, 4),
        "expected_queries": expected_queries,
        "predicted_queries": pred_queries,
        "semantic_overlap_score": round(semantic_overlap, 4)
    }

def print_claim_report(gold_entry: dict, metrics: dict) -> None:
    print(f"\n{'-' * 70}")
    print(f"  Subclaim: {gold_entry['subclaim_id']}")
    print(f"  Text:     {gold_entry['subclaim'][:100]}...")
    print(f"{'-' * 70}")
    print(f"  Source:   expected={metrics['expected_source']} allocated={metrics['predicted_coins']} "
          f"(Score: {metrics['source_accuracy_score']:.2f})")
    print(f"  Queries:  semantic overlap={metrics['semantic_overlap_score']:.2f}")

def compute_aggregate_metrics(results: list[dict]) -> dict[str, Any]:
    n = len(results)
    if n == 0:
        return {}

    def _avg(key: str) -> float:
        return round(sum(r[key] for r in results) / n, 4)

    def _rate(key: str) -> float:
        return round(sum(1 for r in results if r[key]) / n, 4)

    return {
        "total_subclaims": n,
        "source_accuracy": _avg("source_accuracy_score"),
        "avg_queries_semantic_overlap": _avg("semantic_overlap_score")
    }

def print_aggregate_report(agg: dict) -> None:
    print(f"\n{'=' * 70}")
    print("  AGGREGATE METRICS")
    print(f"{'=' * 70}")
    print(f"  Total subclaims tested:      {agg.get('total_subclaims', 0)}")
    print(f"  Source selector accuracy:    {agg.get('source_accuracy', 0):.2%}")
    print(f"  Avg queries overlap score:   {agg.get('avg_queries_semantic_overlap', 0):.2%}")
    print(f"{'=' * 70}")

def main() -> None:
    print("\n" + "=" * 66)
    print("           ABLATION TEST -- RETRIEVAL NODES")
    print("=" * 66 + "\n")

    if not GOLD_SET_PATH.exists():
        print(f"ERROR: Gold set not found at {GOLD_SET_PATH}")
        sys.exit(1)

    with open(GOLD_SET_PATH, "r", encoding="utf-8") as f:
        gold_data = json.load(f)

    gold_subclaims = gold_data.get("gold_subclaims", [])
    print(f"Loaded {len(gold_subclaims)} subclaims from gold set\n")

    provider = config.get("llm.provider", "google")
    provider_settings = config.get(f"llm.providers.{provider}", {})
    model_name = provider_settings.get("model_name", config.get("llm.model_name", "gemma-4-26b-a4b-it"))
    temperature = config.get("llm.temperature", 0.2)
    base_url = provider_settings.get("base_url")

    print(f"Provider:    {provider}")
    print(f"Model:       {model_name}")
    print(f"Temperature: {temperature}\n")

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

    all_results: list[dict] = []
    total_time = 0.0

    dynamic_coins = config.get("retrieval.dynamic_coins", 3)
    # pyre-ignore [58]
    from prompts.retrieve import retrieval_source_selection_prompt, retrieval_query_generation_prompt

    for idx, gold_entry in enumerate(gold_subclaims, 1):
        subclaim_text = gold_entry["subclaim"]
        sub_id = gold_entry["subclaim_id"]
        expected_source = gold_entry["expected_target_source"]
        expected_query_for_strategy = gold_entry["expected_queries"][0] if gold_entry["expected_queries"] else subclaim_text

        print(f"\n[{idx}/{len(gold_subclaims)}] Testing: {sub_id}")

        t0 = time.time()
        
        try:
            # 1. Test Source Selector
            sys_prompt_source = retrieval_source_selection_prompt.format(total_coins=dynamic_coins)
            source_res = source_selector_agent.invoke([
                {"role": "system", "content": sys_prompt_source},
                {"role": "user", "content": subclaim_text}
            ])
            
            pred_coins = {"systematic_reviews": 0, "knowledge_base": 0, "literature": 0}
            if isinstance(source_res, dict):
                pred_coins["systematic_reviews"] = max(0, int(source_res.get("systematic_reviews_coins", 0)))
                pred_coins["knowledge_base"] = max(0, int(source_res.get("knowledge_base_coins", 0)))
                pred_coins["literature"] = max(0, int(source_res.get("literature_coins", 0)))

            # 2. Test Query Generator
            sys_prompt_query = retrieval_query_generation_prompt.format(
                num_queries=dynamic_coins, target_source=expected_source
            )
            query_generator_agent = base_llm.with_structured_output(
                get_retrieval_query_generation_schema(dynamic_coins), method="function_calling"
            )
            query_res = query_generator_agent.invoke([
                {"role": "system", "content": sys_prompt_query},
                {"role": "user", "content": subclaim_text}
            ])
            pred_queries = query_res.get("search_queries", []) if isinstance(query_res, dict) else getattr(query_res, "search_queries", [])

        except Exception as exc:
            print(f"  ERROR invoking agents: {exc}")
            pred_coins, pred_queries = {}, []

        elapsed = time.time() - t0
        total_time += elapsed
        print(f"  Completed in {elapsed:.1f}s")

        metrics = compute_metrics(
            pred_coins, pred_queries, "hybrid", gold_entry, dynamic_coins
        )
        all_results.append(metrics)
        print_claim_report(gold_entry, metrics)

    aggregate = compute_aggregate_metrics(all_results)
    print_aggregate_report(aggregate)
    print(f"\nTotal execution time: {total_time:.1f}s")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"retrieval_nodes_report_{timestamp}.json"

    report = {
        "run_timestamp": datetime.now().isoformat(),
        "config": {
            "provider": provider,
            "model_name": model_name,
            "temperature": temperature,
        },
        "total_execution_time_s": round(total_time, 2),
        "per_claim_results": all_results,
        "aggregate_metrics": aggregate,
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    print(f"\nReport saved to: {report_path}")

if __name__ == "__main__":
    main()
