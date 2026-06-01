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
DATASET_TO_EVALUATE = "healthfc" 

# Maximum number of samples PER CLASS (e.g. 5 supported, 5 refuted). 
# Useful for getting almost immediate feedback.
MAX_SAMPLES_PER_CLASS = 5
# ==========================================

def run_rapid_evaluation():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print(f"STARTING RAPID EVALUATION\n" + "="*50)
    print(f"Selected dataset: {DATASET_TO_EVALUATE.upper()}")
    print(f"Max samples per class: {MAX_SAMPLES_PER_CLASS}")
    
    agent = FactAgent(dataset="evaluation_run")
    
    datasets_to_run = ["scifact", "bioasq", "healthfc"] if DATASET_TO_EVALUATE.lower() == "all" else [DATASET_TO_EVALUATE]
    
    for ds_name in datasets_to_run:
        csv_path = os.path.join(DATASETS_DIR, f"{ds_name}_clean.csv")
        output_json_path = os.path.join(OUTPUT_DIR, f"rapid_pred_{ds_name}.json")
        
        if not os.path.exists(csv_path):
            print(f"WARNING: Dataset {csv_path} not found. Skipping.")
            continue
            
        print(f"\nProcessing dataset: {ds_name.upper()}")
        df = pd.read_csv(csv_path)
        
        # EXCLUDE claims with true_label == "NEI" before running the pipeline
        df = df[df['true_label'].str.upper() != "NEI"].copy()
        
        sampled_dfs = []
        for label, group in df.groupby('true_label'):
            n_samples = min(len(group), MAX_SAMPLES_PER_CLASS)
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

def calculate_metrics():
    print("\n" + "="*50)
    print("CALCULATING METRICS...")
    
    datasets_to_run = ["scifact", "bioasq", "healthfc"] if DATASET_TO_EVALUATE.lower() == "all" else [DATASET_TO_EVALUATE]
    all_metrics = []
    
    for ds_name in datasets_to_run:
        pred_file = os.path.join(OUTPUT_DIR, f"rapid_pred_{ds_name}.json")
        
        if not os.path.exists(pred_file):
            continue
            
        with open(pred_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
            
        total_claims = len(results)
        if total_claims == 0:
            continue
            
        filtered_results = [
            item for item in results 
            if str(item["true_label"]).upper() != "NEI" and str(item["predicted_label"]).upper() != "NEI"
        ]
        evaluated_claims = len(filtered_results)
        excluded_claims = total_claims - evaluated_claims
        
        print(f"\nAnalyzing: {ds_name.upper()}")
        print("-" * 40)
        print(f"Total claims:     {total_claims}")
        print(f"Excluded 'NEI':   {excluded_claims} (True or Predicted)")
        print(f"Evaluated claims: {evaluated_claims} (Supported/Refuted)")
        
        if evaluated_claims == 0:
            continue
            
        y_true = [str(item["true_label"]).lower() for item in filtered_results]
        y_pred = [str(item["predicted_label"]).lower() for item in filtered_results]
        
        acc = accuracy_score(y_true, y_pred)
        prec = precision_score(y_true, y_pred, average='weighted', zero_division=0)
        rec = recall_score(y_true, y_pred, average='weighted', zero_division=0)
        f1 = f1_score(y_true, y_pred, average='weighted', zero_division=0)
        
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
