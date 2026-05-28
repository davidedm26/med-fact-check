"""
Ablation Test -- Decompose Stage
================================
Runs the decompose subgraph in isolation against a curated gold set
and computes per-claim + aggregate quality metrics.

Usage:
    cd src
    python -m tests.test_decompose_stage          (from project root -- not recommended)
    python ../tests/test_decompose_stage.py        (from src/)

Or simply:
    cd <project_root>
    python tests/test_decompose_stage.py

The script adds ``src/`` to sys.path so that project imports work
regardless of how it is invoked.
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
# Path setup -- make sure ``src/`` is importable
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _PROJECT_ROOT / "src"

# Ensure src/ is at position 0 so local packages (stages, prompts, etc.)
# take priority over any globally installed packages with the same name.
_src_str = str(_SRC_DIR)
if _src_str in sys.path:
    sys.path.remove(_src_str)
sys.path.insert(0, _src_str)

# ---------------------------------------------------------------------------
# Fix ``utils`` module shadowing
# ---------------------------------------------------------------------------
# A globally installed ``utils`` single-file module (pip package) may shadow
# the local ``src/utils/`` package.  We explicitly register the local
# directory as the ``utils`` package before importing anything from it.
import importlib
import types as _types

for _mod in list(sys.modules):
    if _mod == "utils" or _mod.startswith("utils."):
        del sys.modules[_mod]

_utils_pkg = _types.ModuleType("utils")
_utils_pkg.__path__ = [str(_SRC_DIR / "utils")]
_utils_pkg.__package__ = "utils"
sys.modules["utils"] = _utils_pkg

# Now we can safely import project modules
from dotenv import load_dotenv

load_dotenv(_PROJECT_ROOT / ".env")

# Force-disable MongoDB logging for tests to avoid polluting the database
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
# Constants
# ---------------------------------------------------------------------------

GOLD_SET_PATH = _PROJECT_ROOT / "tests" / "data" / "decompose_gold.json"
REPORTS_DIR = _PROJECT_ROOT / "tests" / "reports"
JACCARD_THRESHOLD = 0.5  # minimum token-overlap for a "match"


# ===========================================================================
# Fuzzy matching helpers
# ===========================================================================


def _tokenize(text: str) -> set[str]:
    """Lowercase token set (split on whitespace + punctuation)."""
    import re
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _jaccard(a: str, b: str) -> float:
    """Token-level Jaccard similarity between two strings."""
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _best_match_overlap(
    predicted: list[dict],
    expected: list[dict],
    field: str,
) -> float:
    """
    Greedy best-match overlap for a given field (subject / object / relation).

    For each expected predicate, find the predicted predicate with the
    highest Jaccard similarity on ``field`` (above threshold), consume that
    pair, and average the scores.  Unmatched expected predicates contribute 0.
    """
    if not expected:
        return 1.0  # nothing to match -> perfect by convention

    available = list(range(len(predicted)))
    scores: list[float] = []

    for exp in expected:
        best_score = 0.0
        best_idx = -1
        exp_val = exp.get(field, "")
        for idx in available:
            pred_val = predicted[idx].get(field, "")
            sim = _jaccard(exp_val, pred_val)
            if sim > best_score:
                best_score = sim
                best_idx = idx
        if best_idx >= 0 and best_score >= JACCARD_THRESHOLD:
            available.remove(best_idx)
        else:
            best_score = 0.0  # no match above threshold
        scores.append(best_score)

    return sum(scores) / len(scores)


# ===========================================================================
# Metric computation
# ===========================================================================


def compute_claim_metrics(
    predicted_state: dict[str, Any],
    gold_entry: dict[str, Any],
) -> dict[str, Any]:
    """Compute per-claim metrics comparing predicted output with gold."""
    # -- Extract predicted data --
    predicted_predicates_raw = predicted_state.get("predicates") or []
    predicate_type_dict = predicted_state.get("predicate_type_dict") or []
    verifiable_subclaims = predicted_state.get("verifiable_subclaims") or []

    # Normalise predicted predicates into a flat list of dicts
    predicted_predicates: list[dict] = []
    for p in predicted_predicates_raw:
        if isinstance(p, dict):
            predicted_predicates.append(p)
        else:
            predicted_predicates.append({"relation": str(p), "subject": "", "object": ""})

    # -- Gold data --
    expected_predicates = gold_entry.get("expected_predicates", [])
    expected_count = gold_entry.get("expected_predicate_count", len(expected_predicates))
    expected_verifiable_count = gold_entry.get("expected_verifiable_count", expected_count)

    pred_count = len(predicted_predicates)

    # 1. Predicate count match
    count_match = pred_count == expected_count
    count_delta = abs(pred_count - expected_count)

    # 2. Over / under decomposition
    over = pred_count > expected_count
    under = pred_count < expected_count

    # 3. S/R/O fuzzy overlap
    subject_overlap = _best_match_overlap(predicted_predicates, expected_predicates, "subject")
    object_overlap = _best_match_overlap(predicted_predicates, expected_predicates, "object")
    relation_overlap = _best_match_overlap(predicted_predicates, expected_predicates, "relation")

    # 4. Classification accuracy
    #    Compare predicted type assignments with gold types.
    #    Build a map: for each expected predicate, find its best match
    #    in predicate_type_dict and check if the type is correct.
    classification_correct = 0
    classification_total = 0

    for exp_pred in expected_predicates:
        exp_type = exp_pred.get("type", "verifiable")
        exp_subj = exp_pred.get("subject", "")
        classification_total += 1

        # Find the best-matching entry in predicate_type_dict
        best_sim = 0.0
        matched_type = None
        for ptd_entry in predicate_type_dict:
            pred_obj = ptd_entry.get("predicate", {})
            if isinstance(pred_obj, dict):
                sim = _jaccard(exp_subj, pred_obj.get("subject", ""))
            else:
                sim = _jaccard(exp_subj, str(pred_obj))
            if sim > best_sim:
                best_sim = sim
                matched_type = ptd_entry.get("type")
        if best_sim >= JACCARD_THRESHOLD and matched_type is not None:
            if matched_type == exp_type:
                classification_correct += 1

    classification_accuracy = (
        classification_correct / classification_total if classification_total > 0 else 0.0
    )

    # 5. Filter precision & recall
    #    Expected verifiable count vs. predicted verifiable subclaims
    predicted_verifiable_count = len(verifiable_subclaims)

    # Filter precision: of the predicates the filter kept, how many were correct?
    # We approximate: if the filter output count is <= expected_verifiable_count, precision = 1
    # (since we don't have per-subclaim ground truth matching here, we use count-based proxy)
    #
    # For a more precise version, we'd match each verifiable_subclaim to expected verifiable predicates.
    # Here we use the count-based heuristic:
    expected_verifiable_set_size = expected_verifiable_count
    actual_verifiable_set_size = predicted_verifiable_count

    # True positives: min of expected and predicted (assuming alignment)
    # This is a simplification; real TP would need content matching
    tp = min(expected_verifiable_set_size, actual_verifiable_set_size)
    fp = max(0, actual_verifiable_set_size - expected_verifiable_set_size)
    fn = max(0, expected_verifiable_set_size - actual_verifiable_set_size)

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
        "subject_overlap_score": round(subject_overlap, 4),
        "object_overlap_score": round(object_overlap, 4),
        "relation_overlap_score": round(relation_overlap, 4),
        "classification_accuracy": round(classification_accuracy, 4),
        "expected_verifiable_count": expected_verifiable_count,
        "predicted_verifiable_count": predicted_verifiable_count,
        "filter_precision": round(filter_precision, 4),
        "filter_recall": round(filter_recall, 4),
        "predicted_predicates": predicted_predicates,
        "predicted_predicate_type_dict": predicate_type_dict,
        "predicted_verifiable_subclaims": verifiable_subclaims,
        "expected_predicates": expected_predicates,
    }


def compute_aggregate_metrics(results: list[dict]) -> dict[str, Any]:
    """Compute aggregate metrics across all claims."""
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
        "avg_subject_overlap": _avg("subject_overlap_score"),
        "avg_object_overlap": _avg("object_overlap_score"),
        "avg_relation_overlap": _avg("relation_overlap_score"),
        "avg_classification_accuracy": _avg("classification_accuracy"),
        "avg_filter_precision": _avg("filter_precision"),
        "avg_filter_recall": _avg("filter_recall"),
        "over_decomposition_rate": _rate("over_decomposed"),
        "under_decomposition_rate": _rate("under_decomposed"),
    }


# ===========================================================================
# Console reporting
# ===========================================================================

_SEP = "-" * 70


def print_claim_report(gold_entry: dict, metrics: dict) -> None:
    """Print a compact per-claim report to the console."""
    print(f"\n{_SEP}")
    print(f"  Claim: {gold_entry['claim_id']}  ({gold_entry.get('complexity', '?')})")
    print(f"  Text:  {gold_entry['claim'][:100]}...")
    print(f"{_SEP}")
    print(f"  Predicates:  expected={metrics['expected_predicate_count']}  "
          f"predicted={metrics['predicted_predicate_count']}  "
          f"{'OK' if metrics['predicate_count_match'] else 'FAIL'}")
    print(f"  Overlap:     subject={metrics['subject_overlap_score']:.2f}  "
          f"object={metrics['object_overlap_score']:.2f}  "
          f"relation={metrics['relation_overlap_score']:.2f}")
    print(f"  Classify:    accuracy={metrics['classification_accuracy']:.2f}")
    print(f"  Filter:      precision={metrics['filter_precision']:.2f}  "
          f"recall={metrics['filter_recall']:.2f}")
    if metrics["over_decomposed"]:
        print(f"  [!] OVER-decomposed (+{metrics['predicate_count_delta']})")
    if metrics["under_decomposed"]:
        print(f"  [!] UNDER-decomposed (-{metrics['predicate_count_delta']})")


def print_aggregate_report(agg: dict) -> None:
    """Print the final aggregate summary."""
    print(f"\n{'=' * 70}")
    print("  AGGREGATE METRICS")
    print(f"{'=' * 70}")
    print(f"  Total claims tested:         {agg.get('total_claims', 0)}")
    print(f"  Predicate count accuracy:    {agg.get('predicate_count_accuracy', 0):.2%}")
    print(f"  Avg predicate count delta:   {agg.get('avg_predicate_count_delta', 0):.2f}")
    print(f"  Avg subject overlap:         {agg.get('avg_subject_overlap', 0):.2%}")
    print(f"  Avg object overlap:          {agg.get('avg_object_overlap', 0):.2%}")
    print(f"  Avg relation overlap:        {agg.get('avg_relation_overlap', 0):.2%}")
    print(f"  Avg classification accuracy: {agg.get('avg_classification_accuracy', 0):.2%}")
    print(f"  Avg filter precision:        {agg.get('avg_filter_precision', 0):.2%}")
    print(f"  Avg filter recall:           {agg.get('avg_filter_recall', 0):.2%}")
    print(f"  Over-decomposition rate:     {agg.get('over_decomposition_rate', 0):.2%}")
    print(f"  Under-decomposition rate:    {agg.get('under_decomposition_rate', 0):.2%}")
    print(f"{'=' * 70}")


# ===========================================================================
# Main
# ===========================================================================


def main() -> None:
    print("\n" + "=" * 66)
    print("           ABLATION TEST -- DECOMPOSE STAGE")
    print("=" * 66 + "\n")

    # -- Load gold set -------------------------------------------------
    if not GOLD_SET_PATH.exists():
        print(f"ERROR: Gold set not found at {GOLD_SET_PATH}")
        sys.exit(1)

    with open(GOLD_SET_PATH, "r", encoding="utf-8") as f:
        gold_data = json.load(f)

    gold_claims = gold_data.get("gold_claims", [])
    print(f"Loaded {len(gold_claims)} claims from gold set\n")

    # -- Setup LLM agents (standalone -- no full FactAgent needed) ------
    provider = config.get("llm.provider", "google")
    provider_settings = config.get(f"llm.providers.{provider}", {})
    model_name = provider_settings.get(
        "model_name", config.get("llm.model_name", "gemma-4-26b-a4b-it")
    )
    temperature = config.get("llm.temperature", 0.2)
    base_url = provider_settings.get("base_url")

    print(f"Provider:    {provider}")
    print(f"Model:       {model_name}")
    print(f"Temperature: {temperature}")
    print(f"Jaccard thr: {JACCARD_THRESHOLD}\n")

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

    # -- Build decompose graph -----------------------------------------
    decompose_graph = build_decompose_graph(decomposition_agent, classification_agent)

    # -- Run tests -----------------------------------------------------
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
            # Record a failure entry
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
                "subject_overlap_score": 0.0,
                "object_overlap_score": 0.0,
                "relation_overlap_score": 0.0,
                "classification_accuracy": 0.0,
                "expected_verifiable_count": gold_entry.get("expected_verifiable_count", 0),
                "predicted_verifiable_count": 0,
                "filter_precision": 0.0,
                "filter_recall": 0.0,
                "predicted_predicates": [],
                "predicted_predicate_type_dict": [],
                "predicted_verifiable_subclaims": [],
                "expected_predicates": gold_entry.get("expected_predicates", []),
            })
            continue

        elapsed = time.time() - t0
        total_time += elapsed
        print(f"  Completed in {elapsed:.1f}s")

        # Compute metrics
        metrics = compute_claim_metrics(response, gold_entry)
        all_results.append(metrics)
        print_claim_report(gold_entry, metrics)

    # -- Aggregate -----------------------------------------------------
    aggregate = compute_aggregate_metrics(all_results)
    print_aggregate_report(aggregate)
    print(f"\nTotal execution time: {total_time:.1f}s")

    # -- Save JSON report ----------------------------------------------
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"decompose_report_{timestamp}.json"

    report = {
        "run_timestamp": datetime.now().isoformat(),
        "config": {
            "provider": provider,
            "model_name": model_name,
            "temperature": temperature,
            "jaccard_threshold": JACCARD_THRESHOLD,
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
