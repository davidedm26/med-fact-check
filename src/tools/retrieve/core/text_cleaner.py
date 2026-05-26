from bs4 import BeautifulSoup
from typing import List, Dict

from utils.logger import get_logger
log = get_logger("TextCleaner")


# 1. Unstructured data cleaning (XML from Europe PMC)

def clean_europe_pmc_xml(xml_string: str, article_metadata: Dict) -> List[Dict]:
    """
    Cleans Europe PMC XML and returns a list of dictionaries.
    Each dictionary contains a paragraph and the metadata passport.
    """
    if not xml_string:
        return []

    try:
        soup = BeautifulSoup(xml_string, "xml")
        body = soup.find("body") or soup.find("abstract") or soup
        
        tags_to_remove = ["ref-list", "table-wrap", "fig", "disp-formula", "ack"]
        for tag_name in tags_to_remove:
            for tag in body.find_all(tag_name):
                tag.decompose()

        paragraphs_with_metadata = []
        for p_tag in body.find_all("p"):
            text = p_tag.get_text(separator=" ", strip=True)
            if len(text) > 50: 
                paragraphs_with_metadata.append({
                    "text": text,
                    "metadata": article_metadata
                })
        """
        # Salva i dati filtrati (TEXT + METADATA) in un file JSON per Membro 3
        if paragraphs_with_metadata:
            pmcid = article_metadata.get("pmcid", "Unknown")
            filename_chunks = f"processed_pmc_chunks_{pmcid}.json"
            
            with open(filename_chunks, "w", encoding="utf-8") as f_out:
                import json
                json.dump(paragraphs_with_metadata, f_out, indent=2, ensure_ascii=False)
            logging.info(f"[Cleaner] Text+Metadata file saved for Member 3: {filename_chunks}")
        """

        return paragraphs_with_metadata
    except Exception as e:
        log.error(f"XML cleanup error: {e}")
        return []


# 2. Structured data formatting (Clinical Trials and Uniprot)

def format_clinical_trial(trial_dict: Dict) -> str:
    
    return trial_dict.get('clinical_text', '')

def format_uniprot(protein_dict: Dict) -> str:
    
    return protein_dict.get('function', 'No function available.')



