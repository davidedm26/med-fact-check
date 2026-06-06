"""
Ablation Test -- Evaluation Nodes
================================
Tests the Evaluation Team subgraph (extractor + veracity) against a gold set.
Evaluates: Label accuracy and confidence.
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
from prompts.evaluate import reasoning_schema, veracity_schema
# pyrefly: ignore [missing-import]
from stages.evaluation_team import build_evaluation_graph
from langchain_core.messages import HumanMessage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GOLD_SET_PATH = _PROJECT_ROOT / "test" / "data" / "evaluation_gold.json"
REPORTS_DIR = _PROJECT_ROOT / "test" / "reports"

def _format_evidence_text(chunks: list[dict]) -> str:
    if not chunks:
        return "(No evidence chunks available.)"
        
    evidence_lines = []
    for idx, chunk in enumerate(chunks, 1):
        if isinstance(chunk, dict):
            text = chunk.get("text") or chunk.get("content") or json.dumps(chunk)
            source = chunk.get("source") or chunk.get("id") or "unknown"
            score = chunk.get("score", "")
            evidence_lines.append(f"[Chunk {idx} | source={source} | score={score}]\n{text}")
        else:
            evidence_lines.append(f"[Chunk {idx}]\n{str(chunk)}")
    return "\n\n".join(evidence_lines)

def compute_metrics(
    eval_result: dict[str, Any], 
    gold_entry: dict[str, Any],
) -> dict[str, Any]:
    expected_label = gold_entry["expected_label"].lower()
    
    pred_label = eval_result.get("label", "nei").lower()
    if pred_label == "not_enough_information":
        pred_label = "nei"
        
    confidence = float(eval_result.get("confidence", 0.0))
    label_correct = (pred_label == expected_label)
    
    return {
        "eval_id": gold_entry["eval_id"],
        "subclaim": gold_entry["subclaim"],
        "expected_label": expected_label,
        "predicted_label": pred_label,
        "confidence": confidence,
        "label_correct": label_correct,
        "justification": eval_result.get("justification", ""),
        "key_evidence": eval_result.get("key_evidence", [])
    }

def print_claim_report(gold_entry: dict, metrics: dict) -> None:
    print(f"\n{'-' * 70}")
    print(f"  Eval ID:  {gold_entry['eval_id']}")
    print(f"  Subclaim: {gold_entry['subclaim'][:90]}...")
    print(f"{'-' * 70}")
    print(f"  Label:    expected={metrics['expected_label'].upper()}  "
          f"predicted={metrics['predicted_label'].upper()}  "
          f"{'OK' if metrics['label_correct'] else 'FAIL'} (conf={metrics['confidence']:.2f})")

def compute_aggregate_metrics(results: list[dict]) -> dict[str, Any]:
    n = len(results)
    if n == 0:
        return {}

    def _avg(key: str) -> float:
        return round(sum(r[key] for r in results) / n, 4)

    def _rate(key: str) -> float:
        return round(sum(1 for r in results if r[key]) / n, 4)
        
    correct_results = [r for r in results if r["label_correct"]]
    incorrect_results = [r for r in results if not r["label_correct"]]
    
    avg_conf_correct = sum(r["confidence"] for r in correct_results) / len(correct_results) if correct_results else 0.0
    avg_conf_incorrect = sum(r["confidence"] for r in incorrect_results) / len(incorrect_results) if incorrect_results else 0.0
    
    # Per-label accuracy
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
        "avg_confidence_correct": round(avg_conf_correct, 4),
        "avg_confidence_incorrect": round(avg_conf_incorrect, 4),
        "per_label_accuracy": per_label
    }

def print_aggregate_report(agg: dict) -> None:
    print(f"\n{'=' * 70}")
    print("  AGGREGATE METRICS")
    print(f"{'=' * 70}")
    print(f"  Total evaluations:           {agg.get('total_evaluations', 0)}")
    print(f"  Label accuracy:              {agg.get('label_accuracy', 0):.2%}")
    print(f"  Avg confidence (correct):    {agg.get('avg_confidence_correct', 0):.2f}")
    print(f"  Avg confidence (incorrect):  {agg.get('avg_confidence_incorrect', 0):.2f}")
    
    print("\n  Per-label accuracy:")
    for label, acc in agg.get("per_label_accuracy", {}).items():
        print(f"    - {label.ljust(10)} {acc:.2%}")
    print(f"{'=' * 70}")

def main() -> None:
    print("\n" + "=" * 66)
    print("           ABLATION TEST -- EVALUATION NODES")
    print("=" * 66 + "\n")

    if not GOLD_SET_PATH.exists():
        print(f"ERROR: Gold set not found at {GOLD_SET_PATH}")
        sys.exit(1)

    with open(GOLD_SET_PATH, "r", encoding="utf-8") as f:
        gold_data = json.load(f)

    gold_evaluations = gold_data.get("gold_evaluations", [])
    print(f"Loaded {len(gold_evaluations)} evaluations from gold set\n")

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

    reasoning_agent = base_llm.with_structured_output(
        reasoning_schema, method="function_calling"
    )
    veracity_agent = base_llm.with_structured_output(
        veracity_schema, method="function_calling"
    )
    
    evaluation_graph = build_evaluation_graph(reasoning_agent, veracity_agent)

    all_results: list[dict] = []
    total_time = 0.0

    for idx, gold_entry in enumerate(gold_evaluations, 1):
        subclaim = gold_entry["subclaim"]
        eval_id = gold_entry["eval_id"]
        evidence_chunks = gold_entry.get("evidence_chunks", [])
        
        evidence_text = _format_evidence_text(evidence_chunks)

        print(f"\n[{idx}/{len(gold_evaluations)}] Testing: {eval_id}")

        t0 = time.time()
        
        try:
            response = evaluation_graph.invoke({
                "subclaim_id": eval_id,
                "subclaim": subclaim,
                "evidence_text": evidence_text,
                "messages": [HumanMessage(content=subclaim, name="evaluation_input")],
                "run_id": "test_run"
            })
            
            evaluation_results = response.get("evaluation_results", [])
            if evaluation_results:
                result = evaluation_results[0]
            else:
                result = {"label": "error", "confidence": 0.0, "justification": "No result returned"}
                
        except Exception as exc:
            print(f"  ERROR invoking graph: {exc}")
            result = {"label": "error", "confidence": 0.0, "justification": str(exc)}

        elapsed = time.time() - t0
        total_time += elapsed
        print(f"  Completed in {elapsed:.1f}s")

        metrics = compute_metrics(result, gold_entry)
        all_results.append(metrics)
        print_claim_report(gold_entry, metrics)

    aggregate = compute_aggregate_metrics(all_results)
    print_aggregate_report(aggregate)
    print(f"\nTotal execution time: {total_time:.1f}s")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"evaluation_nodes_report_{timestamp}.json"

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
