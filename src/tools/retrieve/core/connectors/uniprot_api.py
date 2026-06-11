import json
import time

import requests
from typing import List, Dict

from utils.logger import get_logger
log = get_logger("UniProtAPI")

BASE_URL_UNIPROT = "https://rest.uniprot.org/uniprotkb/search"

def _robust_get(url: str, params: dict = None, timeout: float = 30.0, max_retries: int = 3, backoff_factor: float = 1.0) -> requests.Response:
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            if response.status_code == 429:
                log.warning(f"UniProt rate limit (429) hit. Retrying in {backoff_factor * (2 ** (attempt - 1))}s...")
                time.sleep(backoff_factor * (2 ** (attempt - 1)))
                continue
            if 500 <= response.status_code < 600:
                log.warning(f"UniProt server error ({response.status_code}). Retrying in {backoff_factor * (2 ** (attempt - 1))}s...")
                time.sleep(backoff_factor * (2 ** (attempt - 1)))
                continue
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            last_exc = e
            log.warning(f"UniProt network error on attempt {attempt}: {e}. Retrying...")
            time.sleep(backoff_factor * (2 ** (attempt - 1)))
    
    if last_exc:
        raise last_exc
    raise requests.exceptions.RequestException("UniProt request failed after maximum retries.")

def search_protein(query: str, limit: int = 10) -> List[Dict]: # Limit to 10
    log.info(f"Searching protein/gene for query: '{query}'")
    
    params = {
        "query": query,
        "size": limit,
        "format": "json",
        "fields": "accession,id,protein_name,gene_names,cc_function,cc_interaction,organism_name"
    }
    
    try:
        response = _robust_get(BASE_URL_UNIPROT, params=params, timeout=10)
        data = response.json()
        results = data.get('results', [])
        
        extracted_data = []
        for item in results:
            accession = item.get("primaryAccession", "Unknown")
            protein_desc = item.get("proteinDescription", {})
            rec_name = protein_desc.get("recommendedName", {})
            full_name = rec_name.get("fullName", {}).get("value", "Name unavailable")
            
            genes = item.get("genes", [])
            gene_name = genes[0].get("geneName", {}).get("value", "Unknown gene") if genes else "N/A"
            organism = item.get("organism", {}).get("scientificName", "Unknown organism")
            
            """
            comments = item.get("comments", [])
            function_text, interaction_text, disease_text = "", "", ""
            
            for comment in comments:
                tipo = comment.get("commentType")
                if tipo == "FUNCTION":
                    function_text = comment.get("texts", [{}])[0].get("value", "")
                elif tipo == "DISEASE":
                    disease_text = comment.get("note", {}).get("texts", [{}])[0].get("value", "")
                elif tipo == "INTERACTION":
                    interactants = comment.get("interactions", [])
                    interaction_text = ", ".join([i.get("interactantTwo", {}).get("geneName", "") for i in interactants])

            full_bio_text = f"Function: {function_text} Diseases: {disease_text} Interacts with: {interaction_text}".strip()
            """

            comments = item.get("comments", [])
            function_text = "Funzione non specificata."
            interaction_list = []
            
            for comment in comments:
                tipo = comment.get("commentType")
                if tipo == "FUNCTION":
                    texts = comment.get("texts", [])
                    if texts and function_text == "Funzione non specificata.":
                        function_text = texts[0].get("value", "")
                elif tipo == "INTERACTION":
                    interactants = comment.get("interactions", [])
                    for i in interactants:
                        gene = i.get("interactantTwo", {}).get("geneName")
                        if gene and gene not in interaction_list:
                            interaction_list.append(gene)
            
            biological_text = f"Function: {function_text}"
            if interaction_list:
                biological_text += f" Interacts with: {', '.join(interaction_list)}"
                    
            official_url = f"https://www.uniprot.org/uniprotkb/{accession}/entry" if accession != 'Unknown' else ""
            
            extracted_data.append({
                "accession_id": accession,
                "protein_name": full_name,
                "biological_text": biological_text,
                "gene_name": gene_name,
                "organism": organism,
                "url": official_url
            })
            
        """   
        # Salva i dati filtrati (TEXT + METADATA) in un file JSON per Membro 3
        nome_file = f"processed_uniprot_{query.replace(' ', '_')[:20]}.json"
        with open(nome_file, "w", encoding="utf-8") as f_out:
            json.dump(extracted_data, f_out, indent=2, ensure_ascii=False)
        logging.info(f"[UniProt] File filtrato salvato per Membro 3: {nome_file}")
        """

        return extracted_data

    except requests.exceptions.RequestException as e:
        log.error(f"Network error: {e}")
        return []

# Local test block
if __name__ == "__main__":
    print("\n" + "="*50)
    print("TEST API UNIPROT WITH METADATA")
    print("="*50)
    
    test_query = "ACE2 AND organism_id:9606" 
    protein_results = search_protein(test_query, limit=2)
    
    for i, protein in enumerate(protein_results):
        print(f"\n[{i+1}] {protein['protein_name']} ({protein['gene_name']})")
        print(f"    Organism: {protein['organism']}")
        print(f"    UniProt ID: {protein['accession_id']}")
        print(f"    Link: {protein['url']}")
        print(f"    Biological Text: {protein['biological_text'][:200]}...\n")