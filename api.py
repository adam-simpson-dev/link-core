from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from main import LinkCore
import logging

# Initialize logging to be consistent with main.py
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

app = FastAPI(title="LINK-CORE API")
core = LinkCore()

class ToolCall(BaseModel):
    tool_name: str
    arguments: dict

@app.get("/health")
async def health():
    return {"status": "online"}

@app.post("/command")
async def execute_command(call: ToolCall):
    logging.info(f"API Request: {call.tool_name}")
    result = core.process_tool_call(call.tool_name, call.arguments)
    
    if result is False:
        raise HTTPException(status_code=400, detail="Tool execution failed.")
    
    return {"status": "success", "result": result}

@app.on_event("shutdown")
def shutdown():
    core.shutdown()