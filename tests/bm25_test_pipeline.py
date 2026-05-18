import sys
import os
import json
import logging
import time
import glob
from dotenv import load_dotenv  

# Ensure Python can see the 'src' package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import modular components
from src.agents.retriever_agent import RetrieverAgent
from src.tools.retrieve.ingestion import IngestionNode
from src.tools.retrieve.bm25_search import extract_relevant_paragraphs

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

def clear_temp_files():
    """Clean temporary files from data/ and the repository root."""
    print("🧹 Cleaning temporary files...")
    files_to_remove = glob.glob("data/export_*.json") + glob.glob("evidence_package*.json")
    removed_count = 0
    for file_path in files_to_remove:
        try:
            os.remove(file_path)
            removed_count += 1
        except Exception as e:
            print(f"Unable to delete {file_path}: {e}")
    if removed_count > 0:
        print(f"✨ Cleanup completed: removed {removed_count} old files.\n")

"""
mock_decomposer_json = {

    "original_claim": "Il Paxlovid (Nirmatrelvir) ha fallito la Fase 3, e la Vitamina C previene la mortalità da COVID-19, agendo sulla proteina ACE2.",
    "sub_claims": [
        {
            "sub_id": "sc_01",
            "text": "Il Paxlovid (Nirmatrelvir) ha fallito i test clinici di Fase 3."
        },
        {
            "sub_id": "sc_02",
            "text": "La Vitamina C previene la mortalità da COVID-19."
        },
        {
            "sub_id": "sc_03",
            "text": "La Vitamina C agisce direttamente sulla proteina ACE2."
        }
    ]
}


"""
mock_decomposer_json = {
    "original_claim": "Pfizer ha interrotto gli studi sul Nirmatrelvir per inefficacia, mentre è ampiamente dimostrato che dosi massicce di Acido Ascorbico azzerano i decessi nei pazienti ricoverati bloccando fisicamente il recettore umano ACE2.",
    "sub_claims": [
        {
            "sub_id": "sc_01",
            "text": "La sperimentazione sul farmaco Nirmatrelvir è stata interrotta anticipatamente a causa della sua inefficacia sui pazienti."
        },
        {
            "sub_id": "sc_02",
            "text": "La somministrazione di Acido Ascorbico azzera il rischio di mortalità nei pazienti ospedalizzati per COVID-19."
        },
        {
            "sub_id": "sc_03",
            "text": "L'Acido Ascorbico impedisce l'infezione virale legandosi e bloccando fisicamente il recettore cellulare ACE2."
        }
    ]
}
"""
mock_decomposer_json = {
    "original_claim": "mRNA vaccines alter human DNA and have been linked to a surge in myocarditis deaths in athletes",
    "sub_claims": [
        {
            "sub_id": "sc_01",
            "text": "I vaccini a mRNA alterano il DNA umano."
        },
        {
            "sub_id": "sc_02",
            "text": "I vaccini a mRNA sono collegati a un'ondata di morti per miocardite negli atleti."
        }
    ]
}
"""


def run_test_pipeline():
    clear_temp_files()

    print("\n" + "="*60)
    print("🚀 START EVIDENCE RETRIEVAL PIPELINE (Modular)")
    print("="*60)
    
    # --- 2. Load environment variables ---
    load_dotenv() 
    
    HF_TOKEN = os.getenv("HF_TOKEN")
    if not HF_TOKEN:
        raise ValueError("❌ ERROR: Environment variable 'HF_TOKEN' not found! Check the .env file in the project root.")
    
    # 1. Inizialization of modular components
    router_agent = RetrieverAgent(hf_token=HF_TOKEN)
    ingestion_node = IngestionNode()
    
    # This is the package that you (and your BM25) will produce
    final_evidence_package = {
        "original_claim": mock_decomposer_json["original_claim"],
        "evidences": []
    }
    
    # This is the core file to pass to Member 3
    query_mapping = []

    for sub_claim in mock_decomposer_json["sub_claims"]:
        sc_id = sub_claim["sub_id"]
        sc_text = sub_claim["text"]
        
        print(f"\n⚙️ Analyzing Sub-Claim [{sc_id}]: '{sc_text}'")
        
        # --- PHASE A: The agent generates queries ---
        print("   🧠 Requesting routing from Llama-3-8B...")
        llm_decision = router_agent.generate_query(sc_text)
        
        destination = llm_decision.get("target_source", "literature")
        query_list = llm_decision.get("search_queries", [sc_text])
        
        print(f"   🎯 Source: {destination.upper()} | Query: {query_list}")
        
        # Save the query map for Member 3
        query_mapping.append({
            "sub_id": sc_id,
            "target_source": destination,
            "queries_used": query_list
        })
        
        # --- PHASE B: Ingestion (Data download) ---
        print("   📥 Starting data download...")
        downloaded_chunks = ingestion_node.prepare_data(sc_id, query_list, destination)
        
        # --- PHASE C: BM25 (Final extraction) ---
        retrieved_evidences = []
        if downloaded_chunks:
            print(f"   🔎 Running BM25 on a pool of {len(downloaded_chunks)} chunks...")
            mega_query = " ".join(query_list) # Combine synonyms to strengthen BM25
            
            best_chunks = extract_relevant_paragraphs(
                query=mega_query, 
                paragraphs_with_metadata=downloaded_chunks, 
                top_k=5
            )
            
            # Format for final output
            for c in best_chunks:
                retrieved_evidences.append({
                    "text_content": c["text"],
                    "source_metadata": c["metadata"]
                })
        else:
            retrieved_evidences.append({
                "text_content": "No evidence found.",
                "source_metadata": {}
            })
            
        final_evidence_package["evidences"].append({
            "sub_id": sc_id,
            "target_source": destination,
            "queries_used": query_list,
            "retrieved_texts": retrieved_evidences
        })
        
        time.sleep(2) # Courtesy pause for the APIs

    print("\n" + "="*60)
    print("📦 FINAL PACKAGE AND EXPORT COMPLETED")
    print("="*60)
    
    # 1. Save your BM25 package
    with open("evidences_bm25.json", "w", encoding="utf-8") as f:
        json.dump(final_evidence_package, f, indent=2, ensure_ascii=False)
        
    # 2. Save the query map for Member 3 (inside the data folder)
    with open("data/member3_query_map.json", "w", encoding="utf-8") as f:
        json.dump(query_mapping, f, indent=2, ensure_ascii=False)
        
    print(f"💾 Your BM25 package is saved to: 'evidences_bm25.json'")
    print(f"💾 Raw data for your colleague is ready in the 'data/' folder!")

if __name__ == "__main__":
    run_test_pipeline()