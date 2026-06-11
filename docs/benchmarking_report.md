# Benchmarking & Evaluation: Architecture Report

This report analyzes the rapid benchmarking infrastructure (`evaluation/rapid_evaluation.py`), which is designed for iterative, fast-feedback testing of the MedFactCheck pipeline against standard medical datasets.

## 1. Evaluation Setup

The evaluation suite is built to support multiple datasets out-of-the-box (e.g., `scifact`, `bioasq`, `healthfc`). Because running the entire LLM pipeline on thousands of claims is time-consuming and expensive, the script is optimized for "Rapid Evaluation".

### Key Features:
- **Stratified Sampling**: Uses `MAX_SAMPLES_PER_CLASS` to perform balanced, stratified sampling via pandas (`groupby('true_label')`). This ensures the model is tested evenly across `supported`, `refuted`, and `nei` claims without processing the entire dataset.
- **Pipeline Integration**: Directly imports the `FactAgent` and streams the claim through the entire super-graph, mimicking a real production request.
- **State Serialization**: Cleans the LangGraph state of non-serializable objects (like LangChain message objects) and dumps the full pipeline trace into a JSON prediction file (`rapid_pred_{dataset}.json`). This is crucial for debugging *why* a claim failed (e.g., did retrieval fail, or did the evaluation team make a logic error?).

---

## 2. Metrics Calculation Strategy

The `calculate_metrics` function evaluates the saved JSON predictions using `scikit-learn` (Accuracy, Macro-Precision, Macro-Recall, Macro-F1). 

However, it applies a very important **dynamic filtering strategy** based on the dataset's native schema:

### A. 3-Class Datasets
If the dataset natively contains `NEI` (Not Enough Information) as a valid ground-truth label, the script evaluates the pipeline across all 3 classes. A prediction of `NEI` is treated as a standard classification.

### B. Binary Datasets
If the dataset only contains `supported` and `refuted` ground truths (e.g., standard SciFact), the script automatically detects this. 
- **Filtering**: It dynamically *excludes* any claims where the pipeline predicted `NEI`. 
- **Why?**: In a real-world medical setting, admitting "I don't have enough evidence to judge this" (NEI) is a safe, preferred fallback over hallucinating a definitive True/False answer. Excluding NEI predictions from binary datasets allows researchers to measure the *strict accuracy* of the model only in cases where it felt confident enough to take a definitive stance.

---

## 3. Future Benchmarking Optimizations

- **Parallel Evaluation**: Currently, the script processes the sampled claims sequentially (`tqdm` loop). Wrapping the `agent.process_claim()` calls in an asynchronous pool or threading executor would massively speed up the evaluation phase.
- **Automated Cost Tracking**: Integrating an LLM token tracker (e.g., LangChain callbacks) to log the exact API cost for each dataset run. This would help balance accuracy vs. cost when testing smaller, cheaper models.
