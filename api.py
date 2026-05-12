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
    logger.info("[*] LINK-CORE Service warming up...")
    yield
    logger.info("[*] LINK-CORE Service shutting down...")
    core.shutdown()

app = FastAPI(title="LINK-CORE API", lifespan=lifespan)
core = LinkCore()

class ToolCall(BaseModel):
    tool_name: str
    arguments: dict
    override: bool = False

@app.get("/health")
async def health():
    return {
        "status": core.state,
        "last_error": core.last_error,
        "version": "1.2.0"
    }

@app.post("/command")
async def execute_command(call: ToolCall):
    logger.info(f"[*] API Command: {call.tool_name} | Override: {call.override}")
    
    try:
        result = core.process_tool_call(
            call.tool_name, 
            call.arguments, 
            override=call.override
        )
        
        # Detect logical failures returned by the orchestrator
        if isinstance(result, dict) and result.get("status") == "error":
            raise HTTPException(
                status_code=400, 
                detail=result.get("message", "Tool execution failed.")
            )

        # Fallback for legacy handlers returning raw booleans
        if result is False:
            raise HTTPException(
                status_code=400, 
                detail="The requested action failed or returned an invalid state."
            )

        return {"status": "success", "result": result}

    except HTTPException:
        raise # Re-raise FastAPI-specific exceptions
    except Exception as e:
        logger.error(f"[!] Execution Crash: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Internal Engine Error: {str(e)}"
        )