# Decomposing Team: Top-Down Architecture Report

This report analyzes the **Decomposing Team** subgraph (`src/stages/decomposing_team.py`), which acts as the entry point (ingestion layer) for the MedFactCheck pipeline. Its goal is to take complex, unstructured user claims and distill them into discrete, verifiable medical facts.

## 1. Graph Topology

Unlike the main workflow, the Decomposing Team is a strictly **sequential** pipeline. There is no dynamic routing or conditional logic—every claim flows through the same three steps.

```mermaid
graph TD
    Start((START)) --> Decompose[claim_decomposition]
    Decompose --> Classify[claim_classification]
    Classify --> Filter[claim_filter]
    Filter --> End((END))
```

---

## 2. Node Breakdown & Agent Logic

### A. `claim_decomposition`
- **Agent**: `decomposition_agent` (LLM with `claim_decomposition` schema)
- **Prompt Logic**: Instructs the LLM to extract BOTH factual assertions and subjective opinions, splitting compound sentences into atomic predicates. It forces coreference resolution (replacing pronouns with actual nouns) and conditional propagation (attaching "if X" to all related subclaims).
- **Output**: An array of `predicates`, where each predicate contains a `relation`, `subject`, `object`, and a natural language `search_query`.

### B. `claim_classification`
- **Agent**: `classification_agent` (LLM with `claim_classification` schema)
- **Prompt Logic**: Acts as a strict gatekeeper. It evaluates the `search_query` of each predicate and assigns one of three labels:
  - `verifiable`: Objective assertions related to medicine/biology.
  - `non-verifiable`: Subjective opinions, vague anecdotes, or normative statements.
  - `out-of-domain`: Verifiable facts that are not related to healthcare (e.g., tech, finance, pop culture).
- **Output**: A mapped `predicate_type_dict`.

### C. `claim_filter`
- **Agent**: Pure Python logic (No LLM).
- **Action**: Iterates through the classification dictionary. It discards anything marked `non-verifiable` or `out-of-domain`.
- **Output**: The final array of `verifiable_subclaims` that will be sent back to the Main Graph to trigger the Map-Reduce verification process.

---

## 3. Structural Vulnerabilities & Optimization Ideas

As you plan your refactoring, here are the architectural weak points and opportunities for optimization in this team:

> [!WARNING]
> **Lack of Fallback / Error Handling**
> Currently, if `decomposition_agent` fails to produce valid JSON (e.g., returns `None` for predicates), the code has a placeholder `pass # TO DO` (line 31) and proceeds anyway, which will crash the downstream `claim_classification` node. Implementing a retry loop with LangGraph conditional edges (e.g., `if failed -> loop back to decompose`) is highly recommended.

> [!TIP]
> **Agent Consolidation (Cost & Latency Reduction)**
> Currently, the pipeline makes **two separate LLM calls** in sequence (Decompose, then Classify). This doubles the latency of the ingestion phase. With powerful models like LLaMA-70B or GPT-4o, these two tasks can be merged into a single structured output schema (e.g., the LLM extracts the subclaim AND assigns the `is_verifiable` and `domain` tags in the same JSON object). This would cut ingestion time by 50%.

> [!NOTE]
> **Information Loss on Filter**
> The `claim_filter` node completely drops non-verifiable subclaims. If a user inputs *"My doctor is an idiot and he prescribed me paracetamol for cancer"*, the pipeline drops the first half entirely. While correct for fact-checking, you might want to preserve these dropped subclaims in the state to inform the final UI output (e.g., "We ignored X because it's an opinion, but we checked Y").
