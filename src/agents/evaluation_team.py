"""
Evaluation Team – subgraph
==========================
Two-step evaluation for each subclaim:
  1. **Reasoning Agent** (LLM)  → structured justification grounded on chunks
  2. **Veracity Agent**  (PubMedBERT NLI) → label + confidence

The graph is invoked once per subclaim from the main workflow
(the main graph iterates over `subclaim_results` in batch).
"""

import json
import os

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, SystemMessage

from state import State, _message_text
from prompts.evaluate import reasoning_prompt, reasoning_schema
from utils.logger import get_logger
from utils.config import config

log = get_logger("EvaluationTeam")


_veracity_pipeline_cache = None  # module-level cache for the NLI pipeline


def _get_hf_token() -> str | None:
    return os.getenv("HF_TOKEN")


def create_veracity_pipeline(model_name: str = None):
    """
    Factory: create (or return cached) PubMedBERT NLI text-classification pipeline.

    Parameters
    ----------
    model_name : str, optional
        HuggingFace model identifier. Defaults to env var
        ``VERACITY_MODEL_NAME`` or ``pritamdeka/PubMedBERT-MNLI-MedNLI``.

    Returns
    -------
    TextClassificationPipeline
    """
    global _veracity_pipeline_cache
    if _veracity_pipeline_cache is not None:
        return _veracity_pipeline_cache

    from transformers import (
        AutoTokenizer,
        AutoModelForSequenceClassification,
        TextClassificationPipeline,
    )

    resolved = model_name or os.getenv("VERACITY_MODEL_NAME") or config.get("evaluation.veracity_model_name", "pritamdeka/PubMedBERT-MNLI-MedNLI")
    log.info(f"Loading NLI model: {resolved}")
    hf_token = _get_hf_token()
    token_kwargs = {"token": hf_token} if hf_token else {}
    tok = AutoTokenizer.from_pretrained(resolved, **token_kwargs)
    model = AutoModelForSequenceClassification.from_pretrained(resolved, **token_kwargs)
    _veracity_pipeline_cache = TextClassificationPipeline(
        model=model, tokenizer=tok, top_k=None,  # return scores for all labels
    )
    log.info("NLI model loaded successfully")
    return _veracity_pipeline_cache


def build_evaluation_graph(reasoning_agent):
    """
    Build the evaluation subgraph.

    Parameters
    ----------
    reasoning_agent :
        LLM agent configured with structured output (reasoning_schema).
    """

    # NLI label id → pipeline label string mapping.
    # PubMedBERT-MNLI-MedNLI uses: 0=entailment, 1=neutral, 2=contradiction
    _NLI_LABEL_MAP = {
        "ENTAILMENT": "supported",
        "NEUTRAL": "nei",
        "CONTRADICTION": "refuted",
        # Some models use numeric labels
        "LABEL_0": "supported",   # entailment
        "LABEL_1": "nei",         # neutral
        "LABEL_2": "refuted",     # contradiction
    }

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


    def reasoning_node(state: State):
        """Invoke the Reasoning Agent to produce a structured justification."""
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
            justification = structured.get("justification", "")
            key_evidence = structured.get("key_evidence", [])
            reasoning_conclusion = structured.get("reasoning_conclusion", "not_enough_information")
        else:
            justification = getattr(structured, "justification", "")
            key_evidence = getattr(structured, "key_evidence", [])
            reasoning_conclusion = getattr(structured, "reasoning_conclusion", "not_enough_information")

        return {
            "subclaim_justification": justification,
            "key_evidence": key_evidence,
            "reasoning_conclusion": reasoning_conclusion,
            "messages": [
                HumanMessage(
                    content=str({
                        "justification": justification,
                        "reasoning_conclusion": reasoning_conclusion,
                    }),
                    name="reasoning_agent",
                )
            ],
        }

    def veracity_node(state: State):
        """Run the PubMedBERT NLI classifier to assign label + confidence."""
        log.info("veracity_agent start")

        # Collect fields from the previous node's output
        subclaim = state.get("subclaim") or ""
        justification = state.get("subclaim_justification") or ""
        subclaim_id = state.get("subclaim_id") or ""

        # Build premise (justification) and hypothesis (subclaim)
        premise = justification if justification else "(No justification available.)"
        hypothesis = subclaim

        # NLI pipeline input format: "premise </s></s> hypothesis"
        nli_input = f"{premise} </s></s> {hypothesis}"

        try:
            nli_results = create_veracity_pipeline()(nli_input, truncation=True, max_length=512)
            log.debug(f"NLI raw output: {nli_results}")

            # nli_results is a list of dicts: [{"label": "ENTAILMENT", "score": 0.87}, ...]
            # Pick the top prediction
            if isinstance(nli_results, list) and len(nli_results) > 0:
                # Handle both single-label (top_k=1) and multi-label outputs
                if isinstance(nli_results[0], list):
                    # Some pipelines return [[{...}, {...}, ...]]
                    nli_results = nli_results[0]
                
                top = max(nli_results, key=lambda x: x.get("score", 0))
                raw_label = top.get("label", "NEUTRAL").upper()
                confidence = round(top.get("score", 0.0), 4)
                label = _NLI_LABEL_MAP.get(raw_label, "nei")
            else:
                label = "nei"
                confidence = 0.0

        except Exception as exc:
            log.error(f"NLI error: {exc}")
            label = "nei"
            confidence = 0.0

        log.info(f"label={label}, confidence={confidence}")

        evaluation_entry = {
            "subclaim_id": subclaim_id,
            "subclaim": subclaim,
            "justification": justification,
            "key_evidence": state.get("key_evidence", []),
            "reasoning_conclusion": state.get("reasoning_conclusion", ""),
            "label": label,
            "confidence": confidence,
        }

        return {
            "evaluation_results": [evaluation_entry],
            "messages": [
                HumanMessage(
                    content=str({
                        "subclaim_id": subclaim_id,
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
