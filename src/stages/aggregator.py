"""
Aggregator – final verdict node
================================
Runs ONCE after the evaluation stage. Uses an LLM to logically aggregate
evaluated subclaims into a single final verdict for the original claim.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from state import State, _message_text
from utils.logger import get_logger
from utils.mongo_logger import log_node
from prompts.aggregate import aggregator_prompt

log = get_logger("Aggregator")


def build_aggregate_node(aggregator_agent):
    """
    Return the aggregate node function.

    Usage in main_agent::

        from stages.aggregator import build_aggregate_node
        aggregate_node = build_aggregate_node(self.aggregator_agent)
        main_builder.add_node("aggregate", aggregate_node)
    """

    @log_node("aggregation")
    def aggregate_node(state: State):
        evaluation_results = state.get("evaluation_results") or []
        main_claim = _message_text(state["messages"][0])

        if not evaluation_results:
            log.warning("no evaluation_results to aggregate")
            verdict = {
                "logical_relationship": "none",
                "aggregation_analysis": "No evaluations available to aggregate.",
                "label": "not_enough_information",
                "confidence": 0.0,
                "justification": "No subclaims were evaluated, preventing aggregation.",
                "total_subclaims": 0,
                "subclaim_breakdown": [],
            }
            return {"final_verdict": verdict, "messages": [
                HumanMessage(content=str(verdict), name="aggregate_node")
            ]}

        # Build per-subclaim breakdown for logging/state and prompt injection
        breakdown = [
            {
                "subclaim_id": r.get("subclaim_id", ""),
                "subclaim": r.get("subclaim", ""),
                "label": r.get("label", "nei"),
                "confidence": r.get("confidence", 0.0),
                "justification": r.get("justification", ""),
            }
            for r in evaluation_results
        ]

        # Format input for the Aggregator LLM
        subclaims_text = ""
        for i, b in enumerate(breakdown, 1):
            subclaims_text += f"{i}. Subclaim: {b['subclaim']}\n"
            subclaims_text += f"   Label: {b['label']} (Confidence: {b['confidence']:.2f})\n"
            subclaims_text += f"   Justification: {b['justification']}\n\n"

        user_content = (
            f"## Original Claim\n{main_claim}\n\n"
            f"## Evaluated Subclaims\n{subclaims_text}"
        )

        messages = [
            SystemMessage(content=aggregator_prompt),
            HumanMessage(content=user_content)
        ]

        log.info("aggregator_agent start")
        try:
            structured = aggregator_agent.invoke(messages)
            log.info("aggregator_agent response received")
            
            if isinstance(structured, dict):
                logical_relationship = structured.get("logical_relationship", "")
                aggregation_analysis = structured.get("aggregation_analysis", "")
                label = structured.get("label", "nei")
                justification = structured.get("justification", "")
                try:
                    confidence = float(structured.get("confidence", 0.0))
                except (ValueError, TypeError):
                    confidence = 0.0
            else:
                logical_relationship = getattr(structured, "logical_relationship", "")
                aggregation_analysis = getattr(structured, "aggregation_analysis", "")
                label = getattr(structured, "label", "nei")
                justification = getattr(structured, "justification", "")
                try:
                    confidence = float(getattr(structured, "confidence", 0.0))
                except (ValueError, TypeError):
                    confidence = 0.0
                    
        except Exception as exc:
            log.error(f"Aggregator Agent error: {exc}")
            logical_relationship = "error"
            aggregation_analysis = f"Error: {exc}"
            label = "not_enough_information"
            confidence = 0.0
            justification = "An error occurred during final aggregation."

        verdict = {
            "logical_relationship": logical_relationship,
            "aggregation_analysis": aggregation_analysis,
            "label": label,
            "confidence": round(confidence, 4),
            "justification": justification,
            "total_subclaims": len(breakdown),
            "subclaim_breakdown": breakdown,
        }

        # Log a human-readable summary
        log.info("=" * 60)
        log.info("  FINAL VERDICT (LLM Aggregation)")
        log.info(f"  Logic:      {logical_relationship}")
        log.info(f"  Label:      {label.upper()}")
        log.info(f"  Confidence: {confidence:.4f}")
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
