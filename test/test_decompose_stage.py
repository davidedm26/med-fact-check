"""
Ablation Test -- Decompose Stage
================================
Runs the decompose subgraph in isolation against a curated gold set
and computes per-claim + aggregate quality metrics.
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
from prompts.decompose import claim_decomposition, claim_classification
# pyrefly: ignore [missing-import]
from stages.decomposing_team import build_decompose_graph
# pyrefly: ignore [missing-import]
from tools.retrieve.dense import BiomedicalEmbedder
import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GOLD_SET_PATH = _PROJECT_ROOT / "test" / "data" / "decompose_gold.json"
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

def compute_claim_metrics(
    predicted_state: dict[str, Any],
    gold_entry: dict[str, Any],
) -> dict[str, Any]:
    predicted_predicates_raw = predicted_state.get("predicates") or []
    predicate_type_dict = predicted_state.get("predicate_type_dict") or []
    verifiable_subclaims = predicted_state.get("verifiable_subclaims") or []

    predicted_queries: list[str] = []
    for p in predicted_predicates_raw:
        if isinstance(p, dict):
            predicted_queries.append(p.get("search_query", ""))
        else:
            predicted_queries.append(str(p))

    expected_queries_objs = gold_entry.get("expected_queries", [])
    expected_queries = [obj.get("query", "") for obj in expected_queries_objs]
    
    expected_count = gold_entry.get("expected_predicate_count", len(expected_queries))
    expected_verifiable_count = gold_entry.get("expected_verifiable_count", expected_count)

    pred_count = len(predicted_queries)

    count_match = pred_count == expected_count
    count_delta = abs(pred_count - expected_count)

    over = pred_count > expected_count
    under = pred_count < expected_count

    semantic_overlap = _best_match_overlap(predicted_queries, expected_queries)

    classification_correct = 0
    classification_total = 0

    for exp_obj in expected_queries_objs:
        exp_type = exp_obj.get("type", "verifiable")
        exp_q = exp_obj.get("query", "")
        classification_total += 1

        best_sim = 0.0
        matched_type = None
        
        if expected_queries:
            exp_vec = _embedder.embed_passages([exp_q])[0]
            for ptd_entry in predicate_type_dict:
                pred_q = ptd_entry.get("query", "")
                if not pred_q: continue
                pred_vec = _embedder.embed_passages([pred_q])[0]
                sim = _cosine_sim(exp_vec, pred_vec)
                if sim > best_sim:
                    best_sim = sim
                    matched_type = ptd_entry.get("type")
                    
        if best_sim >= 0.8 and matched_type is not None:
            if matched_type == exp_type:
                classification_correct += 1

    classification_accuracy = (
        classification_correct / classification_total if classification_total > 0 else 0.0
    )

    predicted_verifiable_count = len(verifiable_subclaims)
    tp = min(expected_verifiable_count, predicted_verifiable_count)
    fp = max(0, predicted_verifiable_count - expected_verifiable_count)
    fn = max(0, expected_verifiable_count - predicted_verifiable_count)

    filter_precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    filter_recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    return {
        "claim_id": gold_entry["claim_id"],
        "claim": gold_entry["claim"],
        "expected_predicate_count": expected_count,
        "predicted_predicate_count": pred_count,
        "predicate_count_match": count_match,
        "predicate_count_delta": count_delta,
        "over_decomposed": over,
        "under_decomposed": under,
        "semantic_overlap_score": round(semantic_overlap, 4),
        "classification_accuracy": round(classification_accuracy, 4),
        "expected_verifiable_count": expected_verifiable_count,
        "predicted_verifiable_count": predicted_verifiable_count,
        "filter_precision": round(filter_precision, 4),
        "filter_recall": round(filter_recall, 4),
        "predicted_queries": predicted_queries,
        "predicted_predicate_type_dict": predicate_type_dict,
        "predicted_verifiable_subclaims": verifiable_subclaims,
        "expected_queries": expected_queries_objs,
    }


def compute_aggregate_metrics(results: list[dict]) -> dict[str, Any]:
    n = len(results)
    if n == 0:
        return {}

    def _avg(key: str) -> float:
        return round(sum(r[key] for r in results) / n, 4)

    def _rate(key: str) -> float:
        return round(sum(1 for r in results if r[key]) / n, 4)

    return {
        "total_claims": n,
        "predicate_count_accuracy": _rate("predicate_count_match"),
        "avg_predicate_count_delta": _avg("predicate_count_delta"),
        "avg_semantic_overlap": _avg("semantic_overlap_score"),
        "avg_classification_accuracy": _avg("classification_accuracy"),
        "avg_filter_precision": _avg("filter_precision"),
        "avg_filter_recall": _avg("filter_recall"),
        "over_decomposition_rate": _rate("over_decomposed"),
        "under_decomposition_rate": _rate("under_decomposed"),
    }


def print_claim_report(gold_entry: dict, metrics: dict) -> None:
    print(f"\n{'-' * 70}")
    print(f"  Claim: {gold_entry['claim_id']}  ({gold_entry.get('complexity', '?')})")
    print(f"  Text:  {gold_entry['claim'][:100]}...")
    print(f"{'-' * 70}")
    print(f"  Predicates:  expected={metrics['expected_predicate_count']}  "
          f"predicted={metrics['predicted_predicate_count']}  "
          f"{'OK' if metrics['predicate_count_match'] else 'FAIL'}")
    print(f"  Overlap:     semantic={metrics['semantic_overlap_score']:.2f}")
    print(f"  Classify:    accuracy={metrics['classification_accuracy']:.2f}")
    print(f"  Filter:      precision={metrics['filter_precision']:.2f}  "
          f"recall={metrics['filter_recall']:.2f}")
    if metrics["over_decomposed"]:
        print(f"  [!] OVER-decomposed (+{metrics['predicate_count_delta']})")
    if metrics["under_decomposed"]:
        print(f"  [!] UNDER-decomposed (-{metrics['predicate_count_delta']})")


def print_aggregate_report(agg: dict) -> None:
    print(f"\n{'=' * 70}")
    print("  AGGREGATE METRICS")
    print(f"{'=' * 70}")
    print(f"  Total claims tested:         {agg.get('total_claims', 0)}")
    print(f"  Predicate count accuracy:    {agg.get('predicate_count_accuracy', 0):.2%}")
    print(f"  Avg predicate count delta:   {agg.get('avg_predicate_count_delta', 0):.2f}")
    print(f"  Avg semantic overlap:        {agg.get('avg_semantic_overlap', 0):.2%}")
    print(f"  Avg classification accuracy: {agg.get('avg_classification_accuracy', 0):.2%}")
    print(f"  Avg filter precision:        {agg.get('avg_filter_precision', 0):.2%}")
    print(f"  Avg filter recall:           {agg.get('avg_filter_recall', 0):.2%}")
    print(f"  Over-decomposition rate:     {agg.get('over_decomposition_rate', 0):.2%}")
    print(f"  Under-decomposition rate:    {agg.get('under_decomposition_rate', 0):.2%}")
    print(f"{'=' * 70}")


def main() -> None:
    print("\n" + "=" * 66)
    print("           ABLATION TEST -- DECOMPOSE STAGE")
    print("=" * 66 + "\n")

    if not GOLD_SET_PATH.exists():
        print(f"ERROR: Gold set not found at {GOLD_SET_PATH}")
        sys.exit(1)

    with open(GOLD_SET_PATH, "r", encoding="utf-8") as f:
        gold_data = json.load(f)

    gold_claims = gold_data.get("gold_claims", [])
    print(f"Loaded {len(gold_claims)} claims from gold set\n")

    provider = config.get("llm.provider", "google")
    provider_settings = config.get(f"llm.providers.{provider}", {})
    model_name = provider_settings.get(
        "model_name", config.get("llm.model_name", "gemma-4-26b-a4b-it")
    )
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

    decomposition_agent = base_llm.with_structured_output(
        claim_decomposition, method="function_calling"
    )
    classification_agent = base_llm.with_structured_output(
        claim_classification, method="function_calling"
    )

    decompose_graph = build_decompose_graph(decomposition_agent, classification_agent)

    all_results: list[dict] = []
    total_time = 0.0

    for idx, gold_entry in enumerate(gold_claims, 1):
        claim_text = gold_entry["claim"]
        claim_id = gold_entry["claim_id"]
        print(f"\n[{idx}/{len(gold_claims)}] Testing: {claim_id}")

        t0 = time.time()
        try:
            response = decompose_graph.invoke(
                {"messages": [("user", claim_text)]}
            )
        except Exception as exc:
            print(f"  ERROR invoking graph: {exc}")
            all_results.append({
                "claim_id": claim_id,
                "claim": claim_text,
                "error": str(exc),
                "expected_predicate_count": gold_entry.get("expected_predicate_count", 0),
                "predicted_predicate_count": 0,
                "predicate_count_match": False,
                "predicate_count_delta": gold_entry.get("expected_predicate_count", 0),
                "over_decomposed": False,
                "under_decomposed": True,
                "semantic_overlap_score": 0.0,
                "classification_accuracy": 0.0,
                "expected_verifiable_count": gold_entry.get("expected_verifiable_count", 0),
                "predicted_verifiable_count": 0,
                "filter_precision": 0.0,
                "filter_recall": 0.0,
                "predicted_queries": [],
                "predicted_predicate_type_dict": [],
                "predicted_verifiable_subclaims": [],
                "expected_queries": gold_entry.get("expected_queries", []),
            })
            continue

        elapsed = time.time() - t0
        total_time += elapsed
        print(f"  Completed in {elapsed:.1f}s")

        metrics = compute_claim_metrics(response, gold_entry)
        all_results.append(metrics)
        print_claim_report(gold_entry, metrics)

    aggregate = compute_aggregate_metrics(all_results)
    print_aggregate_report(aggregate)
    print(f"\nTotal execution time: {total_time:.1f}s")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"decompose_report_{timestamp}.json"

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
