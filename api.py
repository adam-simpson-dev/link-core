from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from contextlib import asynccontextmanager
import logging
from core_logger import setup_core_logger
from main import LinkCore
import asyncio
import subprocess
from datetime import datetime, timedelta

setup_core_logger()
logger = logging.getLogger("LINK-API")

async def run_janitor_schedule():
    """Background loop to fire the Janitor subprocess at 03:00 daily."""
    while True:
        now = datetime.now()
        target = now.replace(hour=3, minute=0, second=0, microsecond=0)
        
        # If we are already past 3 AM today, schedule for tomorrow
        if now >= target:
            target += timedelta(days=1)
            
        sleep_seconds = (target - now).total_seconds()
        logger.info(f"[*] Janitor daemon entering standby. Waking at {target.strftime('%H:%M:%S')} (in {int(sleep_seconds)}s).")
        
        try:
            await asyncio.sleep(sleep_seconds)
            logger.info("[*] Waking Nocturnal Janitor subprocess...")
            # Execute completely isolated from the main API thread
            subprocess.run(["python3", "janitor.py"], check=True)
        except asyncio.CancelledError:
            logger.info("[!] Janitor schedule interrupted by system shutdown.")
            break
        except Exception as e:
            logger.error(f"[!] Janitor execution failed: {e}")

# Lifespan management: The modern replacement for on_event
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[*] LINK-CORE Service initializing...")
    # Spawn the localized background task
    janitor_task = asyncio.create_task(run_janitor_schedule())
    yield
    logger.info("[*] LINK-CORE Service shutting down...")
    janitor_task.cancel()
    core.shutdown()

app = FastAPI(title="LINK-CORE API", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
core = LinkCore()

class CommandRequest(BaseModel):
    tool_name: str
    arguments: dict

class ChatRequest(BaseModel):
    text: str

@app.get("/")
async def read_index():
    """Returns the dashboard UI."""
    return FileResponse('static/index.html')

@app.get("/health")
async def health():
    return {
        "status": core.state,
        "last_error": core.last_error,
        "version": "1.2.0"
    }

@app.get("/logs", include_in_schema=False)
async def view_logs():
    """Serves the backend log file directly to the browser as plain text."""
    import os
    file_path = "link-core.log"
    if os.path.exists(file_path):
        # 'text/plain' forces the browser to display it rather than triggering a download
        return FileResponse(file_path, media_type="text/plain")
    return {"error": "Log file not found or has not been generated yet."}

@app.get("/api/telemetry")
async def get_telemetry():
    """Feeds GUI State Box and Memory Box."""
    return core.get_system_telemetry()

@app.get("/api/node/{uid}")
async def get_node_details(uid: str):
    """Feeds GUI Inspector box."""
    data = core.db.get_node_data(uid)
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
    return data

@app.get("/api/graph")
async def get_graph():
    """Feeds GUI Web Box."""
    nodes_raw = core.db.get_all_nodes()
    edges_raw = core.db.get_all_edges()
    
    nodes = [{"id": n[0], "name": n[2], "label": n[1]} for n in nodes_raw]
    links = [{"source": e[1], "target": e[2], "relationship": e[3]} for e in edges_raw]
    
    return {"nodes": nodes, "links": links}

@app.get("/favicon.png", include_in_schema=False)
async def favicon():
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "static", "favicon.png")
    
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="image/png")
    return Response(status_code=204)

@app.post("/command")
async def execute_command(call: CommandRequest):
    result = core.process_tool_call(call.tool_name, call.arguments)
    return {"status": "success", "result": result}

@app.post("/api/interact")
async def interact(request: ChatRequest):
    return {"status": "success", "result": core.process_natural_language(request.text)}