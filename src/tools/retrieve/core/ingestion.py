import json
import os
from typing import List

from tools.retrieve.core.connectors.europe_pmc_api import search_articles, fetch_full_text_xml
from tools.retrieve.core.connectors.clinical_trials_api import search_trials  # kept for reference
from tools.retrieve.core.connectors.uniprot_api import search_protein
from tools.retrieve.core.connectors.pubmed_api import search_systematic_reviews


from tools.retrieve.core.text_cleaner import clean_europe_pmc_xml, format_clinical_trial, format_uniprot, format_systematic_review

from utils.logger import get_logger
from utils.config import config

try:
    from tqdm.auto import tqdm
except ImportError:  # pragma: no cover - optional dependency fallback
    def tqdm(iterable, **kwargs):
        return iterable

log = get_logger("IngestionNode")

class IngestionNode:
    def __init__(self):
        # Ensure the data/ folder exists in the project
        os.makedirs("data", exist_ok=True)
        self.last_stats = {}
        log.info("Initialized. Ready to download data.")

    def prepare_data(self, sub_id: str, search_queries: List[str], target_source: str) -> tuple[List[dict], dict]:
        log.info(f"Task for {sub_id}: {search_queries} -> Destination: {target_source.upper()}")
        
        target = target_source.lower()
        raw_chunks = []
        stats = {
            "sub_id": sub_id,
            "target_source": target,
            "queries_total": len(search_queries),
            "queries_processed": 0,
            "documents_found": 0,
            "chunks_extracted": 0,
            "duplicates_removed": 0,
        }

        if target == "literature":
            stats.update({
                "articles_download_attempted": 0,
                "articles_downloaded_success": 0,
                "articles_download_failed": 0,
            })

        from collections import Counter
        query_counts = Counter(search_queries)

        # 1. Loop through each unique query
        for query_index, (single_query, count) in enumerate(
            tqdm(query_counts.items(), desc=f"[{sub_id} | {target.upper()}] queries", unit="query"),
            1,
        ):
            query_tag = f"[{sub_id} | {target.upper()} | query_{query_index}]"
            log.info(f"{query_tag}  Searching data for query: '{single_query}' (Count: {count})")
            stats["queries_processed"] += count
            
            base_limit = config.get("retrieval.max_results_per_query", 5)
            api_limit = base_limit * count
            
            # Read max_year dynamically based on the current dataset
            current_dataset = config.get("current_dataset", "scifact")
            max_year = config.get(f"retrieval.knowledge_cutoff_year.{current_dataset}")
            
            if target == "systematic_reviews":
                # Fetch 10x more results because reviews are not split into multiple chunks
                extracted_reviews = search_systematic_reviews(query=single_query, limit=api_limit * 10, max_year=max_year)
                stats["documents_found"] += len(extracted_reviews)
                for review in extracted_reviews:
                    raw_chunks.append({
                        "text": format_systematic_review(review),
                        "metadata": {
                            "id": review.get("pmid"), "title": review.get("title"), "type": "Systematic Review",
                            "date": review.get("date"), "url": review.get("url"),
                            "extra_info": {"doi": review.get("doi"), "publication_types": review.get("publication_types", [])}
                        }
                    })

            elif target == "knowledge_base":
                # Fetch 10x more results because proteins are not split into multiple chunks
                extracted_proteins = search_protein(query=single_query, limit=api_limit * 10)
                stats["documents_found"] += len(extracted_proteins)
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
                articles = search_articles(query=single_query, limit=api_limit, max_year=max_year)
                stats["documents_found"] += len(articles)
                for article in tqdm(articles, desc=f"[{sub_id} | {target.upper()} | query_{query_index}] articles", unit="article", leave=False):
                    stats["articles_download_attempted"] += 1
                    pmcid = article.get("pmcid")
                    if not pmcid:
                        stats["articles_download_failed"] += 1
                        continue
                    raw_xml = fetch_full_text_xml(pmcid)
                    if raw_xml:
                        stats["articles_downloaded_success"] += 1
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
                        abstract = article.get("abstract")
                        if abstract:
                            log.debug(f"XML not found for {pmcid}, falling back to abstract.")
                            stats["articles_downloaded_success"] += 1
                            raw_chunks.append({
                                "text": f"ABSTRACT: {abstract}",
                                "metadata": {
                                    "id": article.get("pmid"), "title": article.get("title"), "type": "Scientific Literature Abstract",
                                    "date": article.get("date"),
                                    "url": f"https://doi.org/{article.get('doi')}" if article.get("doi") else "",
                                    "extra_info": {"doi": article.get("doi"), "is_abstract_fallback": True}
                                }
                            })
                        else:
                            stats["articles_download_failed"] += 1
            else:
                log.error(f"Source '{target}' not supported.")
                continue

        # 2. Smart deduplication
        unique_chunks = {}
        for chunk in raw_chunks:
            # Create a unique key using ID + first 50 characters of the text
            unique_key = f"{chunk['metadata'].get('id', 'no_id')}_{hash(chunk['text'][:50])}"
            unique_chunks[unique_key] = chunk
            
        final_chunks = list(unique_chunks.values())
        stats["chunks_extracted"] = len(raw_chunks)
        stats["duplicates_removed"] = max(0, len(raw_chunks) - len(final_chunks))
        self.last_stats = stats

        # 3. Log extraction summary without saving to disk
        if not final_chunks:
            log.warning(f"No data found for '{sub_id}'.")

        if target == "literature":
            log.info(
                f"[{sub_id} | {target.upper()}] Stats: "
                f"queries={stats['queries_processed']}/{stats['queries_total']}, "
                f"documents_found={stats['documents_found']}, "
                f"download_attempted={stats['articles_download_attempted']}, "
                f"downloaded_success={stats['articles_downloaded_success']}, "
                f"download_failed={stats['articles_download_failed']}, "
                f"chunks_raw={stats['chunks_extracted']}, "
                f"duplicates_removed={stats['duplicates_removed']}, "
                f"final_chunks={len(final_chunks)}"
            )
        else:
            log.info(
                f"[{sub_id} | {target.upper()}] Stats: "
                f"queries={stats['queries_processed']}/{stats['queries_total']}, "
                f"documents_found={stats['documents_found']}, "
                f"chunks_raw={stats['chunks_extracted']}, "
                f"duplicates_removed={stats['duplicates_removed']}, "
                f"final_chunks={len(final_chunks)}"
            )

        return final_chunks, stats