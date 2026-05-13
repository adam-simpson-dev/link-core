import logging
import json
import os
from brain import MessageHistory, PromptManager
from database import DatabaseManager
from hass_client import HassClient
from tools import get_tool_schema
from inference import InferenceEngine

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
        self.history = MessageHistory(max_turns=20)
        self.brain = PromptManager()

        try:
            self.db = DatabaseManager()
            self.hass = HassClient()
            self.ai = InferenceEngine()
            # Map JSON tool names to their handler functions for dynamic dispatching
            self.dispatch_map = {
                "get_context": self.db.get_relevant_context,
                "update_memory": self.db.upsert_lore,
                "create_link": self.db.create_relationship,
                "control_home": self.handle_home_control,
                "read_document": self.handle_read_document,
                "delete_node": self.db.delete_node,
                "wipe_database": self.db.wipe_database,
                "batch_update_lore": self.db.batch_update_lore
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
        """Feeds the UI. Consumes the data wake to prevent sticky pings."""
        
        # Capture the current radar targets
        current_wake = list(self.db.last_accessed_uids)
        
        # Instantly flush the backend buffer
        self.db.last_accessed_uids.clear()
        
        # Return your standard telemetry payload. Ensure the names match what the frontend expects.
        return {
            "state": self.state,
            "last_error": self.last_error,
            "memory": self.history.get_context(),
            "last_accessed_uids": current_wake # Passed to frontend
        }
        
    def process_natural_language(self, user_input: str):
        """The ReAct (Reasoning & Acting) Loop."""
        if self.state == "SAFE_MODE": return "System locked."

        # Log user intent
        self.history.add_message("user", user_input)
        
        iteration = 0
        max_iterations = 5 # Circuit breaker to prevent infinite loop token drain

        while iteration < max_iterations:
            iteration += 1
            decision = self.ai.think(self.brain.get_system_prompt(self.state, self.last_error), self.history.get_context())
            
            if decision["type"] == "error":
                logging.error(f"[!] INFERENCE FATAL: {decision['content']}")
                return "API ERROR. Check core logs."
                
            elif decision["type"] == "text":
                self.history.add_message("model", decision["content"])
                return decision["content"]
                
            elif decision["type"] == "tool_call":
                t_name, t_args = decision["tool_name"], decision["arguments"]
                
                # Standardized tool logging
                self.history.add_message("model", "", tool_calls=[decision])
                
                result = self.process_tool_call(t_name, t_args)
                obs_data = result.get("data", result.get("message", "Executed."))
                
                # Feed the observation back into the loop
                self.history.add_message("system", str(obs_data), tool_results=[{"tool_name": t_name, "content": obs_data}])

        self.trip_breaker("LLM Recursive Loop Detected.")
        return "Maximum iterations reached."

    def process_tool_call(self, tool_name: str, arguments: dict):
        if self.state == "SAFE_MODE":
            return {"status": "system_locked", "message": self.last_error}

        handler = self.dispatch_map.get(tool_name)
        if handler:
            try:
                result = handler(**arguments)
                self.error_streak = 0
                return {"status": "executed", "data": result}
            except Exception as e:
                self.error_streak += 1
                if self.error_streak >= 3: self.trip_breaker(str(e))
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
        """Graceful termination of database links."""
        logging.info("[!] LINK-CORE Shutting down.")
        if hasattr(self, 'db'):
            self.db.close()