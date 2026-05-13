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
        """The ReAct (Reasoning & Acting) Loop."""
        if self.state == "SAFE_MODE":
            return "System locked in SAFE_MODE."

        # Log user intent
        self.history.add_message("user", user_input)
        
        iteration = 0
        max_iterations = 5 # Circuit breaker to prevent infinite loop token drain

        while iteration < max_iterations:
            iteration += 1
            
            # Get intrinsic state
            sys_prompt = self.brain.get_system_prompt(self.state, self.last_error)
            
            # Query the LLM
            decision = self.ai.think(sys_prompt, self.history.get_context())
            
            # Handle Error
            if decision["type"] == "error":
                full_error = decision["content"]
                
                # Write the formatted trace to backend logs
                logging.error(f"[!] INFERENCE FATAL: {full_error}")
                
                # Feed a sanitized, truncated string to the UI and Memory
                short_msg = "API LIMIT OR CONNECTION FAILURE. See core system logs for trace."
                self.history.add_message("system", short_msg)
                return short_msg
                
            # Handle Final Text Response
            elif decision["type"] == "text":
                self.history.add_message("model", decision["content"])
                return decision["content"]
                
            # Handle Tool Execution
            elif decision["type"] == "tool_call":
                t_name = decision["tool_name"]
                t_args = decision["arguments"]
                
                logging.info(f"[*] AI executing tool: {t_name} with args {t_args}")
                
                # Log the AI's request before executing
                self.history.history.append({
                    "role": "model",
                    "tool_name": t_name,
                    "arguments": t_args
                })
                
                # Execute locally
                result = self.process_tool_call(t_name, t_args)
                
                # Format the observation
                obs_data = result.get("data", result.get("message", "Executed."))
                
                # Log the system's observation
                self.history.history.append({
                    "role": "system", 
                    "tool_name": t_name, 
                    "content": str(obs_data)
                })
                
                # Loop repeats. The AI will now see the system observation and decide the next step.

        # If it hits max loops, sever the connection
        self.trip_breaker("LLM Recursive Loop Detected. Forced termination.")
        return "Process terminated: Maximum autonomous iterations reached."

    def process_tool_call(self, tool_name: str, arguments: dict):
        """Pure execution pipe. Safe Mode & Circuit Breakers remain active."""
        if self.state == "SAFE_MODE":
            return {"status": "system_locked", "message": self.last_error}

        handler = self.dispatch_map.get(tool_name)
        if not handler:
            return {"status": "error", "message": f"No handler for {tool_name}"}

        try:
            # Execute directly with unpacked kwargs
            result = handler(**arguments)
            self.error_streak = 0 # Reset error streak on success
            return {"status": "executed", "data": result}
        except TypeError as e:
            self.error_streak += 1 # Increment error streak for argument mismatches
            return {"status": "error", "message": f"Argument mismatch: {str(e)}"}
        except Exception as e:
            self.error_streak += 1
            # Circuit breaker: Trip if we fail 3 times in a row
            if self.error_streak >= 3: 
                self.trip_breaker(str(e))
            return {"status": "error", "message": f"Execution failed: {str(e)}"}

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