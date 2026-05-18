import json
import logging
import os
from typing import List

from src.tools.retrieve.connectors.europe_pmc_api import search_articles, fetch_full_text_xml
from src.tools.retrieve.connectors.clinical_trials_api import search_trials
from src.tools.retrieve.connectors.uniprot_api import search_protein


from src.tools.retrieve.text_cleaner import clean_europe_pmc_xml, format_clinical_trial, format_uniprot

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

class IngestionNode:
    def __init__(self):
        # Ensure the data/ folder exists in the project
        os.makedirs("data", exist_ok=True)
        logging.info("[IngestionNode] Initialized. Ready to download data.")

    def prepare_data(self, sub_id: str, search_queries: List[str], target_source: str) -> List[dict]:
        logging.info(f"[IngestionNode] Task for {sub_id}: {search_queries} -> Destination: {target_source.upper()}")
        
        target = target_source.lower()
        raw_chunks = []

        # 1. Loop through each query
        for single_query in search_queries:
            logging.info(f"[{target.upper()}] 🔎 Searching data for variant: '{single_query}'")
            
            if target == "clinical_trials":
                extracted_trials = search_trials(query=single_query, limit=5) 
                for trial in extracted_trials:
                    raw_chunks.append({
                        "text": format_clinical_trial(trial),
                        "metadata": {
                            "id": trial.get("nct_id"), "title": trial.get("title"), "type": "Clinical Trial",
                            "date": trial.get("start_date"), "url": trial.get("url"),
                            "extra_info": {"phase": trial.get("phase"), "status": trial.get("status")}
                        }
                    })

            elif target == "knowledge_base":
                extracted_proteins = search_protein(query=single_query, limit=5)
                for protein in extracted_proteins:
                    raw_chunks.append({
                        "text": format_uniprot(protein),
                        "metadata": {
                            "id": protein.get("accession_id"), "title": protein.get("protein_name"), "type": "Protein Knowledge",
                            "date": "N/A", "url": protein.get("url"),
                            "extra_info": {"organism": protein.get("organism"), "gene": protein.get("gene_name")}
                        }
                    })

            elif target == "literature":
                articles = search_articles(query=single_query, limit=5)
                for article in articles:
                    pmcid = article.get("pmcid")
                    if pmcid:
                        raw_xml = fetch_full_text_xml(pmcid)
                        if raw_xml:
                            paragraphs = clean_europe_pmc_xml(xml_string=raw_xml, article_metadata=article)
                            for p in paragraphs:
                                raw_chunks.append({
                                    "text": p["text"],
                                    "metadata": {
                                        "id": p["metadata"].get("pmid"), "title": p["metadata"].get("title"), "type": "Scientific Literature",
                                        "date": p["metadata"].get("date", p["metadata"].get("year")),
                                        "url": f"https://doi.org/{p['metadata'].get('doi')}" if p["metadata"].get("doi") else "",
                                        "extra_info": {"doi": p["metadata"].get("doi")}
                                    }
                                })
            else:
                logging.error(f"[IngestionNode] Source '{target}' not supported.")
                continue

        # 2. Smart deduplication
        unique_chunks = {}
        for chunk in raw_chunks:
            # Create a unique key using ID + first 50 characters of the text
            unique_key = f"{chunk['metadata'].get('id', 'no_id')}_{hash(chunk['text'][:50])}"
            unique_chunks[unique_key] = chunk
            
        final_chunks = list(unique_chunks.values())

        # 3. Save shared export into the data folder
        if final_chunks:
            # e.g. "data/export_sc_01_literature.json"
            export_filename = os.path.join("data", f"export_{sub_id}_{target}.json")
            with open(export_filename, "w", encoding="utf-8") as f_out:
                json.dump(final_chunks, f_out, indent=2, ensure_ascii=False)
            logging.info(f"[{target.upper()}] 📦 Saved deduplicated export ({len(final_chunks)} chunks) to: '{export_filename}'")
        else:
            logging.warning(f"[IngestionNode] No data found for '{sub_id}'. No export created.")

        return final_chunks