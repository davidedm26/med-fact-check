import requests
from typing import List, Dict, Optional

from utils.logger import get_logger
log = get_logger("EuropePMC_API")

BASE_URL_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
BASE_URL_FULLTEXT = "https://www.ebi.ac.uk/europepmc/webservices/rest/{}/fullTextXML"

def search_articles(query: str, limit: int = 10, max_year: int = None) -> List[Dict]: # Limit a 10
    """
    Search Europe PMC for articles using keywords.
    Enforces Open Access search and extracts the core metadata.
    """
    log.info(f"Searching articles for query: '{query}' (limit={limit}, max_year={max_year})")
    
    # Keep the OPEN_ACCESS:y filter to ensure full-text access, but allow abstract fallback
    structured_query = f"({query}) AND OPEN_ACCESS:y"
    if max_year:
        structured_query += f" AND (FIRST_PDATE:[* TO {max_year}-12-31])"
    
    params = {
        'query': structured_query,
        'format': 'json',
        'pageSize': limit,
        'resultType': 'core' 
    }
    header = {
    "User-Agent": "MedFactCheck-UniversityProject/1.0 (tua_email_reale@studenti.unisa.it)"
    }
    
    try:
        response = requests.get(BASE_URL_SEARCH, params=params, timeout=30, headers=header)
        response.raise_for_status()
        
        data = response.json()
        results = data.get('resultList', {}).get('result', [])
        
        extracted_data = []
        for item in results:
            # Extract the requested metadata with care
            extracted_data.append({
                "pmcid": item.get("pmcid", ""),
                "pmid": item.get("pmid", ""),          
                "doi": item.get("doi", ""),            
                "title": item.get("title", "Titolo non disponibile"),
                "abstract": item.get("abstractText", ""),
                "date": item.get("firstPublicationDate", item.get("pubYear", "N/A")) 
            })
            
        log.info(f"Found {len(extracted_data)} articles with metadata extracted.")
        return extracted_data

    except requests.exceptions.RequestException as e:
        log.error(f"Network error during search: {e}")
        return []

def fetch_full_text_xml(pmcid: str) -> Optional[str]:
    """
    Given an article PMCID, download the full text XML.
    """
    if not pmcid:
        return None

    url = BASE_URL_FULLTEXT.format(pmcid)
    
    try:
        response = requests.get(url, timeout=30) 
        if response.status_code == 404:
            log.debug(f"XML non disponibile per PMCID {pmcid} (404 Not Found).")
            return None
        response.raise_for_status()
        return response.text
        
    except requests.exceptions.RequestException as e:
        log.warning(f"Error downloading PMCID {pmcid}: {e}")
        return None

# Local test block

if __name__ == "__main__":
    print("\n" + "="*50)
    print("TEST API EUROPE PMC WITH METADATA")
    print("="*50)
    
    test_query = "mRNA vaccine DNA alteration"
    found_articles = search_articles(test_query, limit=2)
    
    for i, article in enumerate(found_articles):
        print(f"\n[{i+1}] {article['title']}")
        print(f"    PMID:  {article['pmid']}")
        print(f"    DOI:   {article['doi']}")
        print(f"    YEAR:  {article['year']}")
        
        if article['pmcid']:
            raw_xml = fetch_full_text_xml(article['pmcid'])
            if raw_xml:
                print(f"    ✓ XML downloaded successfully ({len(raw_xml)} bytes)")
            else:
                print("    ✗ XML download failed")