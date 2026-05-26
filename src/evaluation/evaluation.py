import os
import json
import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

MOCK_DIR = "mock_predictions"
DATASETS = ["scifact", "bioasq", "healthfc"]
OUTPUT_CSV = "evaluation_summary.csv"

def run_evaluation():
    print("STARTING PIPELINE EVALUATION (BINARY ONLY)...\n" + "="*50)
    
    all_metrics = []

    for ds_name in DATASETS:
        mock_file = f"{MOCK_DIR}/mock_{ds_name}.json"
        print(f"\nAnalyzing: {ds_name.upper()}")
        print("-" * 40)
        
        if not os.path.exists(mock_file):
            print(f"WARNING: File {mock_file} not found. Skipping dataset.")
            continue
            
        with open(mock_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
            
        total_claims = len(results)
        
        # Filter out 'NEI' claims for evaluation
        filtered_results = [item for item in results if item["true_label"] != "NEI"]
        evaluated_claims = len(filtered_results)
        excluded_claims = total_claims - evaluated_claims
        
        print(f"Total claims loaded:     {total_claims}")
        print(f"Excluded 'NEI' claims:   {excluded_claims}")
        print(f"Evaluated claims:        {evaluated_claims} (Supported/Refuted)")
        
        if evaluated_claims == 0:
            print("No valid claims left for evaluation.")
            continue
            
        y_true = [item["true_label"] for item in filtered_results]
        y_pred = [item["predicted_label"] for item in filtered_results]
        
        # Compute metrics (weighted average to balance any class imbalance)
        acc = accuracy_score(y_true, y_pred)
        prec = precision_score(y_true, y_pred, average='weighted', zero_division=0)
        rec = recall_score(y_true, y_pred, average='weighted', zero_division=0)
        f1 = f1_score(y_true, y_pred, average='weighted', zero_division=0)
        
        print(f"\nAccuracy:  {acc:.4f}  ({acc*100:.2f}%)")
        print(f"Precision: {prec:.4f}  ({prec*100:.2f}%)")
        print(f"Recall:    {rec:.4f}  ({rec*100:.2f}%)")
        print(f"F1-Score:  {f1:.4f}  ({f1*100:.2f}%)")
        
        # Add metrics to the list for CSV export
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

    print("\n" + "="*50)
    
    # Export to CSV
    if all_metrics:
        df_metrics = pd.DataFrame(all_metrics)
        df_metrics.to_csv(OUTPUT_CSV, index=False)
        print(f"Save complete! Summary table exported to:\n➡️  {OUTPUT_CSV}")
    else:
        print("No data to export.")

if __name__ == "__main__":
    run_evaluation()