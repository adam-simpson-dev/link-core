import logging
import json
import os
from brain import MessageHistory, PromptManager
from database import DatabaseManager
from hass_client import HassClient
from tools import get_tool_schema

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("link-core.log"),
        logging.StreamHandler()
    ]
)

class LinkCore:
    """
    The Orchestrator: Bridges LORE (Memory) and HASS (Action) 
    via a dynamic Tool Dispatcher.
    """
    def __init__(self):
        # Circuit Breaker
        self.state = "NOMINAL"
        self.last_error = None
        self.error_streak = 0
        
        # Neural Pathways
        self.history = MessageHistory(max_turns=10)
        self.brain = PromptManager()

        try:
            self.db = DatabaseManager()
            self.hass = HassClient()
            # Map JSON tool names to their handler functions for dynamic dispatching
            self.dispatch_map = {
                "get_context": self.db.get_relevant_context,
                "update_memory": self.db.upsert_lore,
                "control_home": self.handle_home_control,
                "read_document": self.handle_read_document,
                "delete_node": self.db.delete_node
            }
            logging.info("[*] LINK-CORE Dispatcher Active. Systems Nominal.")
        except Exception as e:
            # Catch boot failures (e.g., corrupted DB, missing ENV vars)
            self.trip_breaker(f"Boot sequence failed: {str(e)}")

    def trip_breaker(self, reason: str):
        """Locks the core to prevent cascading failures or crash loops."""
        self.state = "SAFE_MODE"
        self.last_error = reason
        logging.critical(f"[!] CIRCUIT BREAKER TRIPPED. System Locked. Reason: {reason}")

    def get_system_telemetry(self):
        """Feeds the UI State and Memory boxes."""
        return {
            "state": self.state,
            "last_error": self.last_error,
            "memory": self.history.get_history()
        }

    def process_tool_call(self, tool_name, arguments, override=False):
        # Check System State before processing any tool calls to prevent damage or infinite loops.
        if self.state == "SAFE_MODE":
            return {
                "status": "system_locked",
                "message": f"Core is in SAFE MODE. Reason: {self.last_error}. Manual intervention required."
            }

        schema = get_tool_schema(tool_name)
        # If the tool is unregistered, we return an error immediately to avoid silent failures or unintended consequences.
        if not schema:
            logging.warning(f"[!] Attempted to call unregistered tool: {tool_name}")
            return {"status": "error", "message": f"Tool {tool_name} not found."}

        # Check Security Handshake if the tool requires confirmation and override is not set
        if schema.get("requires_confirmation", False) and not override:
            return {
                "status": "pending_authorization",
                "tool_name": tool_name,
                "arguments": arguments,
                "message": f"Execution of {tool_name} requires explicit human confirmation."
            }

        # Execution & Monitoring
        handler = self.dispatch_map.get(tool_name)
        if handler:
            try:
                result = handler(**arguments)
                self.error_streak = 0 # Reset error streak on successful execution
                return {"status": "executed", "data": result}
            except Exception as e:
                self.error_streak += 1
                if self.error_streak >= 3: # Threshold for consecutive failures before tripping the breaker
                    self.trip_breaker(f"Consecutive failures: {str(e)}")
                return {"status": "error", "message": str(e)}
        
        return {"status": "error", "message": "Handler missing."}

    # --- Tool Handlers ---
    # These are kept separate from the dispatch map to allow for more complex logic, error handling, or multi-step processes that might be required for certain tools.

    def handle_read_document(self, file_path):
        if not os.path.exists(file_path):
            return f"Error: File at {file_path} not found."
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def handle_home_control(self, domain, service, entity_id, **kwargs):
        service_data = {"entity_id": entity_id}
        service_data.update(kwargs) # This catches brightness, color_name, etc.
        logging.info(f"Refined HA Call: {domain}.{service} -> {service_data}")
        return self.hass.call_service(domain, service, service_data)

    def shutdown(self):
        self.db.close()
        logging.info("[*] LINK-CORE Offline.")