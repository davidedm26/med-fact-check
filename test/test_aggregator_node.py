"""
Test Script -- Aggregator Node
==============================
Tests the LLM-based aggregator node against a set of predefined logic cases.
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
from prompts.aggregate import aggregator_schema
# pyrefly: ignore [missing-import]
from stages.aggregator import build_aggregate_node
from langchain_core.messages import HumanMessage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CASES_PATH = _PROJECT_ROOT / "test" / "data" / "aggregator_cases.json"
REPORTS_DIR = _PROJECT_ROOT / "test" / "reports"

def compute_metrics(
    eval_result: dict[str, Any], 
    gold_entry: dict[str, Any],
) -> dict[str, Any]:
    expected_label = gold_entry["expected_label"].lower()
    
    pred_label = eval_result.get("label", "nei").lower()
    if pred_label == "not_enough_information":
        pred_label = "nei"
    if expected_label == "not_enough_information":
        expected_label = "nei"
        
    confidence = float(eval_result.get("confidence", 0.0))
    label_correct = (pred_label == expected_label)
    
    return {
        "eval_id": gold_entry["eval_id"],
        "main_claim": gold_entry["main_claim"],
        "expected_label": expected_label,
        "predicted_label": pred_label,
        "confidence": confidence,
        "label_correct": label_correct,
        "logical_relationship": eval_result.get("logical_relationship", ""),
        "aggregation_analysis": eval_result.get("aggregation_analysis", ""),
        "justification": eval_result.get("justification", "")
    }

def print_claim_report(gold_entry: dict, metrics: dict) -> None:
    print(f"\n{'-' * 70}")
    print(f"  Eval ID:    {gold_entry['eval_id']}")
    print(f"  Main Claim: {gold_entry['main_claim'][:90]}...")
    print(f"{'-' * 70}")
    print(f"  Expected:   {metrics['expected_label'].upper()}")
    print(f"  Predicted:  {metrics['predicted_label'].upper()}")
    print(f"  Logic:      {metrics['logical_relationship']}")
    print(f"  Result:     {'OK' if metrics['label_correct'] else 'FAIL'} (conf={metrics['confidence']:.2f})")

def compute_aggregate_metrics(results: list[dict]) -> dict[str, Any]:
    n = len(results)
    if n == 0:
        return {}

    def _avg(key: str) -> float:
        return round(sum(r[key] for r in results) / n, 4)

    def _rate(key: str) -> float:
        return round(sum(1 for r in results if r[key]) / n, 4)
        
    per_label = {}
    for label in ["supported", "refuted", "nei"]:
        label_results = [r for r in results if r["expected_label"] == label]
        if label_results:
            acc = sum(1 for r in label_results if r["label_correct"]) / len(label_results)
            per_label[label] = round(acc, 4)

    return {
        "total_evaluations": n,
        "label_accuracy": _rate("label_correct"),
        "avg_confidence": _avg("confidence"),
        "per_label_accuracy": per_label
    }

def run_evaluation() -> None:
    provider = config.get("llm.provider", "google")
    model_name = config.get(f"llm.providers.{provider}.model_name", config.get("llm.model_name"))
    temperature = config.get("llm.temperature", 0.2)
    
    print(f"Running Aggregator tests...")
    print(f"Provider: {provider} | Model: {model_name}")

    base_llm = get_llm_with_tools(
        [], 
        provider=provider,
        model_name=model_name,
        temperature=temperature,
        allow_tools=False
    )
    
    aggregator_agent = base_llm.with_structured_output(
        aggregator_schema, method="function_calling"
    )

    aggregator_node = build_aggregate_node(aggregator_agent)

    if not CASES_PATH.exists():
        print(f"Error: Cases file not found at {CASES_PATH}")
        sys.exit(1)

    with open(CASES_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)

    print(f"Loaded {len(cases)} test cases.")

    results = []
    start_time = time.time()

    for idx, case in enumerate(cases, 1):
        print(f"\nProcessing [{idx}/{len(cases)}]: {case['eval_id']}")
        
        # Prepare mock state
        state = {
            "messages": [HumanMessage(content=case["main_claim"])],
            "evaluation_results": case["subclaims"]
        }
        
        try:
            output = aggregator_node(state)
            final_verdict = output["final_verdict"]
        except Exception as e:
            print(f"Error evaluating {case['eval_id']}: {e}")
            continue

        metrics = compute_metrics(final_verdict, case)
        print_claim_report(case, metrics)
        results.append(metrics)

    total_time = time.time() - start_time
    agg_metrics = compute_aggregate_metrics(results)

    print(f"\n{'=' * 70}")
    print("  AGGREGATE METRICS")
    print(f"{'=' * 70}")
    print(f"  Total evaluations:           {agg_metrics.get('total_evaluations', 0)}")
    print(f"  Label accuracy:              {agg_metrics.get('label_accuracy', 0):.2%}")
    for lbl, acc in agg_metrics.get("per_label_accuracy", {}).items():
        print(f"    - {lbl.upper()}: {acc:.2%}")
    print(f"{'=' * 70}")
    
    # Save report
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"aggregator_node_report_{ts}.json"
    
    report_data = {
        "run_timestamp": datetime.now().isoformat(),
        "config": {
            "provider": provider,
            "model_name": model_name,
            "temperature": temperature
        },
        "total_execution_time_s": round(total_time, 2),
        "per_claim_results": results,
        "aggregate_metrics": agg_metrics
    }
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
        
    print(f"Report saved to: {report_path}")

if __name__ == "__main__":
    run_evaluation()
