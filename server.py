import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import load_dotenv
import uvicorn

from models import Agent, CallState
from engine import DataStore
from plivo_provider import PlivoProvider
from main import SmartDialer

load_dotenv()

# Global state
store = DataStore()
# Pre-populate some agents for testing
initial_agents = int(os.getenv("INITIAL_AGENTS", "10"))
for i in range(initial_agents):
    store.agents[f"A{i}"] = Agent(id=f"A{i}")

# A queue of phone numbers to dial. 
# In a real app, this would be fetched from the database based on campaign logic.
leads_queue = ["+15550000001", "+15550000002"]

provider = PlivoProvider()
dialer = SmartDialer(store, provider, predictive=True)

# Background task to continuously tick the dialer
async def dialer_loop():
    print("Started Dialer Background Loop")
    while True:
        try:
            # We pass the queue to the dialer. It will pop leads as needed based on pacing.
            if leads_queue:
                await dialer.tick(leads_queue)
            else:
                # If no leads, just sweep
                await dialer.sweeper.sweep()
        except Exception as e:
            print(f"Error in dialer tick: {e}")
            
        tick_interval = float(os.getenv("DIALER_TICK_INTERVAL", "1.0"))
        await asyncio.sleep(tick_interval)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the background loop when the server starts
    task = asyncio.create_task(dialer_loop())
    yield
    # Cleanup on shutdown
    task.cancel()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook/plivo")
async def plivo_webhook(request: Request):
    """
    Endpoint for Plivo to send call status updates.
    """
    # Plivo sends form data for webhooks
    data = await request.form()
    
    # Extract Plivo fields
    call_uuid = data.get("CallUUID") # Plivo's remote ID
    call_status = data.get("CallStatus") # ringing, in-progress, completed, failed, busy, no-answer
    
    # We passed call_id in the URL query string when initiating the call
    internal_call_id = request.query_params.get("call_id")
    
    print(f"[WEBHOOK] Received status '{call_status}' for internal call '{internal_call_id}' (Remote: {call_uuid})")
    
    # Mapping Plivo states to our CallState
    state_mapping = {
        "ringing": CallState.RINGING,
        "in-progress": CallState.ANSWERED, # Answered and connected
        "completed": CallState.COMPLETED,
        "failed": CallState.FAILED,
        "busy": CallState.FAILED,
        "no-answer": CallState.COMPLETED # They didn't answer, so it's done
    }
    
    target_state = state_mapping.get(call_status)
    
    if target_state and internal_call_id:
        # Push the event into our state machine!
        await dialer.handle_telecom_event(internal_call_id, target_state, call_uuid)
        
    return {"status": "ok"}

if __name__ == "__main__":
    host = os.getenv("SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("SERVER_PORT", "8000"))
    uvicorn.run("server:app", host=host, port=port, reload=True)
