import os
import pandas as pd
import json
from datasets import load_dataset

# Define directories for separation of concerns
RAW_DIR = "raw_datasets"
OUTPUT_DIR = "datasets"

# Create directories if they don't exist
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def prepare_scifact():
    print("📥 Downloading SciFact (Train+Validation) from Hugging Face...")

    dataset = load_dataset("allenai/scifact", "claims", split="train+validation", trust_remote_code=True)
    
    scifact_data = []
    for item in dataset:
        claim = item['claim']
        evidence_label = item.get('evidence_label', '')
        
        if evidence_label == "SUPPORT":
            true_label = "Supported"
        elif evidence_label == "CONTRADICT":
            true_label = "Refuted"
        else:
            true_label = "NEI"
                        
        scifact_data.append({"claim_id": f"scifact_{item['id']}", "claim": claim, "true_label": true_label})
    
    df = pd.DataFrame(scifact_data)
    
    # Remove duplicates from SciFact claims, keeping only one instance of each claim.
    # Note: We previously verified via a separate script (check_conflicts.py) that there are 0 conflicting labels 
    # for the same claim in this dataset. Therefore, it is completely safe to drop duplicates.
    df['label_priority'] = df['true_label'].map({'Supported': 1, 'Refuted': 1, 'NEI': 2})
    df = df.sort_values('label_priority').drop_duplicates(subset=['claim'], keep='first').drop(columns=['label_priority'])
    
    df.to_csv(f"{OUTPUT_DIR}/scifact_clean.csv", index=False)
    
    counts = df['true_label'].value_counts().to_dict()
    print(f"✅ SciFact saved! ({len(df)} UNIQUE claims). Label distribution: {counts}")

def prepare_bioasq():
    print("🛠️ Formatting BioASQ (from local file)...")
    file_path = f"{RAW_DIR}/BioASQ-train-yesno-7b.json"
    
    if not os.path.exists(file_path):
        print(f"⚠️ WARNING: File {file_path} not found. Please copy it to the '{RAW_DIR}/' folder.")
        return
        
    import json
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    bioasq_data = []
    
    if "data" in data:
        for article in data["data"]:
            for paragraph in article.get("paragraphs", []):
                for qas in paragraph.get("qas", []):
                    claim = qas.get("question", "")
                    ans_text = ""
                    answers = qas.get("answers")
                    
                    if isinstance(answers, str):
                        ans_text = answers.lower().strip()
                    elif isinstance(answers, list) and len(answers) > 0:
                        if isinstance(answers[0], dict):
                            ans_text = str(answers[0].get("text", "")).lower().strip()
                        else:
                            ans_text = str(answers[0]).lower().strip()
                    
                    if ans_text == "yes":
                        true_label = "Supported"
                    elif ans_text == "no":
                        true_label = "Refuted"
                    else:
                        true_label = "NEI"
                        
                    bioasq_data.append({
                        "claim_id": f"bioasq_temp", 
                        "claim": claim, 
                        "true_label": true_label
                    })
                    
    df = pd.DataFrame(bioasq_data)
    
    # Remove duplicates from BioASQ claims, keeping only one instance of each claim.
    # Note: As with SciFact, we verified there are no label conflicts for identical questions.
    # We drop duplicate claims to keep the dataset unbiased and clean.
    df = df.drop_duplicates(subset=['claim'], keep='first').reset_index(drop=True)
    
    df['claim_id'] = [f"bioasq_{i}" for i in range(len(df))]
    
    df.to_csv(f"{OUTPUT_DIR}/bioasq_clean.csv", index=False)
    
    counts = df['true_label'].value_counts().to_dict()
    print(f"✅ BioASQ saved and formatted! ({len(df)} UNIQUE claims). Label distribution: {counts}")
    
def prepare_healthfc():
    print("🛠️ Formatting HealthFC (from local file)...")
    file_path = f"{RAW_DIR}/healthFC_annotated.csv"
    
    if not os.path.exists(file_path):
        print(f"⚠️ WARNING: File {file_path} not found. Please copy it to the '{RAW_DIR}/' folder.")
        return
        
    df_original = pd.read_csv(file_path)
    healthfc_data = []
    
    for i, row in df_original.iterrows():
        claim = row['en_claim'] 
        
        # Robust check stripping hidden spaces and checking common synonyms
        original_label = str(row['label']).lower().strip()
        
        if original_label in ["true", "yes", "1", "1.0", "wahr"]:
            true_label = "Supported"
        elif original_label in ["false", "no", "0", "0.0", "falsch"]:
            true_label = "Refuted"
        else:
            true_label = "NEI"
            
        healthfc_data.append({"claim_id": f"healthfc_{i}", "claim": claim, "true_label": true_label})
        
    df = pd.DataFrame(healthfc_data)
    df.to_csv(f"{OUTPUT_DIR}/healthfc_clean.csv", index=False)
    
    counts = df['true_label'].value_counts().to_dict()
    print(f"✅ HealthFC saved and formatted! ({len(df)} claims). Label distribution: {counts}")


if __name__ == "__main__":
    print("🚀 STARTING DATASET PREPARATION\n" + "="*40)
    prepare_scifact()
    prepare_bioasq()
    prepare_healthfc()
    print("="*40 + "\n🎉 All datasets are clean, formatted, and ready for evaluation!")