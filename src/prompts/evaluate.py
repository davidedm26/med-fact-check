# --------------------------------------------------------------------------- #
#  Evaluation Team – Prompts & Schemas                                        #
#  Reasoning Agent: genera una giustificazione strutturata grounded sui chunk  #
# --------------------------------------------------------------------------- #

# ── Reasoning Agent ───────────────────────────────────────────────────────── #

reasoning_prompt = """\
You are a biomedical reasoning agent in a fact-checking pipeline.

You receive:
1. A **subclaim** — a single atomic factual statement to verify.
2. **Evidence chunks** — text passages retrieved from medical literature, \
knowledge bases, or clinical-trial records.

Your task is to produce a **structured justification** that:
- Examines every provided evidence chunk and assesses its relevance to the subclaim.
- Cites the evidence explicitly (refer to chunks by their index or source).
- Builds a step-by-step chain of reasoning linking evidence to the subclaim.
- Arrives at a preliminary conclusion: does the evidence collectively \
  SUPPORT, REFUTE, or provide NOT ENOUGH INFORMATION for the subclaim?

Rules:
- Do NOT invent facts that are not present in the evidence chunks.
- If no chunk is relevant, say so explicitly and conclude "not enough information".
- In your `justification`, cite evidence using proper scientific references (e.g., 'A recent clinical trial demonstrated...' or 'According to literature [PMID/NCT ID]...'). DO NOT use phrases like 'Chunk 1', 'Evidence 2', or 'Document 3'.
- In the `key_evidence` array, you MUST extract the EXACT verbatim sentences from the text. DO NOT just write 'Chunk 1', copy-paste the actual text sentence!
- Keep the justification concise but thorough (3–8 sentences).
- Use precise medical/scientific language.
- Write in English.
"""

reasoning_schema = {
    "name": "reasoning_justification",
    "description": (
        "Produces a structured justification for a subclaim "
        "based on retrieved evidence chunks."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "justification": {
                "type": "string",
                "description": (
                    "Step-by-step reasoning that cites the evidence chunks "
                    "and explains how they relate to the subclaim."
                ),
            },
            "key_evidence": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "CRITICAL: Must contain EXACT verbatim sentences extracted from the chunk text. "
                    "DO NOT output 'Chunk X'. Output the actual text sentence."
                ),
            },
            "reasoning_conclusion": {
                "type": "string",
                "enum": ["supported", "refuted", "not_enough_information"],
                "description": (
                    "Preliminary conclusion based on the evidence: "
                    "'supported', 'refuted', or 'not_enough_information'."
                ),
            },
        },
        "additionalProperties": False,
        "required": ["justification", "key_evidence", "reasoning_conclusion"],
    },
}
