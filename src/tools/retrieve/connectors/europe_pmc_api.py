import requests
import logging
from typing import List, Dict, Optional

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

BASE_URL_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
BASE_URL_FULLTEXT = "https://www.ebi.ac.uk/europepmc/webservices/rest/{}/fullTextXML"

def search_articles(query: str, limit: int = 10) -> List[Dict]: # Limit a 10
    """
    Search Europe PMC for articles using keywords.
    Enforces Open Access search and extracts the core metadata.
    """
    logging.info(f"[EuropePMC] Searching articles for query: '{query}'")
    
    # Keep the OPEN_ACCESS:y filter to ensure full-text access
    structured_query = f"{query} OPEN_ACCESS:y"
    
    params = {
        'query': structured_query,
        'format': 'json',
        'pageSize': limit,
        'resultType': 'core' 
    }
    
    try:
        response = requests.get(BASE_URL_SEARCH, params=params, timeout=15)
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
            
        logging.info(f"[EuropePMC] Found {len(extracted_data)} articles with metadata extracted.")
        return extracted_data

    except requests.exceptions.RequestException as e:
        logging.error(f"[EuropePMC] Network error during search: {e}")
        return []

def fetch_full_text_xml(pmcid: str) -> Optional[str]:
    """
    Given an article PMCID, download the full text XML.
    """
    if not pmcid:
        return None
        
    logging.info(f"[EuropePMC] Downloading full text XML for article {pmcid}...")
    url = BASE_URL_FULLTEXT.format(pmcid)
    
    try:
        response = requests.get(url, timeout=20) 
        response.raise_for_status()
        return response.text
        
    except requests.exceptions.RequestException as e:
        logging.error(f"[EuropePMC] Error downloading PMCID {pmcid}: {e}")
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