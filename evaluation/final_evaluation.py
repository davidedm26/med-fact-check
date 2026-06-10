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
# Modify this list to evaluate more or fewer datasets
DATASETS = ["scifact", "bioasq", "healthfc"]

# Custom run folder name (e.g. "final_run_1", "run_2") to avoid overwriting previous results.
# If empty, saves directly under results/pipeline_predictions/
RUN_NAME = ""

def load_progress(output_json_path):
    if os.path.exists(output_json_path):
        with open(output_json_path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_progress(predictions, output_json_path):
    temp_path = output_json_path + ".tmp"
    with open(temp_path, 'w', encoding='utf-8') as f:
        json.dump(predictions, f, indent=4)
    os.replace(temp_path, output_json_path)

def run_final_evaluation():
    run_output_dir = os.path.join(OUTPUT_DIR, RUN_NAME) if RUN_NAME else OUTPUT_DIR
    os.makedirs(run_output_dir, exist_ok=True)
    
    print(f"STARTING FINAL EVALUATION (MULTI-SESSION)\n" + "="*50)
    print("Progress will be saved automatically to allow resuming execution later.")
    if RUN_NAME:
        print(f"Run name (folder): {RUN_NAME}")
        
    agent = FactAgent()
    
    for ds_name in DATASETS:
        csv_path = os.path.join(DATASETS_DIR, f"{ds_name}_clean.csv")
        output_json_path = os.path.join(run_output_dir, f"final_pred_{ds_name}.json")
        
        if not os.path.exists(csv_path):
            print(f"WARNING: Dataset {csv_path} not found. Skipping.")
            continue
            
        print(f"\nProcessing dataset: {ds_name.upper()}")
        df = pd.read_csv(csv_path)
        
        # Perform stratified sampling to select exactly 100 samples
        total_samples = min(len(df), 100)
        counts = (df['true_label'].value_counts(normalize=True) * total_samples).round().astype(int)
        for label in df['true_label'].unique():
            if counts.get(label, 0) == 0 and len(df[df['true_label'] == label]) > 0:
                counts[label] = 1
        difference = total_samples - counts.sum()
        if difference != 0:
            largest_class = counts.idxmax()
            counts[largest_class] = max(1, counts[largest_class] + difference)
            
        sampled_dfs = []
        for label, group in df.groupby('true_label'):
            n_samples = min(len(group), counts.get(label, 0))
            if n_samples > 0:
                sampled_dfs.append(group.sample(n=n_samples, random_state=42))
        df_sampled = pd.concat(sampled_dfs).reset_index(drop=True)
        
        # Load previous progress
        predictions = load_progress(output_json_path)
        processed_claim_ids = {p["claim_id"] for p in predictions}
        
        # Filter claims to process (remove those already evaluated)
        df_to_process = df_sampled[~df_sampled['claim_id'].isin(processed_claim_ids)].copy()
        
        print(f"Dataset {ds_name}: {len(processed_claim_ids)} claims already processed in previous sessions.")
        print(f"Dataset {ds_name}: {len(df_to_process)} claims remaining to evaluate.")
        
        if len(df_to_process) == 0:
            print(f"Dataset {ds_name} already completed!")
            continue
            
        for _, row in tqdm(df_to_process.iterrows(), total=len(df_to_process), desc=f"Evaluating {ds_name}"):
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
            
            # Save progress after EACH claim, so execution can be interrupted at any time
            save_progress(predictions, output_json_path)

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

def calculate_final_metrics():
    print("\n" + "="*50)
    print("CALCULATING FINAL METRICS...")
    
    all_metrics = []
    
    run_output_dir = os.path.join(OUTPUT_DIR, RUN_NAME) if RUN_NAME else OUTPUT_DIR
    if RUN_NAME:
        print(f"Filtering metrics for run: {RUN_NAME}")
        
    for ds_name in DATASETS:
        filename = f"final_pred_{ds_name}.json"
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
            "Total_Claims": total_claims,
            "Excluded_NEI": excluded_claims,
            "Evaluated_Claims": evaluated_claims,
            "Accuracy": round(acc, 4),
            "Precision": round(prec, 4),
            "Recall": round(rec, 4),
            "F1_Score": round(f1, 4)
        })

    if all_metrics:
        df_metrics = pd.DataFrame(all_metrics)
        output_csv = os.path.join(OUTPUT_DIR, "final_evaluation_summary.csv")
        df_metrics.to_csv(output_csv, index=False)
        print(f"\nSave complete! Final summary table exported to:\n->  {output_csv}")

if __name__ == "__main__":
    run_final_evaluation()
    calculate_final_metrics()
