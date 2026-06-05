from bs4 import BeautifulSoup
from typing import List, Dict

from utils.logger import get_logger
log = get_logger("TextCleaner")


# 1. Unstructured data cleaning (XML from Europe PMC)

def _is_glossary_or_noise(text: str) -> bool:
    """Detect abbreviation lists, glossaries, bullet-point highlights, and other non-argumentative noise."""
    stripped = text.strip()
    words = stripped.split()
    
    # Shallow bullet points (•, –, -, *) with fewer than 30 words → highlight lines with no substance
    if stripped and stripped[0] in '•–-*' and len(words) < 30:
        return True
    
    # High ratio of semicolons or commas relative to text length → likely a list of abbreviations
    semicolons = stripped.count(";") + stripped.count(",")
    if len(words) > 0 and semicolons / len(words) > 0.25:
        return True
    # High ratio of uppercase words → likely acronym-heavy glossary
    upper_words = sum(1 for w in words if w.isupper() and len(w) > 1)
    if len(words) > 5 and upper_words / len(words) > 0.3:
        return True
    return False


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
            if len(text) > 100 and not _is_glossary_or_noise(text): 
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
    """Return the clinical trial summary text."""
    return trial_dict.get('clinical_text', '')

def format_uniprot(protein_dict: Dict) -> str:
    
    return protein_dict.get('biological_text', 'No biological text available.')

def format_systematic_review(review_dict: Dict) -> str:
    """Return the abstract text from a PubMed systematic review / meta-analysis."""
    return review_dict.get('abstract_text', '')
