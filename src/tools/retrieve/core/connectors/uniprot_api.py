import json

import requests
import logging
from typing import List, Dict

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

BASE_URL_UNIPROT = "https://rest.uniprot.org/uniprotkb/search"

def search_protein(query: str, limit: int = 10) -> List[Dict]: # Limit to 10
    logging.info(f"[UniProt] Searching protein/gene for query: '{query}'")
    
    params = {
        "query": query,
        "size": limit,
        "format": "json",
        #"fields": "accession,id,protein_name,gene_names,cc_function,cc_interaction,cc_disease,organism_name"
        "fields": "accession,id,protein_name,gene_names,cc_function,organism_name"
    }
    
    try:
        response = requests.get(BASE_URL_UNIPROT, params=params, timeout=10)
        response.raise_for_status()
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
            for comment in comments:
                if comment.get("commentType") == "FUNCTION":
                    texts = comment.get("texts", [])
                    if texts:
                        function_text = texts[0].get("value", "")
                    break
                    
            official_url = f"https://www.uniprot.org/uniprotkb/{accession}/entry" if accession != 'Unknown' else ""
            
            extracted_data.append({
                "accession_id": accession,
                "protein_name": full_name,
                #"biological_text": full_bio_text,
                "gene_name": gene_name,
                "organism": organism,
                "function": function_text,
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
        logging.error(f"[UniProt] Network error: {e}")
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
        print(f"    Function: {protein['function'][:200]}...\n")