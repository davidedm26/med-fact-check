import os
import sys
import json
import pandas as pd
from tqdm import tqdm
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

# Add src to path to import the agent
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
# pyrefly: ignore [missing-import]
from main_agent import FactAgent

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASETS_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "data", "datasets"))
OUTPUT_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "results", "pipeline_predictions"))

# ==========================================
# RAPID EVALUATION SETTINGS
# ==========================================
# Change the dataset name here: "scifact", "bioasq", "healthfc", or "all" to run all
DATASET_TO_EVALUATE = "bioasq" 

# Total maximum number of samples to evaluate across all classes.
# The script will perform stratified sampling to maintain class proportions.
MAX_SAMPLES = 30

# Custom run folder name (e.g. "test3", "run_2") to avoid overwriting previous results.
# If empty, saves directly under results/pipeline_predictions/
RUN_NAME = "test4"
# ==========================================

def run_rapid_evaluation():
    run_output_dir = os.path.join(OUTPUT_DIR, RUN_NAME) if RUN_NAME else OUTPUT_DIR
    os.makedirs(run_output_dir, exist_ok=True)
    
    print(f"STARTING RAPID EVALUATION\n" + "="*50)
    print(f"Selected dataset: {DATASET_TO_EVALUATE.upper()}")
    print(f"Max samples: {MAX_SAMPLES}")
    if RUN_NAME:
        print(f"Run name (folder): {RUN_NAME}")
    
    agent = FactAgent()
    
    datasets_to_run = ["scifact", "bioasq", "healthfc"] if DATASET_TO_EVALUATE.lower() == "all" else [DATASET_TO_EVALUATE]
    
    for ds_name in datasets_to_run:
        csv_path = os.path.join(DATASETS_DIR, f"{ds_name}_clean.csv")
        output_json_path = os.path.join(run_output_dir, f"rapid_pred_{ds_name}.json")
        
        if not os.path.exists(csv_path):
            print(f"WARNING: Dataset {csv_path} not found. Skipping.")
            continue
            
        print(f"\nProcessing dataset: {ds_name.upper()}")
        df = pd.read_csv(csv_path)
        
        # Do NOT exclude claims with true_label == "NEI" before running the pipeline
        # df = df[df['true_label'].str.upper() != "NEI"].copy()
        
        total_samples = min(len(df), MAX_SAMPLES)
        
        # Stratified sampling
        # Compute exact counts per class to match total_samples as closely as possible
        counts = (df['true_label'].value_counts(normalize=True) * total_samples).round().astype(int)
        
        # Ensure each class gets at least 1 sample if there are samples available
        for label in df['true_label'].unique():
            if counts.get(label, 0) == 0 and len(df[df['true_label'] == label]) > 0:
                counts[label] = 1
                
        # Adjust sum of counts to match total_samples exactly
        difference = total_samples - counts.sum()
        if difference != 0:
            largest_class = counts.idxmax()
            counts[largest_class] = max(1, counts[largest_class] + difference)
            
        sampled_dfs = []
        for label, group in df.groupby('true_label'):
            n_samples = min(len(group), counts.get(label, 0))
            if n_samples > 0:
                sampled_dfs.append(group.sample(n=n_samples, random_state=42))
        
        sampled_df = pd.concat(sampled_dfs).reset_index(drop=True)
            
        print(f"Sampled {len(sampled_df)} claims from {len(df)} total.")
        print("Label distribution in sample:")
        print(sampled_df['true_label'].value_counts())
        
        predictions = []
        
        for _, row in tqdm(sampled_df.iterrows(), total=len(sampled_df), desc=f"Evaluating {ds_name}"):
            claim_id = row['claim_id']
            claim_text = row['claim']
            true_label = row['true_label']
            
            try:
                agent.dataset = ds_name
                results = agent.process_claim(claim_text, recursion_limit=20, verbose=False)
                
                clean_steps = []
                predicted_label = "NEI"
                for step in results:
                    # Estrai i dati escludendo oggetti Langchain non serializzabili come 'messages'
                    clean_step = {}
                    for node_name, node_data in step.items():
                        clean_node = {k: v for k, v in node_data.items() if k != "messages"}
                        clean_step[node_name] = clean_node
                    clean_steps.append(clean_step)
                    
                    if "aggregate" in step:
                        final_verdict = step["aggregate"].get("final_verdict", {})
                        predicted_label = final_verdict.get("label", "NEI")
                        
            except Exception as e:
                print(f"\nError processing claim {claim_id}: {e}")
                predicted_label = "ERROR"
                clean_steps = [{"error": str(e)}]
                
            predictions.append({
                "claim_id": claim_id,
                "claim": claim_text,
                "true_label": true_label,
                "predicted_label": predicted_label,
                "pipeline_steps": clean_steps
            })
            
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(predictions, f, indent=4)
            
        print(f"Saved {len(predictions)} predictions to {output_json_path}")
        
    print("\n" + "="*50)
    print("RAPID PIPELINE EVALUATION COMPLETED.")

def standardize_label(label: str) -> str:
    lbl = str(label).lower().strip()
    if lbl in ["nei", "not_enough_information", "not enough information"]:
        return "nei"
    if lbl in ["supported", "support", "true", "yes"]:
        return "supported"
    if lbl in ["refuted", "contradict", "false", "no"]:
        return "refuted"
    return lbl

def find_prediction_file(output_dir, filename):
    direct_path = os.path.join(output_dir, filename)
    if os.path.exists(direct_path):
        return direct_path
    for root, dirs, files in os.walk(output_dir):
        if filename in files:
            return os.path.join(root, filename)
    return None

def calculate_metrics():
    print("\n" + "="*50)
    print("CALCULATING METRICS...")
    
    datasets_to_run = ["scifact", "bioasq", "healthfc"] if DATASET_TO_EVALUATE.lower() == "all" else [DATASET_TO_EVALUATE]
    all_metrics = []
    
    run_output_dir = os.path.join(OUTPUT_DIR, RUN_NAME) if RUN_NAME else OUTPUT_DIR
    if RUN_NAME:
        print(f"Filtering metrics for run: {RUN_NAME}")
        
    for ds_name in datasets_to_run:
        filename = f"rapid_pred_{ds_name}.json"
        pred_file = find_prediction_file(run_output_dir, filename)
        
        if not pred_file:
            print(f"WARNING: Prediction file '{filename}' not found in {run_output_dir} or its subdirectories. Skipping.")
            continue
            
        print(f"Loading predictions from: {pred_file}")
        with open(pred_file, 'r', encoding='utf-8') as f:
            try:
                results = json.load(f)
            except json.JSONDecodeError as e:
                print(f"ERROR: Failed to parse JSON file {pred_file}: {e}")
                continue
            
        total_claims = len(results)
        if total_claims == 0:
            print(f"WARNING: Prediction file '{pred_file}' is empty. Skipping.")
            continue
            
        # Determine if dataset is natively 3-class (contains NEI true labels in the original CSV)
        csv_path = os.path.join(DATASETS_DIR, f"{ds_name}_clean.csv")
        has_nei_true = False
        if os.path.exists(csv_path):
            try:
                df_full = pd.read_csv(csv_path)
                has_nei_true = any(standardize_label(val) == "nei" for val in df_full["true_label"].dropna().unique())
            except Exception as e:
                print(f"WARNING: Could not check original CSV for 3-class status: {e}")
                has_nei_true = any(standardize_label(item.get("true_label", "")) == "nei" for item in results)
        else:
            has_nei_true = any(standardize_label(item.get("true_label", "")) == "nei" for item in results)
        
        filtered_results = results
        evaluated_claims = len(results)
        excluded_claims = 0
        
        if has_nei_true:
            print(f"\nAnalyzing: {ds_name.upper()} (3-class dataset)")
            print("-" * 40)
            print(f"Total claims:     {total_claims}")
            print(f"Evaluated claims: {evaluated_claims} (Supported/Refuted/NEI)")
        else:
            print(f"\nAnalyzing: {ds_name.upper()} (Binary dataset - Strict Evaluation)")
            print("-" * 40)
            print(f"Total claims:     {total_claims}")
            print(f"Evaluated claims: {evaluated_claims} (Supported/Refuted, NEI counted as error)")
        
        if evaluated_claims == 0:
            continue
            
        y_true = [standardize_label(item["true_label"]) for item in filtered_results]
        y_pred = [standardize_label(item["predicted_label"]) for item in filtered_results]
        
        acc = accuracy_score(y_true, y_pred)
        prec = precision_score(y_true, y_pred, average='macro', zero_division=0)
        rec = recall_score(y_true, y_pred, average='macro', zero_division=0)
        f1 = f1_score(y_true, y_pred, average='macro', zero_division=0)
        
        print(f"Accuracy:  {acc:.4f}  ({acc*100:.2f}%)")
        print(f"Precision: {prec:.4f}  ({prec*100:.2f}%)")
        print(f"Recall:    {rec:.4f}  ({rec*100:.2f}%)")
        print(f"F1-Score:  {f1:.4f}  ({f1*100:.2f}%)")
        
        all_metrics.append({
            "Dataset": ds_name.upper(),
            "Accuracy": round(acc, 4),
            "F1_Score": round(f1, 4)
        })

if __name__ == "__main__":
    # Uncomment the line below if you want to rerun predictions from scratch
    run_rapid_evaluation()
    
    # Only calculates metrics using already saved JSONs
    calculate_metrics()
