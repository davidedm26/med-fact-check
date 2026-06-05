import json
import sys
import os

# Ensure the src directory is the primary path to import local modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

# pyrefly: ignore [missing-import]
from tools.retrieve.download import download_documents
# pyrefly: ignore [missing-import]
from tools.retrieve.chunking import BiomedicalChunker, SourceMetadata

def main():
    print("Inizio test di chunking su tutte le sorgenti...")
    
    query = "COVID-19 vaccines"
    raw_documents = []
    sources = ["systematic_reviews", "knowledge_base", "literature"]
    
    for source in sources:
        print(f"Eseguo query '{query}' sulla sorgente: {source}...")
        try:
            result = download_documents.invoke({
                "sub_id": "test_01",
                "search_queries": [query],
                "target_source": source
            })
            docs = result.get("chunks", [])
            print(f"  -> Trovati {len(docs)} paragrafi grezzi in {source}.")
            raw_documents.extend(docs)
        except Exception as e:
            print(f"  -> Errore con {source}: {e}")
            
    print(f"\nIn totale sono stati scaricati {len(raw_documents)} frammenti grezzi da tutte le fonti.")
    
    if not raw_documents:
        print("Nessun documento trovato. Esco.")
        return

    # Inizializziamo il chunker
    chunker = BiomedicalChunker(chunk_size=300, overlap=50)
    
    # Raggruppiamo i chunk finali per articolo (usando il doc_id come chiave)
    articles_dict = {}
    
    for doc in raw_documents:
        text = doc.get("text", "").strip()
        raw_meta = doc.get("metadata", {})
        
        if not text:
            continue
            
        doc_id = raw_meta.get("id", "Sconosciuto")
        title = raw_meta.get("title", "Senza Titolo")
        
        # Estraiamo i chunk reali
        metadata_obj = SourceMetadata.from_dict(raw_meta)
        generated_chunks = chunker.chunk(text, metadata_obj)
        
        if doc_id not in articles_dict:
            articles_dict[doc_id] = {
                "id": doc_id,
                "title": title,
                "url": raw_meta.get("url", ""),
                "chunks": []
            }
            
        # Aggiungiamo i chunk alla lista di questo articolo
        for chunk in generated_chunks:
            articles_dict[doc_id]["chunks"].append({
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "chunk_length": len(chunk.text.split())
            })

    output_data = list(articles_dict.values())
    
    # Salviamo su file JSON in test/reports
    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    output_file = os.path.join(reports_dir, "test_chunking_output.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=4, ensure_ascii=False)
        
    print(f"\nTest completato! Risultati raggruppati per {len(output_data)} documenti unici.")
    print(f"Ispeziona il file {output_file} per vedere come sono stati frammentati.")

if __name__ == "__main__":
    main()
