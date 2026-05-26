import json
from datasets import load_dataset
from collections import defaultdict

def check_scifact_conflicts():
    print("🔍 Controllo conflitti in SciFact...")
    dataset = load_dataset("allenai/scifact", "claims", split="train+validation", trust_remote_code=True)
    
    claim_labels = defaultdict(set)
    for item in dataset:
        claim = item['claim']
        evidence_label = item.get('evidence_label', '')
        
        if evidence_label == "SUPPORT":
            label = "Supported"
        elif evidence_label == "CONTRADICT":
            label = "Refuted"
        else:
            label = "NEI"
            
        # Aggiungiamo la label al set (il set ignora i duplicati identici)
        claim_labels[claim].add(label)
        
    # Filtriamo solo i claim che hanno PIÙ DI UNA label diversa
    conflicts = {claim: labels for claim, labels in claim_labels.items() if len(labels) > 1}
    print(f"📊 Trovati {len(conflicts)} claim con etichette contrastanti in SciFact.")
    
    if conflicts:
        print("Ecco alcuni esempi di conflitti in SciFact:")
        for claim, labels in list(conflicts.items())[:5]: # Mostra i primi 5
            print(f" ⚠️ Claim: '{claim}' -> Etichette trovate: {labels}")

def check_bioasq_conflicts():
    print("\n🔍 Controllo conflitti in BioASQ...")
    file_path = "raw_datasets/BioASQ-train-yesno-7b.json"
    
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
                        label = "Supported"
                    elif ans_text == "no":
                        label = "Refuted"
                    else:
                        label = "NEI"
                        
                    claim_labels[claim].add(label)
                    
    conflicts = {claim: labels for claim, labels in claim_labels.items() if len(labels) > 1}
    print(f"📊 Trovati {len(conflicts)} claim con etichette contrastanti in BioASQ.")
    
    if conflicts:
        print("Ecco alcuni esempi di conflitti in BioASQ:")
        for claim, labels in list(conflicts.items())[:5]:
            print(f" ⚠️ Claim: '{claim}' -> Etichette trovate: {labels}")

if __name__ == "__main__":
    check_scifact_conflicts()
    check_bioasq_conflicts()