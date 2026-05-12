from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager
import logging
from main import LinkCore

# Standardized logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("LINK-API")

# Lifespan management: The modern replacement for on_event
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[*] LINK-CORE Service initializing...")
    yield
    logger.info("[*] LINK-CORE Service shutting down...")
    core.shutdown()

app = FastAPI(title="LINK-CORE API", lifespan=lifespan)
core = LinkCore()

class CommandRequest(BaseModel):
    tool_name: str
    arguments: dict
    override: bool = False

class NaturalLanguageRequest(BaseModel):
    text: str

@app.get("/health")
async def health():
    return {
        "status": core.state,
        "last_error": core.last_error,
        "version": "1.2.0"
    }

@app.get("/api/telemetry")
async def get_telemetry():
    """Feeds GUI State Box and Memory Box."""
    return core.get_system_telemetry()

@app.get("/api/graph")
async def get_graph():
    """Feeds GUI Web Box."""
    nodes_raw = core.db.get_all_nodes()
    edges_raw = core.db.get_all_edges()
    
    nodes = [{"id": n[0], "name": n[2], "label": n[1]} for n in nodes_raw]
    links = [{"source": e[1], "target": e[2], "relationship": e[3]} for e in edges_raw]
    
    return {"nodes": nodes, "links": links}

@app.post("/command")
async def execute_command(call: CommandRequest):
    """Direct tool call endpoint with multi-tier error catching."""
    try:
        # Dispatch to Orchestrator
        result = core.process_tool_call(
            call.tool_name, 
            call.arguments, 
            override=call.override
        )
        
        # Catch Logic Errors: If the Orchestrator reports an error state
        if isinstance(result, dict) and result.get("status") == "error":
            logger.error(f"Tool Error [{call.tool_name}]: {result.get('message')}")
            raise HTTPException(status_code=400, detail=result.get("message"))
            
        # Catch Lockouts: If the Circuit Breaker is active
        if isinstance(result, dict) and result.get("status") == "system_locked":
            raise HTTPException(status_code=503, detail=f"System in SAFE MODE: {result.get('message')}")

        return {"status": "success", "result": result}

    except HTTPException:
        raise  # Re-raise FastAPI-specific errors
    except Exception as e:
        # Catch Engine Crashes: Handle unhandled exceptions in LinkCore
        logger.error(f"CRITICAL ENGINE FAILURE: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Orchestration Error")