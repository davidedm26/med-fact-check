import json
import os
from datasets import load_dataset
from collections import defaultdict

def check_scifact_conflicts():
    print("Checking conflicts in SciFact...")
    dataset = load_dataset("allenai/scifact", "claims", split="train", trust_remote_code=True)
    
    claim_labels = defaultdict(set)
    for item in dataset:
        claim = item['claim']
        evidence_label = item.get('evidence_label', '')
        
        if evidence_label == "SUPPORT":
            label = "supported"
        elif evidence_label == "CONTRADICT":
            label = "refuted"
        else:
            label = "NEI"
            
        # Add label to the set (set ignores identical duplicates)
        claim_labels[claim].add(label)
        
    # Filter only claims that have MORE THAN ONE different label
    conflicts = {claim: labels for claim, labels in claim_labels.items() if len(labels) > 1}
    print(f"Found {len(conflicts)} claims with conflicting labels in SciFact.")
    
    if conflicts:
        print("Here are some examples of conflicts in SciFact:")
        for claim, labels in list(conflicts.items())[:5]: # Show the first 5
            print(f"Claim: '{claim}' -> Labels found: {labels}")

def check_bioasq_conflicts():
    print("\nChecking conflicts in BioASQ...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.abspath(os.path.join(base_dir, "..", "data", "raw_datasets", "BioASQ-train-yesno-7b.json"))
    
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    claim_labels = defaultdict(set)
    
    if "data" in data:
        for article in data["data"]:
            for paragraph in article.get("paragraphs", []):
                for qas in paragraph.get("qas", []):
                    claim = qas.get("question", "")
                    answers = qas.get("answers")
                    
                    ans_text = ""
                    if isinstance(answers, str):
                        ans_text = answers.lower().strip()
                    elif isinstance(answers, list) and len(answers) > 0:
                        if isinstance(answers[0], dict):
                            ans_text = str(answers[0].get("text", "")).lower().strip()
                        else:
                            ans_text = str(answers[0]).lower().strip()
                    
                    if ans_text == "yes":
                        label = "supported"
                    elif ans_text == "no":
                        label = "refuted"
                    else:
                        label = "NEI"
                        
                    claim_labels[claim].add(label)
                    
    conflicts = {claim: labels for claim, labels in claim_labels.items() if len(labels) > 1}
    print(f"Found {len(conflicts)} claims with conflicting labels in BioASQ.")
    
    if conflicts:
        print("Here are some examples of conflicts in BioASQ:")
        for claim, labels in list(conflicts.items())[:5]:
            print(f" Claim: '{claim}' -> Labels found: {labels}")

if __name__ == "__main__":
    check_scifact_conflicts()
    check_bioasq_conflicts()