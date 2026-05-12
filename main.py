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
                "create_link": self.db.create_relationship,
                "control_home": self.handle_home_control,
                "read_document": self.handle_read_document,
                "delete_node": self.db.delete_node,
                "wipe_database": self.db.wipe_database
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
        # Grab the active nodes, then immediately clear the buffer
        active = self.db.last_accessed_uids.copy()
        self.db.last_accessed_uids.clear()
        
        return {
            "state": self.state,
            "last_error": self.last_error,
            "memory": self.history.get_context(),
            "active_nodes": active # Passed to frontend
        }
        
    def process_natural_language(self, user_input: str):
        """
        Phase 6, Step 3: The Agentic Loop.
        Currently compiles context and waits for the LLM bridge.
        """
        if self.state == "SAFE_MODE":
            return {"error": "System locked in SAFE_MODE."}

        # Internal Keyword Extraction (Heuristic for now)
        keywords = user_input.split()
        context = self.db.get_relevant_context(keywords)

        # Add message to short-term memory
        self.history.add_message("user", user_input)

        # Compile the Prompt for the future LLM
        payload = self.brain.compile_payload(user_input, context, self.history.get_context())
        
        logging.info(f"[*] Prompt Compiled for: {user_input}")
        return {"status": "ready_for_inference", "payload": payload}

    def process_tool_call(self, tool_name, arguments, override=False):
        if self.state == "SAFE_MODE":
            return {"status": "system_locked", "message": self.last_error}

        schema = get_tool_schema(tool_name)
        if schema.get("requires_confirmation", False) and not override:
            return {"status": "pending_authorization", "message": f"Confirm {tool_name}."}

        handler = self.dispatch_map.get(tool_name)
        if handler:
            try:
                result = handler(**arguments)
                self.error_streak = 0 # Reset error streak on success
                return {"status": "executed", "data": result}
            except Exception as e:
                self.error_streak += 1
                if self.error_streak >= 3: self.trip_breaker(str(e))   # Trip breaker after 3 consecutive errors
                return {"status": "error", "message": str(e)}

        return {"status": "error", "message": "No handler."}

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