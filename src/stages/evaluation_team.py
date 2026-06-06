"""
Evaluation Team – subgraph
==========================
Two-step evaluation for each subclaim using dual LLMs:
  1. **Reasoning Agent** (LLM)  → extracts clean facts and verbatim quotes from noisy chunks.
  2. **Veracity Agent** (LLM)   → evaluates the distilled evidence logically and outputs label + confidence.

The graph is invoked once per subclaim from the main workflow.
"""

import json

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, SystemMessage

from state import State
from prompts.evaluate import reasoning_prompt, reasoning_schema, veracity_prompt, veracity_schema
from utils.logger import get_logger
from utils.mongo_logger import log_node
from utils.config import config

log = get_logger("EvaluationTeam")


def build_evaluation_graph(reasoning_agent, veracity_agent):
    """
    Build the evaluation subgraph.

    Parameters
    ----------
    reasoning_agent :
        LLM agent configured with structured output (reasoning_schema).
    veracity_agent :
        LLM agent configured with structured output (veracity_schema).
    """

    def _format_evidence_for_prompt(subclaim_result: dict) -> str:
        """Combine sparse + dense chunks into a numbered list for the LLM."""
        chunks = (
            subclaim_result.get("sparse_top_k_chunks") or []
        ) + (
            subclaim_result.get("dense_top_k_chunks") or []
        )
        if not chunks:
            return "(No evidence chunks available.)"

        # Build a numbered list of evidence chunks
        lines = []
        for idx, chunk in enumerate(chunks, 1): 
            if isinstance(chunk, dict):
                text = chunk.get("text") or chunk.get("content") or json.dumps(chunk)
                source = chunk.get("source") or chunk.get("id") or "unknown"
                score = chunk.get("score", "")
                lines.append(f"[Chunk {idx} | source={source} | score={score}]\n{text}")
            else:
                lines.append(f"[Chunk {idx}]\n{str(chunk)}")
        return "\n\n".join(lines)


    @log_node("evaluation")
    def reasoning_node(state: State):
        """Invoke the Reasoning Agent to produce clean evidence and a reasoning scratchpad."""
        log.info("reasoning_agent start")

        subclaim = state.get("subclaim") or ""
        evidence_text = state.get("evidence_text") or ""

        # User prompt
        user_content = (
            f"## Subclaim\n{subclaim}\n\n"  
            f"## Evidence Chunks\n{evidence_text}"
        )

        # Call the reasoning agent with the user prompt
        messages = [
            SystemMessage(content=reasoning_prompt),
            HumanMessage(content=user_content),
        ]
        structured = reasoning_agent.invoke(messages)
        log.info("reasoning_agent response received")

        # Extract fields (handle both dict and object response formats)
        if isinstance(structured, dict):
            reasoning_chain = structured.get("reasoning", "")
            supporting_quotes = structured.get("supporting_quotes", [])
            refuting_quotes = structured.get("refuting_quotes", [])
            distilled_evidence = structured.get("distilled_evidence", "")
            evidence_verdict_hint = structured.get("evidence_verdict_hint", "")
        else:
            reasoning_chain = getattr(structured, "reasoning", "")
            supporting_quotes = getattr(structured, "supporting_quotes", [])
            refuting_quotes = getattr(structured, "refuting_quotes", [])
            distilled_evidence = getattr(structured, "distilled_evidence", "")
            evidence_verdict_hint = getattr(structured, "evidence_verdict_hint", "")

        return {
            "distilled_evidence": distilled_evidence,
            "supporting_quotes": supporting_quotes,
            "refuting_quotes": refuting_quotes,
            "evidence_verdict_hint": evidence_verdict_hint,
            "messages": [
                HumanMessage(
                    content=str({
                        "reasoning": reasoning_chain,
                        "supporting_quotes": supporting_quotes,
                        "refuting_quotes": refuting_quotes,
                        "distilled_evidence": distilled_evidence,
                        "evidence_verdict_hint": evidence_verdict_hint,
                    }),
                    name="reasoning_agent",
                )
            ],
        }

    @log_node("evaluation")
    def veracity_node(state: State):
        """Invoke the Veracity (Judge) Agent to produce final label, confidence, and justification."""
        log.info("veracity_agent start")

        subclaim = state.get("subclaim") or ""
        distilled_evidence = state.get("distilled_evidence") or ""
        evidence_verdict_hint = state.get("evidence_verdict_hint") or ""
        subclaim_id = state.get("subclaim_id") or ""

        # User prompt for the Judge — includes the verdict hint from the Reasoning Agent
        user_content = (
            f"## Subclaim\n{subclaim}\n\n"
            f"## Distilled Evidence\n{distilled_evidence}\n\n"
            f"## Evidence Verdict Hint\n{evidence_verdict_hint}"
        )

        messages = [
            SystemMessage(content=veracity_prompt),
            HumanMessage(content=user_content),
        ]

        try:
            structured = veracity_agent.invoke(messages)
            log.info("veracity_agent response received")
            
            if isinstance(structured, dict):
                logical_analysis = structured.get("logical_analysis", "")
                label = structured.get("label", "nei")
                justification = structured.get("justification", "")
                try:
                    confidence = float(structured.get("confidence", 0.0))
                except (ValueError, TypeError):
                    confidence = 0.0
            else:
                logical_analysis = getattr(structured, "logical_analysis", "")
                label = getattr(structured, "label", "nei")
                justification = getattr(structured, "justification", "")
                try:
                    confidence = float(getattr(structured, "confidence", 0.0))
                except (ValueError, TypeError):
                    confidence = 0.0
                    
        except Exception as exc:
            log.error(f"Veracity Agent error: {exc}")
            logical_analysis = f"Error: {exc}"
            label = "nei"
            confidence = 0.0
            justification = "An error occurred during verification."

        log.info(f"label={label}, confidence={confidence}")

        evaluation_entry = {
            "subclaim_id": subclaim_id,
            "subclaim": subclaim,
            "justification": justification,
            "supporting_quotes": state.get("supporting_quotes", []),
            "refuting_quotes": state.get("refuting_quotes", []),
            "label": label,
            "confidence": confidence,
        }

        return {
            "evaluation_results": [evaluation_entry],
            "messages": [
                HumanMessage(
                    content=str({
                        "subclaim_id": subclaim_id,
                        "logical_analysis": logical_analysis,
                        "justification": justification,
                        "label": label,
                        "confidence": confidence,
                    }),
                    name="veracity_agent",
                )
            ],
        }

    # ── graph assembly ─────────────────────────────────────────────────── #

    builder = StateGraph(State)
    builder.add_node("reasoning", reasoning_node)
    builder.add_node("veracity", veracity_node)

    builder.add_edge(START, "reasoning")
    builder.add_edge("reasoning", "veracity")
    builder.add_edge("veracity", END)

    return builder.compile()
