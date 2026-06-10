"""
Evaluation Team – subgraph
==========================
Two-step evaluation for each subclaim using dual LLMs:
  1. **Reasoning Agent** (LLM)  → extracts clean facts and verbatim quotes from noisy chunks.
  2. **Veracity Agent** (LLM)   → evaluates the distilled evidence logically and outputs label + confidence.

The graph is invoked once per subclaim from the main workflow.
"""

import json
import os
import time

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, SystemMessage
from huggingface_hub import InferenceClient

from state import State
from prompts.evaluate import reasoning_prompt, reasoning_schema, veracity_prompt, veracity_schema
from utils.logger import get_logger
from utils.mongo_logger import log_node
from utils.config import config

log = get_logger("EvaluationTeam")


import re

def clean_chunk_references(text: str) -> str:
    if not text:
        return ""
    
    def repl_numbered(match):
        orig = match.group(0)
        if orig and orig[0].isupper():
            return "The clinical evidence"
        return "the clinical evidence"

    pattern_numbered = re.compile(
        r'\b[Cc]hunks?\b\s*\[?\d+\]?(?:\s*(?:and|or|,)\s*\[?\d+\]?)*'
    )
    text = pattern_numbered.sub(repl_numbered, text)
    
    pattern_passages = re.compile(
        r'\b(?:[Pp]assages?|[Rr]eferences?)\b\s*\[?\d+\]?(?:\s*(?:and|or|,)\s*\[?\d+\]?)*'
    )
    text = pattern_passages.sub(repl_numbered, text)
    
    text = re.sub(r'\bevidence\s+(?:chunks?|passages?)\b', 'evidence sources', text, flags=re.IGNORECASE)
    text = re.sub(r'\b[Cc]hunks?\b', 'studies', text, flags=re.IGNORECASE)
    text = re.sub(r'\b[Pp]assages?\b', 'studies', text, flags=re.IGNORECASE)
    
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


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
        subclaim_id = state.get("subclaim_id") or ""
        # Build Mega-Premise using Reasoning Agent outputs
        justification_text = ""
        distilled_evidence_text = ""
        for msg in state.get("messages", []):
            if getattr(msg, "name", "") == "reasoning_agent":
                try:
                    content_dict = eval(msg.content)
                    justification_text = content_dict.get("reasoning", "")
                    distilled_evidence_text = content_dict.get("distilled_evidence", "")
                except Exception:
                    justification_text = msg.content
                    distilled_evidence_text = msg.content
                    
        supporting_quotes = state.get("supporting_quotes", [])
        refuting_quotes = state.get("refuting_quotes", [])
        
        # DeBERTa v3 large has a context limit. The HF API will error if inputs are too long.
        def safe_truncate(text: str, max_chars: int = 600) -> str:
            if not text: return ""
            return text[:max_chars] + "..." if len(text) > max_chars else text
            
        just_str = safe_truncate(justification_text, 600)
        distilled_str = safe_truncate(distilled_evidence_text or distilled_evidence, 600)
        supp_str = safe_truncate(" ".join(supporting_quotes), 600)
        ref_str = safe_truncate(" ".join(refuting_quotes), 600)
        
        # Extract hint from reasoning node output for predicted label
        hint = ""
        for msg in state.get("messages", []):
            if getattr(msg, "name", "") == "reasoning_agent":
                try:
                    content_dict = eval(msg.content)
                    hint = content_dict.get("evidence_verdict_hint", "")
                except Exception:
                    pass

        # Prepare variables for zero-shot classification
        # Combine supporting and refuting quotes if evidence_text is not directly in state
        sentences = safe_truncate(state.get("evidence_text", " ".join(supporting_quotes + refuting_quotes)), 1000)
        justifications = distilled_str
        
        # Premise is the evidence/justification context
        premise = f"Justification: {justifications}\nEvidence: {sentences}"
        premise = safe_truncate(premise, 1000)

        # Hypothesis template evaluates the subclaim
        claim_escaped = subclaim.replace("{", "[").replace("}", "]")
        hypothesis_template = f"The claim that '{claim_escaped}' is {{}}."
        
        # HF Transformers pipeline using Hugging Face Hub InferenceClient
        label = "nei"
        confidence = 0.0
        logical_analysis = clean_chunk_references(premise)
        justification = clean_chunk_references(distilled_evidence_text or distilled_evidence)

        try:
            model_name = config.get("evaluation", {}).get("veracity_model_name", "MoritzLaurer/deberta-v3-large-zeroshot-v1.1-all-33")
            hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_KEY", "")
            
            # Initialize client
            client = InferenceClient(model=model_name, token=hf_token)
            
            candidate_labels = ["supported", "refuted", "inconclusive"]
            
            log.info(f"Running zero-shot classification via InferenceClient...")
            
            result = client.zero_shot_classification(
                text=premise,
                candidate_labels=candidate_labels,
                hypothesis_template=hypothesis_template,
                multi_label=False
            )
            
            # The result is a list of dicts: [{'label': 'supported', 'score': 0.9}, ...]
            if isinstance(result, list) and len(result) > 0:
                best_label = result[0].get("label", "")
                confidence = float(result[0].get("score", 0.0))
                
                if best_label == "supported":
                    label = "supported"
                elif best_label == "refuted":
                    label = "refuted"
                else:
                    label = "nei"
            else:
                log.warning(f"Unexpected InferenceClient response format: {result}")
                
        except Exception as exc:
            log.error(f"Veracity Agent Pipeline error: {exc}")
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
