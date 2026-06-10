import os
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional

from utils.logger import get_logger

log = get_logger("PubMedAPI")

# NCBI E-Utilities endpoints
BASE_URL_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
BASE_URL_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# Systematic Review / Meta-Analysis filter
# systematic[sb]  → PubMed's built-in Systematic Review subset (NLM algorithm)
# "systematic review"[pt] OR "meta-analysis"[pt] → explicit publication-type filter
SR_MA_FILTER = 'systematic[sb] AND ("systematic review"[pt] OR "meta-analysis"[pt])'

import time

def _robust_get(url: str, params: dict = None, timeout: float = 30.0, max_retries: int = 3, backoff_factor: float = 1.0) -> requests.Response:
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            if response.status_code == 429:
                log.warning(f"PubMed rate limit (429) hit. Retrying in {backoff_factor * (2 ** (attempt - 1))}s...")
                time.sleep(backoff_factor * (2 ** (attempt - 1)))
                continue
            if 500 <= response.status_code < 600:
                log.warning(f"PubMed server error ({response.status_code}). Retrying in {backoff_factor * (2 ** (attempt - 1))}s...")
                time.sleep(backoff_factor * (2 ** (attempt - 1)))
                continue
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            last_exc = e
            log.warning(f"PubMed network error on attempt {attempt}: {e}. Retrying...")
            time.sleep(backoff_factor * (2 ** (attempt - 1)))
    
    if last_exc:
        raise last_exc
    raise requests.exceptions.RequestException("PubMed request failed after maximum retries.")

def _get_api_key() -> Optional[str]:
    """Return the NCBI API key from environment, or None if not set."""
    return os.environ.get("NCBI_API_KEY")


def _build_params(base_params: dict) -> dict:
    """Inject the API key into request params if available."""
    api_key = _get_api_key()
    if api_key:
        base_params["api_key"] = api_key
    return base_params


def _esearch(query: str, limit: int, max_year: int = None) -> List[str]:
    """
    Phase 1: Use ESearch to find PMIDs matching the query + SR/MA filter.
    Returns a list of PMID strings.
    """
    full_query = f"({query}) AND {SR_MA_FILTER}"
    if max_year:
        full_query += f' AND ("1800"[Date - Publication] : "{max_year}"[Date - Publication])'

    params = _build_params({
        "db": "pubmed",
        "term": full_query,
        "retmode": "json",
        "retmax": limit,
    })

    log.info(f"ESearch query: '{full_query}' (limit={limit})")

    try:
        response = _robust_get(BASE_URL_ESEARCH, params=params, timeout=15)
        data = response.json()
        pmids = data.get("esearchresult", {}).get("idlist", [])
        log.info(f"ESearch returned {len(pmids)} PMIDs")
        return pmids
    except requests.exceptions.RequestException as e:
        log.error(f"ESearch network error: {e}")
        return []


def _efetch(pmids: List[str]) -> List[Dict]:
    """
    Phase 2: Use EFetch to retrieve structured abstract data for a batch of PMIDs.
    Returns a list of article dicts with: pmid, title, abstract_text, doi, date, url, publication_types.
    """
    if not pmids:
        return []

    params = _build_params({
        "db": "pubmed",
        "id": ",".join(pmids),
        "rettype": "abstract",
        "retmode": "xml",
    })

    log.info(f"EFetch downloading {len(pmids)} articles")

    try:
        response = _robust_get(BASE_URL_EFETCH, params=params, timeout=30)
        return _parse_efetch_xml(response.text)
    except requests.exceptions.RequestException as e:
        log.error(f"EFetch network error: {e}")
        return []


def _parse_efetch_xml(xml_text: str) -> List[Dict]:
    """Parse the PubMed EFetch XML response and extract article metadata + abstracts."""
    articles = []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        log.error(f"XML parse error: {e}")
        return []

    for article_elem in root.findall(".//PubmedArticle"):
        try:
            medline = article_elem.find("MedlineCitation")
            if medline is None:
                continue

            # PMID
            pmid_elem = medline.find("PMID")
            pmid = pmid_elem.text if pmid_elem is not None else ""

            # Article info
            article_info = medline.find("Article")
            if article_info is None:
                continue

            # Title
            title_elem = article_info.find("ArticleTitle")
            title = title_elem.text if title_elem is not None else "Title unavailable"

            # Abstract - concatenate all AbstractText elements (handles structured abstracts)
            abstract_elem = article_info.find("Abstract")
            abstract_parts = []
            if abstract_elem is not None:
                for abs_text in abstract_elem.findall("AbstractText"):
                    label = abs_text.get("Label", "")
                    # Get all text content including tail text of sub-elements
                    text_content = "".join(abs_text.itertext()).strip()
                    if label and text_content:
                        abstract_parts.append(f"{label}: {text_content}")
                    elif text_content:
                        abstract_parts.append(text_content)

            abstract_text = " ".join(abstract_parts)

            # DOI
            doi = ""
            article_id_list = article_elem.find(".//ArticleIdList")
            if article_id_list is not None:
                for aid in article_id_list.findall("ArticleId"):
                    if aid.get("IdType") == "doi":
                        doi = aid.text or ""
                        break

            # Publication date
            pub_date = article_info.find(".//PubDate")
            date = "N/A"
            if pub_date is not None:
                year = pub_date.findtext("Year", "")
                month = pub_date.findtext("Month", "")
                day = pub_date.findtext("Day", "")
                date_parts = [p for p in [year, month, day] if p]
                date = "-".join(date_parts) if date_parts else "N/A"

            # Publication types
            pub_types = []
            pub_type_list = article_info.find("PublicationTypeList")
            if pub_type_list is not None:
                for pt in pub_type_list.findall("PublicationType"):
                    if pt.text:
                        pub_types.append(pt.text)

            # URL
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

            articles.append({
                "pmid": pmid,
                "title": title,
                "abstract_text": abstract_text,
                "doi": doi,
                "date": date,
                "url": url,
                "publication_types": pub_types,
            })

        except Exception as e:
            log.warning(f"Error parsing article: {e}")
            continue

    log.info(f"EFetch parsed {len(articles)} articles successfully")
    return articles


def search_systematic_reviews(query: str, limit: int = 10, max_year: int = None) -> List[Dict]:
    """
    Search PubMed for Systematic Reviews and Meta-Analyses matching the query.

    Uses a double filter strategy:
    1. systematic[sb] - PubMed's NLM-curated Systematic Review subset
    2. Publication type filter for "systematic review" and "meta-analysis"

    Args:
        query: The search query (medical terms).
        limit: Maximum number of results to return.
        max_year: Maximum publication year for the results.

    Returns:
        A list of dicts, each with keys:
        pmid, title, abstract_text, doi, date, url, publication_types
    """
    log.info(f"Searching systematic reviews for query: '{query}' (limit={limit}, max_year={max_year})")

    # Phase 1: ESearch → get PMIDs
    pmids = _esearch(query, limit, max_year=max_year)
    if not pmids:
        log.warning(f"No systematic reviews found for query: '{query}'")
        return []

    # Phase 2: EFetch → get article details
    articles = _efetch(pmids)

    # Filter out articles with empty abstracts
    articles_with_abstract = [a for a in articles if a.get("abstract_text", "").strip()]
    skipped = len(articles) - len(articles_with_abstract)
    if skipped > 0:
        log.info(f"Skipped {skipped} articles with empty abstracts")

    log.info(f"Returning {len(articles_with_abstract)} systematic reviews/meta-analyses")
    return articles_with_abstract


# Local test block
if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("TEST API PUBMED - SYSTEMATIC REVIEWS")
    print("=" * 50)

    test_query = "Nirmatrelvir COVID-19"
    results = search_systematic_reviews(test_query, limit=3)

    for i, article in enumerate(results):
        print(f"\n[{i + 1}] {article['title']}")
        print(f"    PMID:  {article['pmid']}")
        print(f"    DOI:   {article['doi']}")
        print(f"    Date:  {article['date']}")
        print(f"    URL:   {article['url']}")
        print(f"    Types: {', '.join(article['publication_types'])}")
        print(f"    Abstract: {article['abstract_text'][:200]}...")
