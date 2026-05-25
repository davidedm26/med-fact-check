import json

import requests
from typing import List, Dict

from utils.logger import get_logger
log = get_logger("ClinicalTrialsAPI")

# Using ClinicalTrials API v2
BASE_URL_CT = "https://clinicaltrials.gov/api/v2/studies"

def search_trials(query: str, limit: int = 10) -> List[Dict]: # Limit a 10
    log.info(f"Searching trials for query: '{query}'")
    
    params = {
        "query.term": query,
        "pageSize": limit,
        #"fields": "NCTId,BriefTitle,OverallStatus,Phase,StartDate,CompletionDate,BriefSummary"
        "fields": "NCTId,BriefTitle,OverallStatus,Phase,StartDate,CompletionDate,BriefSummary,protocolSection.eligibilityModule"
    }
    
    
    try:
        response = requests.get(BASE_URL_CT, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        studies = data.get('studies', [])
        
        extracted_data = []
        for study in studies:
            protocol = study.get('protocolSection', {})
            identification_module = protocol.get('identificationModule', {})
            nct_id = identification_module.get('nctId', 'Unknown NCT')
            title = identification_module.get('briefTitle', 'Title unavailable')

            description_module = protocol.get('descriptionModule', {})
            summary = description_module.get('briefSummary', '')
            
            eligibility_module = protocol.get('eligibilityModule', {})
            eligibility = eligibility_module.get('eligibilityCriteria', 'Eligibility criteria not specified.')
            
            # Combine summary and eligibility into a single narrative text block for BM25
            clinical_text = f"Summary: {summary} | Eligibility: {eligibility}".strip()
            
            status_module = protocol.get('statusModule', {})
            status = status_module.get('overallStatus', 'Status unknown')
            start_date = status_module.get('startDateStruct', {}).get('date', 'Date unavailable')
            completion_date = status_module.get('completionDateStruct', {}).get('date', 'Date unavailable')
            
            design_module = protocol.get('designModule', {})
            phases = design_module.get('phases', [])
            phase_str = ", ".join(phases) if phases else "Phase not specified"
            
            official_url = f"https://clinicaltrials.gov/study/{nct_id}" if nct_id != 'Unknown NCT' else ""

            
            extracted_data.append({
                "nct_id": nct_id,
                "title": title,
                "clinical_text": clinical_text,
                "status": status,
                "phase": phase_str,
                "start_date": start_date,
                "completion_date": completion_date,
                "url": official_url
            })

        """    
        # Salva i dati filtrati (TEXT + METADATA) in un file JSON per Membro 3
        nome_file = f"processed_trials_{query.replace(' ', '_')[:20]}.json"
        with open(nome_file, "w", encoding="utf-8") as f_out:
            json.dump(extracted_data, f_out, indent=2, ensure_ascii=False)
        logging.info(f"[ClinicalTrials] File filtrato salvato per Membro 3: {nome_file}")
        """
        
        return extracted_data

    except requests.exceptions.RequestException as e:
        log.error(f"Network error: {e}")
        return []

# Local test block
if __name__ == "__main__":
    print("\n" + "="*50)
    print("TEST API CLINICAL TRIALS WITH METADATA")
    print("="*50)
    
    test_query = "Nirmatrelvir COVID-19" 
    trial_results = search_trials(test_query, limit=2)
    
    for i, trial in enumerate(trial_results):
        print(f"\n[{i+1}] {trial['title']}")
        print(f"    Trial ID: {trial['nct_id']}")
        print(f"    Status:   {trial['status']} (Phase: {trial['phase']})")
        print(f"    Start:    {trial['start_date']} | Completion: {trial['completion_date']}")
        print(f"    Link:     {trial['url']}")