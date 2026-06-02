"""
Aggregator – final verdict node
================================
Runs ONCE after the evaluation stage.  Applies conservative rule-based
aggregation to produce a single final verdict for the original claim.

Logic:
  1. **Refuted-override**: if any subclaim is "refuted" with
     confidence >= threshold → claim is "refuted".
  2. **Weighted majority**: otherwise, sum confidence per label;
     the label with the highest total weight wins.
"""

from langchain_core.messages import HumanMessage

from state import State
from utils.logger import get_logger
from utils.mongo_logger import log_node

log = get_logger("Aggregator")

_REFUTED_CONFIDENCE_THRESHOLD = 0.6


def build_aggregate_node():
    """
    Return the aggregate node function (no LLM needed).

    Usage in main_agent::

        from stages.aggregator import build_aggregate_node
        aggregate_node = build_aggregate_node()
        main_builder.add_node("aggregate", aggregate_node)
    """

    @log_node("aggregation")
    def aggregate_node(state: State):
        evaluation_results = state.get("evaluation_results") or []

        if not evaluation_results:
            log.warning("no evaluation_results to aggregate")
            verdict = {
                "label": "nei",
                "confidence": 0.0,
                "total_subclaims": 0,
                "subclaim_breakdown": [],
            }
            return {"final_verdict": verdict, "messages": [
                HumanMessage(content=str(verdict), name="aggregate_node")
            ]}

        # Build per-subclaim breakdown
        breakdown = [
            {
                "subclaim_id": r.get("subclaim_id", ""),
                "subclaim": r.get("subclaim", ""),
                "label": r.get("label", "nei"),
                "confidence": r.get("confidence", 0.0),
            }
            for r in evaluation_results
        ]

        # 1. Refuted-override: any subclaim refuted with high confidence?
        refuted_entries = [
            e for e in breakdown
            if e["label"] == "refuted" and e["confidence"] >= _REFUTED_CONFIDENCE_THRESHOLD
        ]

        if refuted_entries:
            max_conf = max(e["confidence"] for e in refuted_entries)
            final_label = "refuted"
            final_confidence = max_conf
            log.info(
                f"refuted-override triggered "
                f"({len(refuted_entries)} subclaim(s) refuted with conf >= {_REFUTED_CONFIDENCE_THRESHOLD})"
            )
        else:
            # 2. Weighted majority vote
            weights: dict[str, float] = {}
            counts: dict[str, int] = {}
            for e in breakdown:
                lbl = e["label"]
                weights[lbl] = weights.get(lbl, 0.0) + e["confidence"]
                counts[lbl] = counts.get(lbl, 0) + 1

            final_label = max(weights, key=weights.get)  # type: ignore[arg-type]
            final_confidence = round(weights[final_label] / counts[final_label], 4)
            log.info(
                f"weighted majority -> {final_label} "
                f"(weight={weights[final_label]:.3f}, count={counts[final_label]})"
            )

        verdict = {
            "label": final_label,
            "confidence": round(final_confidence, 4),
            "total_subclaims": len(breakdown),
            "subclaim_breakdown": breakdown,
        }

        # Log a human-readable summary
        log.info("=" * 60)
        log.info("  FINAL VERDICT")
        log.info(f"  Label:      {final_label.upper()}")
        log.info(f"  Confidence: {final_confidence:.4f}")
        log.info(f"  Subclaims:  {len(breakdown)}")
        for entry in breakdown:
            log.info(
                f"    - {entry['subclaim_id']}: "
                f"{entry['label']} (conf={entry['confidence']:.4f})"
            )
        log.info("=" * 60)

        return {
            "final_verdict": verdict,
            "messages": [
                HumanMessage(content=str(verdict), name="aggregate_node")
            ],
        }

    return aggregate_node
