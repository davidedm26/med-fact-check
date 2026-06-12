# MedFactCheck: Future Works & Optimizations

This document tracks potential architectural improvements, optimizations, and advanced features planned for the future evolution of the MedFactCheck pipeline.

## 1. Advanced Fallback & Retry Strategies

### Dynamic Retry Loop with Temperature Variation
Currently, the pipeline employs a "soft fallback" when an LLM fails to output valid structured data (e.g., in the `claim_decomposition` node). While this guarantees pipeline continuity, a more robust approach would be to implement an active retry loop using LangGraph conditional edges.
- **Mechanism**: If an LLM returns `None` or invalid JSON, route back to the same node up to a maximum of `N` times.
- **Enhancement**: At each retry iteration, dynamically increase the LLM's `temperature` parameter (or switch to a more capable/expensive fallback model). This breaks deterministic failure loops and encourages the model to generate a valid, structurally different response.
- **State Impact**: Implementing this safely requires adding a `retry_count` integer variable (using `operator.add` as reducer) to the global `State` (`src/state.py`) to prevent infinite recursive loops.

## 2. Agent Consolidation

### Merging Decompose and Classify Nodes
Currently, the ingestion phase makes two separate, sequential LLM calls: one to decompose the claim into predicates, and a second to classify them (Verifiable, Non-verifiable, Out-of-domain). This separation of concerns is a deliberate architectural choice necessary for our current use of smaller open-weight models (<10B parameters), which typically struggle with multi-task complexity in a single JSON schema.
- **Optimization**: When migrating to more powerful modern LLMs (e.g., LLaMA-70B, GPT-4o), these tasks can be merged into a single structured output schema. The LLM could extract the subclaims AND assign the domain/verifiability tags simultaneously in a single JSON payload. This would reduce the latency of the ingestion phase by nearly 50% and reduce overall token costs.

## 3. Retrieval Optimization

### Local Knowledge Base (Hybrid Live+Offline Retrieval)
Currently, all retrieval relies entirely on live external APIs (PubMed, Clinical Trials, etc.). While robust, this adds significant network latency to the pipeline.
- **Optimization**: Maintain a curated, offline local knowledge base containing highly reliable medical literature and systematic reviews. The retrieval architecture would evolve into a true hybrid system: querying the offline vector database first for guaranteed, zero-latency evidence, and falling back to "live" external API fetching only when the local knowledge base lacks sufficient coverage for novel or highly specific subclaims.

## 4. Aggregator Optimization

### Early Exit (Short-Circuit) Aggregation
Currently, if a user submits a claim that decomposes into 10 subclaims, the system waits for all 10 to be fully retrieved and evaluated before making a final decision.
- **Optimization**: Implement a "short-circuit" mechanism. If subclaim #1 finishes early and is evaluated as unequivocally `refuted` (e.g., with >95% confidence), a signal could be broadcasted to instantly halt the other 9 parallel executions and trigger the aggregator early. Since a single fundamentally false premise often invalidates the entire overarching claim, this would save massive amounts of API tokens and execution time.

---
*Future ideas and optimizations will be tracked here.*
