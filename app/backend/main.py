import sys
import os
import asyncio
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel
import json

# Configurazione path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))


# pyrefly: ignore [missing-import]
from main_agent import FactAgent
# pyrefly: ignore [missing-import]
from utils.config import config

MOCK_MODE = os.getenv("MOCK_PIPELINE", "").lower() == "true" or config.get("mock_pipeline", False)


app = FastAPI(
    title="Med-Fact-Check API",
    description="API per fact-checking medico con streaming asincrono.",
    version="1.1.0"
)

# Inizializzazione Agent
try:
    agent = FactAgent()
except Exception as e:
    print(f"Errore inizializzazione FactAgent: {e}")
    agent = None

class ClaimRequest(BaseModel):
    claim: str

async def generate_mock_stream(claim: str):
    import asyncio
    import json
    
    # Attempt to fetch from MongoDB
    try:
        from utils.mongo_logger import _get_mongo_db
        db = _get_mongo_db()
        if db is not None:
            import random
            # Find the last 10 runs and pick one at random
            recent_runs = list(db["run_logs"].find().sort([("timestamp", -1)]).limit(10))
            if recent_runs:
                run = random.choice(recent_runs)
                nodes = list(db["node_logs"].find({"run_id": run["run_id"]}).sort("timestamp", 1))
                if nodes:
                    chunks_by_subclaim = {}
                    evaluation_phase_started = False
                    for n in nodes:
                        name = n.get("node_name", "")
                        out = n.get("output", {})
                        
                        if name == "claim_filter_node":
                            yield f"data: {json.dumps({'decompose': {'verifiable_subclaims': out.get('verifiable_subclaims', [])}})}\n\n"
                            await asyncio.sleep(3.6)
                            
                        elif name == "source_selector_node":
                            yield f"data: {json.dumps({'source_selector': {'subclaim_id': n.get('subclaim_id'), 'retrieval_source': out.get('retrieval_source', {})}})}\n\n"
                            await asyncio.sleep(2.7)
                            
                        elif name == "downloader_agent_node":
                            yield f"data: {json.dumps({'downloader_agent': {'subclaim_id': n.get('subclaim_id'), 'downloaded_chunks': out.get('downloaded_chunks', []), 'queries_by_source': out.get('queries_by_source', {}), 'download_stats': out.get('download_stats', {})}})}\n\n"
                            await asyncio.sleep(2.7)
                            
                        elif name == "hybrid_retriever_node":
                            sub_id = n.get("subclaim_id")
                            if sub_id:
                                chunks_by_subclaim[sub_id] = out.get("retrieved_chunks", [])
                            yield f"data: {json.dumps({'hybrid_retriever': {'subclaim_id': sub_id, 'retrieved_chunks': out.get('retrieved_chunks', [])}})}\n\n"
                            await asyncio.sleep(2.7)
                            
                        elif name == "veracity_node":
                            if not evaluation_phase_started:
                                yield f"data: {json.dumps({'verify_subclaim': {'evaluation_results': []}})}\n\n"
                                await asyncio.sleep(4.0)
                                evaluation_phase_started = True
                                
                            evals = out.get('evaluation_results', [])
                            for er in evals:
                                sub_id = er.get("subclaim_id")
                                if sub_id and sub_id in chunks_by_subclaim:
                                    er["retrieved_chunks"] = chunks_by_subclaim[sub_id]
                            yield f"data: {json.dumps({'verify_subclaim': {'evaluation_results': evals}})}\n\n"
                            await asyncio.sleep(3.6)
                            
                        elif name == "aggregate_node":
                            yield f"data: {json.dumps({'aggregate': {'final_verdict': out.get('final_verdict', {})}})}\n\n"
                            await asyncio.sleep(4.5)
                            
                    return  # Exit after successfully replaying from DB
    except Exception as e:
        print(f"Mock stream MongoDB fallback triggered: {e}")
        
    # Fallback to simulated data
    # 1. Decomposition stage
    subclaims = [
        f"The claim '{claim[:50]}...' is supported by active clinical trials.",
        f"The claim '{claim[:50]}...' has no adverse reactions in human cohorts."
    ]
    yield f"data: {json.dumps({'decompose': {'verifiable_subclaims': subclaims}})}\n\n"
    await asyncio.sleep(3.6)
    
    # 2. Source selector, downloader, retriever per ogni subclaim
    for idx, sc_text in enumerate(subclaims, 1):
        sub_id = f"sub_{idx:02d}"
        
        # Source Selection
        yield f"data: {json.dumps({'source_selector': {'subclaim_id': sub_id, 'retrieval_source': {'bioasq': 1, 'scifact': 1}}})}\n\n"
        await asyncio.sleep(2.7)
        
        # Downloader agent
        fake_queries = {"bioasq": [f"query bioasq {sc_text[:10]}"], "scifact": [f"query scifact {sc_text[:10]}"]}
        fake_stats = {
            "bioasq": {"documents_found": 5, "chunks_extracted": 12},
            "scifact": {"documents_found": 3, "chunks_extracted": 8}
        }
        yield f"data: {json.dumps({'downloader_agent': {'subclaim_id': sub_id, 'downloaded_chunks': [{'id': f'doc_{idx}_1', 'text': f'Simulated clinical evidence for {sc_text[:20]}', 'source': 'BioASQ'}], 'queries_by_source': fake_queries, 'download_stats': fake_stats}})}\n\n"
        await asyncio.sleep(2.7)
        
        # Hybrid retriever
        yield f"data: {json.dumps({'hybrid_retriever': {'subclaim_id': sub_id, 'retrieved_chunks': [{'id': f'doc_{idx}_1', 'text': f'Simulated clinical evidence for {sc_text[:20]}', 'source': 'BioASQ'}]}})}\n\n"
        await asyncio.sleep(2.7)

    # 3. Evaluation
    yield f"data: {json.dumps({'verify_subclaim': {'evaluation_results': []}})}\n\n"
    await asyncio.sleep(4.0)
    
    eval_results = []
    for idx, sc_text in enumerate(subclaims, 1):
        sub_id = f"sub_{idx:02d}"
        er = {
            "subclaim_id": sub_id,
            "subclaim": sc_text,
            "label": "supported",
            "confidence": 0.95,
            "justification": f"Simulated medical evaluation shows strong backing in scientific databases for: {sc_text}.",
            "selection_reasoning": f"Simulated medical evaluation shows strong backing in scientific databases for: {sc_text}.",
            "supporting_quotes": ["Simulated medical evaluation", "strong backing"],
            "refuting_quotes": [],
            "retrieved_chunks": [{"id": f"doc_{idx}_1", "text": f"Simulated clinical evidence for {sc_text[:20]}", "source": "BioASQ"}]
        }
        eval_results.append(er)
        yield f"data: {json.dumps({'verify_subclaim': {'evaluation_results': [er]}})}\n\n"
        await asyncio.sleep(3.6)

    # 4. Aggregation / Final verdict
    final_verdict = {
        "label": "supported",
        "confidence": 0.92,
        "aggregation_analysis": "The subclaims were consistently supported across multiple systematic reviews and clinical databases. No significant conflicting evidence was found.",
        "justification": f"After verifying '{claim[:80]}...', all subclaims were successfully verified against bioasq and scifact databases. There is consistent clinical evidence backing the claim, with no reported counter-arguments in standard literature.",
        "subclaim_breakdown": eval_results
    }
    yield f"data: {json.dumps({'aggregate': {'final_verdict': final_verdict}})}\n\n"


@app.post("/api/v1/fact-check-stream")
async def fact_check_stream(request: ClaimRequest):
    """
    Endpoint per lo streaming dei risultati del fact-check.
    Utilizza run_in_threadpool per evitare di bloccare l'event loop di FastAPI.
    """
    if MOCK_MODE:
        return StreamingResponse(generate_mock_stream(request.claim), media_type="text/event-stream")

    if agent is None:
        raise HTTPException(status_code=500, detail="FactAgent non disponibile.")

    async def generate():
        try:
            # Inizializziamo il generatore
            stream = agent.stream_claim(request.claim)
            
            while True:
                # Eseguiamo l'iterazione vera e propria nel thread pool per non bloccare l'event loop
                step = await run_in_threadpool(next, stream, None)
                if step is None:
                    break
                
                # Assicurati che lo step sia serializzabile in JSON
                yield f"data: {json.dumps(step)}\n\n"
                
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'status': 'failed'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/api/v1/fact-check")
async def fact_check(request: ClaimRequest):
    """
    Endpoint per esecuzione singola (batch).
    """
    if MOCK_MODE:
        mock_verdict = {
            "aggregate": {
                "final_verdict": {
                    "label": "supported",
                    "confidence": 0.92,
                    "justification": f"Mock batch verification for '{request.claim[:80]}...' succeeded."
                }
            }
        }
        return {"status": "success", "result": mock_verdict}

    if agent is None:
        raise HTTPException(status_code=500, detail="FactAgent non disponibile.")
        
    try:
        # Esecuzione asincrona del task pesante
        results = await run_in_threadpool(lambda: agent.process_claim(request.claim, verbose=False))
        
        if not results:
            raise HTTPException(status_code=500, detail="Nessun risultato prodotto.")
            
        final_state = results[-1]
        return {"status": "success", "result": final_state}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok", "agent_ready": agent is not None}