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
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print(f"STARTING FINAL EVALUATION (MULTI-SESSION)\n" + "="*50)
    print("Progress will be saved automatically to allow resuming execution later.")
    
    agent = FactAgent(dataset="evaluation_run")
    
    for ds_name in DATASETS:
        csv_path = os.path.join(DATASETS_DIR, f"{ds_name}_clean.csv")
        output_json_path = os.path.join(OUTPUT_DIR, f"final_pred_{ds_name}.json")
        
        if not os.path.exists(csv_path):
            print(f"WARNING: Dataset {csv_path} not found. Skipping.")
            continue
            
        print(f"\nProcessing dataset: {ds_name.upper()}")
        df = pd.read_csv(csv_path)
        
        # EXCLUDE claims with true_label == "NEI" before running the pipeline
        df = df[df['true_label'].str.upper() != "NEI"].copy()
        
        # Load previous progress
        predictions = load_progress(output_json_path)
        processed_claim_ids = {p["claim_id"] for p in predictions}
        
        # Filter claims to process (remove those already evaluated)
        df_to_process = df[~df['claim_id'].isin(processed_claim_ids)].copy()
        
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

def calculate_final_metrics():
    print("\n" + "="*50)
    print("CALCULATING FINAL METRICS...")
    
    all_metrics = []
    
    for ds_name in DATASETS:
        pred_file = os.path.join(OUTPUT_DIR, f"final_pred_{ds_name}.json")
        
        if not os.path.exists(pred_file):
            continue
            
        with open(pred_file, 'r', encoding='utf-8') as f:
            try:
                results = json.load(f)
            except json.JSONDecodeError:
                continue
            
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
        output_csv = "final_evaluation_summary.csv"
        df_metrics.to_csv(output_csv, index=False)
        print(f"\nSave complete! Final summary table exported to:\n->  {output_csv}")

if __name__ == "__main__":
    run_final_evaluation()
    calculate_final_metrics()
