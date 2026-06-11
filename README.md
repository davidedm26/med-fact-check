# 🧬 MedFactCheck

**Multi-Agent AI System for Biomedical Claim Verification**

> Big Data Engineering Course — a.a. 2025-26  
> Università degli Studi di Napoli Federico II  
> Prof. Vincenzo Moscato  
> Authors: Vittoria Alberto, Davide Di Matteo, Carmine Bellotti

---

## Overview

MedFactCheck is an end-to-end multi-agent pipeline for automated biomedical fact-checking. It accepts free-text medical claims (from social media, news articles, or clinical web pages) and returns a structured verdict — **Supported**, **Refuted**, or **Not Enough Information (NEI)** — with a confidence score and traceable evidence grounded in peer-reviewed literature.

The system is orchestrated via **LangGraph** and is built around two core novelties:

1. **Extended evidence corpus** — goes beyond PubMed abstracts to include full-text articles (Europe PMC), structured biological knowledge (UniProt), and aggregated systematic reviews (PubMed Meta-Analyses).
2. **Multi-agent architecture** — specialized agents handle distinct subtasks (decomposition, retrieval, reasoning, verdict aggregation) rather than delegating everything to a single monolithic model.

---

## Architecture

The pipeline is modelled as a stateful directed graph (Super-Graph) with four logical phases:

```
Raw Claim
   │
   ▼
Phase 1 — Decomposition Subgraph
   ├── Decomposer LLM     → atomic predicates
   ├── Classification LLM → verifiable / non-verifiable / out-of-domain
   └── Claim Filter       → list of N verifiable medical sub-claims
   │
   ▼ (fan-out: N parallel branches)
Phase 2 — Retrieval (per sub-claim)
   ├── Source Selector LLM  → budget allocation across Europe PMC / UniProt / PubMed
   ├── Downloader Agent     → fetches full-text documents via REST APIs
   └── Hybrid Retriever
       ├── Sparse (BM25)
       ├── Dense (MedCPT Bi-Encoder)
       └── Cross-Encoder Reranker (MedCPT-Cross-Encoder) → Top-K chunks
   │
   ▼
Phase 3 — Reasoning & Veracity Assessment (per sub-claim)
   ├── Reasoning Agent      → evidence distillation, entity mapping, verbatim quotes
   └── Veracity Agent (NLI) → Zero-Shot classification via DeBERTa-v3-large-zeroshot
   │
   ▼ (fan-in)
Phase 4 — Aggregation
   └── Aggregator LLM → boolean logic synthesis → final verdict + justification
```

---

## Key Components

### Claim Decomposition
- Splits complex, conjunctive claims into atomic, self-contained predicates using a structured JSON schema.
- Each predicate captures `relation`, `subject`, `object`, and `search_query`.
- A secondary **Classification Agent** labels each sub-claim as `verifiable`, `non-verifiable`, or `out-of-domain`.
- A deterministic **Claim Filter** discards non-medical and subjective statements.

### Evidence Retrieval
- **Europe PMC** — full-text Open Access articles via REST API.
- **UniProt** — structured biological metadata for molecular claims.
- **PubMed** — systematic reviews and meta-analyses via NCBI E-Utilities API.
- **Two-Stage Hybrid Retrieval**: BM25 sparse search + MedCPT dense search → Cross-Encoder reranking → Top-K diverse chunks.

### Reasoning & Veracity Assessment
- **Reasoning Agent** acts as a neutral extractor: verbatim quotes, entity comparison, numerical tracking — no verdicts.
- **Veracity Agent** uses a Natural Language Inference (NLI) model to classify evidence as `supported`, `refuted`, or `not_enough_information`, with a statistical confidence score.

### Verdict Aggregation
- **Aggregator LLM** applies AND/OR boolean logic over all sub-claim verdicts to produce the final compound verdict.
- Anti-hallucination constraint: the aggregator is forced to trust the NLI labels and cannot override them.

### Agent Orchestration
- Built on **LangGraph** with dynamic fan-out/fan-in for parallel sub-claim verification.
- Thread-safe state synchronization via algebraic reducers (no locking mechanisms needed).
- **LLMFactory** pattern ensures full model agnosticism — switch between NVIDIA NIM, Groq, Gemini, or Ollama via `config.json`.

### Storage
- **MongoDB** (NoSQL) for node-level telemetry: every LangGraph node is instrumented with a `@log_node` decorator.
- Each log entry includes: `run_id`, `node_name`, `stage`, `subclaim`, UTC `timestamp`, and the full output payload.
- Custom recursive BSON serializer handles NumPy arrays, LangChain message objects, and applies context-aware truncation.

### Interactive Dashboard
- Built with **Streamlit** + **FastAPI** backend.
- Real-time pipeline streaming via Server-Sent Events (SSE).
- Displays claim decomposition, RAG retrieval status, per-sub-claim reasoning with color-coded verbatim quotes, and the final verdict.
- Supports PDF report export for Electronic Health Records (EHR).

---

## Models & Configuration

| Parameter | Value |
|---|---|
| LLM (Reasoning/Decomposition) | `nvidia/nvidia-nemotron-nano-9b-v2` (NVIDIA NIM) |
| LLM Temperature | 0.2 |
| Veracity NLI Model | `deberta-v3-large-zeroshot-v1.1` |
| Dense Retriever | MedCPT Bi-Encoder (768-dim, INT8 quantized) |
| Sparse Retriever | BM25 |
| Reranker | `ncbi/MedCPT-Cross-Encoder` |
| Retrieval Budget | 5 queries per sub-claim |
| Max Docs per Query | 10 |
| Stage 1 Candidates | Top 20 Dense + Top 20 Sparse |
| Stage 2 Top-K | 8 chunks |
| Diversity Constraint | Max 10 chunks per document |
| Chunking | 300 words, 50-word overlap |

---
## Project Structure

```
MED-FACT-CHECK/
├── app/
│   ├── backend/
│   │   └── main.py                  # FastAPI backend (SSE streaming endpoint)
│   └── frontend/
│       ├── components/
│       │   └── ui_components.py     # Reusable Streamlit UI components
│       ├── pages/
│       │   └── Fact_Check.py        # Main fact-checking page
│       ├── utils/
│       │   ├── pdf_generator.py     # PDF report export for EHR
│       │   └── text_processing.py   # Text utilities for the frontend
│       └── app.py                   # Streamlit entrypoint
│
├── data/
│   ├── datasets/
│   │   ├── bioasq_clean.csv
│   │   ├── healthfc_clean.csv
│   │   └── scifact_clean.csv
│   └── raw_datasets/
│       ├── BioASQ-train-yesno-7b.json
│       └── healthFC_annotated.csv
│
├── data_preparation/
│   ├── check_conflicts.py           # Duplicate/conflict detection
│   └── prepare_dataset.py           # Dataset preprocessing & label normalization
│
├── docs/
│   ├── ablation_report.md
│   ├── aggregator_report.md
│   ├── architecture_report.md
│   ├── benchmarking_report.md
│   ├── decomposing_team_report.md
│   ├── dense_retrieval_report.md
│   ├── evaluation_team_report.md
│   ├── future_works.md
│   ├── retrieval_team_report.md
│   └── sparse_retrieval_report.md
│
├── src/
│   ├── prompts/
│   │   ├── aggregate.py             # Aggregator Agent system prompt
│   │   ├── decompose.py             # Decomposer Agent system prompt
│   │   ├── evaluate.py              # Veracity/Reasoning Agent system prompts
│   │   └── retrieve.py              # Source Selector & Query Gen. prompts
│   ├── stages/
│   │   ├── aggregator.py            # Phase 4 — Verdict Aggregation subgraph
│   │   ├── decomposing_team.py      # Phase 1 — Decomposition subgraph
│   │   ├── evaluation_team.py       # Phase 3 — Reasoning & Veracity subgraph
│   │   └── retrieval_team.py        # Phase 2 — Evidence Retrieval subgraph
│   ├── tools/retrieve/
│   │   ├── core/
│   │   │   ├── connectors/          # Europe PMC, UniProt, PubMed API connectors
│   │   │   ├── ingestion.py         # Document ingestion & chunking
│   │   │   └── text_cleaner.py      # Noise filtering & deduplication
│   │   ├── chunking.py              # Semantic chunking strategy
│   │   ├── dense.py                 # MedCPT Bi-Encoder dense retrieval
│   │   ├── download.py              # Parallel document downloader
│   │   ├── reranker.py              # MedCPT Cross-Encoder reranking
│   │   └── sparse.py                # BM25 sparse retrieval
│   ├── utils/
│   │   ├── config.py                # Configuration loader
│   │   ├── llm_factory.py           # Model-agnostic LLM factory
│   │   ├── logger.py                # General logging utilities
│   │   └── mongo_logger.py          # @log_node decorator & MongoDB telemetry
│   ├── main_agent.py                # LangGraph Super-Graph entrypoint
│   └── state.py                     # Global pipeline state definition
│
├── test/                            # Ablation & unit tests (REPL tools)
├── .env.example                     # Environment variables template
├── config.json                      # LLM provider & hyperparameter configuration
├── docker-compose.yml               # Multi-container orchestration
├── Dockerfile                       # Container definition
├── requirements.txt                 # Python dependencies
└── text_example.txt                 # Sample input claim for quick testing
```

## Evaluation

The system was benchmarked on three biomedical fact-checking datasets:

| Dataset | Description |
|---|---|
| **SciFact** | Expert-annotated scientific claims (Hugging Face: `allenai/scifact`) |
| **BioASQ** | Biomedical yes/no QA questions (PRAISELab-PicusLab CER) |
| **HealthFC** | Consumer health claims and clinical interventions (PRAISELab-PicusLab CER) |

Metrics: Accuracy, Macro-Precision, Macro-Recall, Macro-F1. For strictly binary datasets, a **binary evaluation with abstention** strategy is applied — NEI predictions are excluded from scoring and reported as the model's *Abstention Rate*.

Preliminary results on a stratified sample of 30 claims showed ~80% accuracy on BioASQ, ~60% on SciFact, and ~40% on HealthFC.

---

## Tech Stack

- **Orchestration**: LangGraph, LangChain
- **LLM Providers**: NVIDIA NIM, Groq (Llama-3), Google Gemini, Ollama
- **Retrieval**: BM25, MedCPT (HuggingFace), PyTorch (INT8 quantization)
- **NLI Classification**: DeBERTa-v3-large (HuggingFace Inference API)
- **Data Sources**: Europe PMC REST API, UniProt REST API, NCBI E-Utilities API
- **Storage**: MongoDB (PyMongo)
- **Backend**: FastAPI (SSE streaming)
- **Frontend**: Streamlit
- **Concurrency**: Python `ThreadPoolExecutor`

---

## 🚀 Quickstart (Docker-based)

The entire pipeline is containerized, eliminating dependency conflicts and ensuring environment consistency.

### 1. Requirements

* [Docker Desktop](https://www.docker.com/products/docker-desktop) installed and running.

### 2. Configuration

Clone the repository and set up your secrets:

```bash
git clone https://github.com/tuo-username/med-fact-check.git
cd med-fact-check

# Prepare environment variables
cp .env.example .env

```

Edit your `.env` file with your credentials:

```ini
MONGODB_URI=mongodb://mongodb:27017/med_fact_check
NVIDIA_API_KEY=your_key_here

```

### 3. Build & Run

Launch the entire system (Frontend, Backend, and Database) with a single command:

```bash
docker compose up --build

```

### 4. Usage

* 🌐 **Dashboard:** `http://localhost:8501`
* ⚙️ **API Docs:** `http://localhost:8000/docs`
* 🗄️ **Data Inspection:** Connect via **MongoDB Compass** to `mongodb://localhost:27017` to monitor node-level state logs and BSON payloads.



*Big Data Engineering Course, University of Naples Federico II | Prof. Vincenzo Moscato*
