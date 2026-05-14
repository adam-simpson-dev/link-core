from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
import logging
from main import LinkCore

# Standardized logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("LINK-API")

# Log Silencer
class FilterHeartbeatLogs(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        # Drop the log if it contains either of the high-frequency polling endpoints
        return msg.find("/api/telemetry") == -1 and msg.find("/api/graph") == -1

logging.getLogger("uvicorn.access").addFilter(FilterHeartbeatLogs())

# Lifespan management: The modern replacement for on_event
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[*] LINK-CORE Service initializing...")
    yield
    logger.info("[*] LINK-CORE Service shutting down...")
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
    return core.db.get_node_data(uid)

@app.get("/api/graph")
async def get_graph():
    """Feeds GUI Web Box."""
    nodes_raw = core.db.get_all_nodes()
    edges_raw = core.db.get_all_edges()
    
    nodes = [{"id": n[0], "name": n[2], "label": n[1]} for n in nodes_raw]
    links = [{"source": e[1], "target": e[2], "relationship": e[3]} for e in edges_raw]
    
    return {"nodes": nodes, "links": links}

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    import os
    file_path = "static/favicon.ico"
    if os.path.exists(file_path):
        # Force the correct MIME type for .ico files
        return FileResponse(file_path, media_type="image/x-icon")
    return Response(status_code=204)

@app.post("/command")
async def execute_command(call: CommandRequest):
    result = core.process_tool_call(call.tool_name, call.arguments)
    return {"status": "success", "result": result}

@app.post("/api/interact")
async def interact(request: ChatRequest):
    return {"status": "success", "result": core.process_natural_language(request.text)}