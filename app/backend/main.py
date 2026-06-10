import sys
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

@app.post("/api/v1/fact-check-stream")
async def fact_check_stream(request: ClaimRequest):
    """
    Endpoint per lo streaming dei risultati del fact-check.
    Utilizza run_in_threadpool per evitare di bloccare l'event loop di FastAPI.
    """
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