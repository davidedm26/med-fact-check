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
from utils.mongo_logger import log_node
from utils.config import config

log = get_logger("EvaluationTeam")


_veracity_pipeline_cache = None  # module-level cache for the NLI pipeline


def _get_hf_token() -> str | None:
    return os.getenv("HF_TOKEN")


def create_veracity_pipeline(model_name: str = None):
    """
    Factory: create (or return cached) NLI text-classification pipeline.

    Supports two modes controlled by ``config.get("evaluation.mode")``:
    - ``"local"`` (default): loads model weights locally via transformers.
    - ``"api"``: uses HuggingFace Inference API (serverless).

    Parameters
    ----------
    model_name : str, optional
        HuggingFace model identifier. Defaults to env var
        ``VERACITY_MODEL_NAME`` or ``MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli``.

    Returns
    -------
    callable
        A pipeline-like callable that accepts NLI input and returns label scores.
    """
    global _veracity_pipeline_cache
    if _veracity_pipeline_cache is not None:
        return _veracity_pipeline_cache

    resolved = model_name or os.getenv("VERACITY_MODEL_NAME") or config.get("evaluation.veracity_model_name", "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli")
    mode = config.get("evaluation.mode", "local")

    if mode == "api":
        _veracity_pipeline_cache = _create_veracity_api_pipeline(resolved)
    else:
        _veracity_pipeline_cache = _create_veracity_local_pipeline(resolved)

    return _veracity_pipeline_cache


def _create_veracity_local_pipeline(model_name: str):
    """Load NLI model locally via transformers (original behavior)."""
    from transformers import (
        AutoTokenizer,
        AutoModelForSequenceClassification,
        TextClassificationPipeline,
    )

    log.info(f"Loading NLI model locally: {model_name}")
    hf_token = _get_hf_token()
    token_kwargs = {"token": hf_token} if hf_token else {}
    tok = AutoTokenizer.from_pretrained(model_name, **token_kwargs)
    model = AutoModelForSequenceClassification.from_pretrained(model_name, **token_kwargs)
    pipeline = TextClassificationPipeline(
        model=model, tokenizer=tok, top_k=None,  # return scores for all labels
    )
    log.info("NLI model loaded successfully (local)")
    return pipeline


def _create_veracity_api_pipeline(model_name: str):
    """Create an API-based NLI callable using HF Inference API."""
    from huggingface_hub import InferenceClient

    hf_token = _get_hf_token()
    client = InferenceClient(token=hf_token)
    log.info(f"Initialized NLI model via HF Inference API: {model_name}")

    def _api_nli_pipeline(nli_input, **kwargs):
        """
        Callable wrapper that mimics the local TextClassificationPipeline interface.

        Accepts either:
          - dict with "text" and "text_pair" keys (like the local pipeline)
          - a plain string

        Returns a list of dicts: [{"label": "ENTAILMENT", "score": 0.95}, ...]
        """
        import time

        # Build the input text for NLI: premise [SEP] hypothesis
        # PubMedBERT max length is 512 tokens. The API does NOT truncate
        # automatically, so we must do it ourselves.
        _MAX_WORDS = 250  # ~450 tokens with medical subword expansion

        if isinstance(nli_input, dict):
            premise = nli_input.get("text", "")
            hypothesis = nli_input.get("text_pair", "")
            # Reserve ~60 words for hypothesis + special tokens, truncate premise
            hyp_words = hypothesis.split()
            max_premise_words = _MAX_WORDS - len(hyp_words) - 3  # [CLS], [SEP], [SEP]
            premise_words = premise.split()
            if len(premise_words) > max_premise_words:
                premise = " ".join(premise_words[:max_premise_words])
            text = f"{premise} [SEP] {hypothesis}" if hypothesis else premise
        else:
            text = str(nli_input)
            words = text.split()
            if len(words) > _MAX_WORDS:
                text = " ".join(words[:_MAX_WORDS])

        max_retries = 3
        last_exc = None
        for attempt in range(max_retries):
            try:
                results = client.text_classification(text, model=model_name)
                # HF API returns list of TextClassificationOutputElement objects
                # Convert to the same format as the local pipeline: [{"label": ..., "score": ...}]
                formatted = [
                    {"label": r.label, "score": r.score}
                    for r in results
                ]
                return formatted
            except Exception as exc:
                last_exc = exc
                wait = 2 ** attempt
                log.warning(
                    f"API text_classification attempt {attempt + 1}/{max_retries} "
                    f"failed: {exc}. Retrying in {wait}s..."
                )
                time.sleep(wait)

        log.error(f"API text_classification failed after {max_retries} attempts: {last_exc}")
        raise RuntimeError(
            f"API text_classification failed after {max_retries} attempts: {last_exc}"
        )

    return _api_nli_pipeline


def build_evaluation_graph(reasoning_agent):
    """
    Build the evaluation subgraph.

    Parameters
    ----------
    reasoning_agent :
        LLM agent configured with structured output (reasoning_schema).
    """

    # NLI label id → pipeline label string mapping.
    # Common NLI models (including DeBERTa/PubMedBERT) use entailment/neutral/contradiction
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


    @log_node("evaluation")
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
            distilled_evidence = structured.get("distilled_evidence", "")
            key_evidence = structured.get("key_evidence", [])
            reasoning_conclusion = structured.get("reasoning_conclusion", "not_enough_information")
        else:
            justification = getattr(structured, "justification", "")
            distilled_evidence = getattr(structured, "distilled_evidence", "")
            key_evidence = getattr(structured, "key_evidence", [])
            reasoning_conclusion = getattr(structured, "reasoning_conclusion", "not_enough_information")

        return {
            "subclaim_justification": justification,
            "distilled_evidence": distilled_evidence,
            "key_evidence": key_evidence,
            "reasoning_conclusion": reasoning_conclusion,
            "messages": [
                HumanMessage(
                    content=str({
                        "justification": justification,
                        "distilled_evidence": distilled_evidence,
                        "reasoning_conclusion": reasoning_conclusion,
                    }),
                    name="reasoning_agent",
                )
            ],
        }

    @log_node("evaluation")
    def veracity_node(state: State):
        """Run the NLI classifier to assign label + confidence."""
        log.info("veracity_agent start")

        # Collect fields from the previous node's output
        subclaim = state.get("subclaim") or ""
        justification = state.get("subclaim_justification") or ""
        distilled_evidence = state.get("distilled_evidence") or ""
        subclaim_id = state.get("subclaim_id") or ""
        
        reasoning_conclusion = state.get("reasoning_conclusion", "")

        # Consensus logic:
        # 1. If Reasoning Agent concludes there is not enough information, set label to "nei" and confidence to 1.0.
        if reasoning_conclusion == "not_enough_information":
            label = "nei"
            confidence = 1.0
            log.info("Consensus override: LLM concluded not_enough_information. Setting label=nei, confidence=1.0")
        else:
            # NLI premise: use the LLM-purified distilled_evidence (which concentrates
            # the relevant facts and filters noise/overlap). Fall back to justification or raw chunks if empty.
            if distilled_evidence:
                premise = distilled_evidence
            else:
                evidence_text = state.get("evidence_text") or ""
                premise = evidence_text if evidence_text else justification
                
            hypothesis = subclaim
                
            # NLI pipeline input format: dict with text and text_pair for correct tokenizer handling
            nli_input = {"text": premise, "text_pair": hypothesis}

            try:
                nli_results = create_veracity_pipeline()(nli_input, truncation=True, max_length=512)
                log.debug(f"NLI raw output: {nli_results}")

                if isinstance(nli_results, list) and len(nli_results) > 0:
                    if isinstance(nli_results[0], list):
                        nli_results = nli_results[0]
                    
                    # Map labels and scores
                    mapped_results = []
                    for r in nli_results:
                        mapped_label = _NLI_LABEL_MAP.get(r["label"].upper(), "nei")
                        mapped_results.append({"label": mapped_label, "score": r.get("score", 0.0)})
                    
                    # Force choice between supported and refuted since reasoning says there is enough info
                    filtered_results = [r for r in mapped_results if r["label"] in ("supported", "refuted")]
                    if filtered_results:
                        # The LLM's reasoning conclusion becomes the final label
                        label = reasoning_conclusion
                        log.info(f"Consensus: LLM label choice is '{label}'. Invoking NLI for confidence score.")
                        
                        # Extract NLI score for the LLM's chosen label
                        llm_label_score = next((r["score"] for r in filtered_results if r["label"] == label), 0.0)
                        
                        # Normalize confidence over supported + refuted
                        total_score = sum(r["score"] for r in filtered_results)
                        confidence = round(llm_label_score / total_score if total_score > 0 else llm_label_score, 4)
                    else:
                        label = "nei"
                        confidence = 0.0
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
            "reasoning_conclusion": reasoning_conclusion,
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
