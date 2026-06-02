import sys
import os
from pathlib import Path

# Add src to the Python path so we can import FactAgent
# We are in app/backend/main.py, so we go up two levels to reach the root, then into src
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
from main_agent import FactAgent

app = FastAPI(
    title="Med-Fact-Check API", 
    description="API for fact-checking medical claims.",
    version="1.0.0"
)

# Initialize the FactAgent on startup
try:
    agent = FactAgent()
except Exception as e:
    print(f"Failed to initialize FactAgent: {e}")
    agent = None

class ClaimRequest(BaseModel):
    claim: str

@app.post("/api/v1/fact-check")
async def fact_check(request: ClaimRequest):
    if agent is None:
        raise HTTPException(status_code=500, detail="FactAgent failed to initialize. Check API keys and configuration.")
        
    try:
        # process_claim returns a list of dictionaries representing steps.
        results = agent.process_claim(request.claim, verbose=False)
        
        if not results:
             raise HTTPException(status_code=500, detail="Pipeline returned no results.")
        
        # We return the last element which represents the final state
        final_state = results[-1]
        
        # Extract final_verdict
        verdict = None
        if "aggregate" in final_state and "final_verdict" in final_state["aggregate"]:
            verdict = final_state["aggregate"]["final_verdict"]
        elif "final_verdict" in final_state:
            verdict = final_state["final_verdict"]
            
        if verdict:
            return {"status": "success", "verdict": verdict}
        else:
            return {"status": "success", "raw_result": final_state}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/fact-check-stream")
async def fact_check_stream(request: ClaimRequest):
    if agent is None:
        raise HTTPException(status_code=500, detail="FactAgent failed to initialize. Check API keys and configuration.")
        
    def generate():
        try:
            for step in agent.stream_claim(request.claim):
                yield f"data: {json.dumps(step)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/health")
async def health_check():
    return {"status": "ok", "agent_initialized": agent is not None}
