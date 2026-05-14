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
        self.history = MessageHistory()
        self.brain = PromptManager()

        try:
            self.db = DatabaseManager()
            self.hass = HassClient()
            self.ai = InferenceEngine()
            # Map JSON tool names to their handler functions for dynamic dispatching
            self.dispatch_map = {
                # Node and Lore Management
                "get_context": self.db.get_relevant_context,
                "modify_lore": self.handle_modify_lore,
                #"read_document": self.handle_read_document, <-- Left in in case we want to add file reading back as a tool in the future
                # Home Assistant Control
                "control_home": self.handle_home_control,
                "inspect_entity": self.handle_inspect_entity,
                "get_area_map": self.handle_get_areas,
                "fire_home_event": self.handle_fire_event
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
        """Feeds the UI. Polling no longer destroys the buffer."""
        wake = list(self.db.last_accessed_uids)
        return {
            "state": self.state,
            "last_error": self.last_error,
            "memory": self.history.get_context(),
            "last_accessed_uids": wake,
            "accessed_uids": wake,
            "active_nodes": wake
        }
        
    def process_natural_language(self, user_input: str):
        """The ReAct (Reasoning & Acting) Loop."""
        if self.state == "SAFE_MODE": return "System locked."

        # Flush the radar buffer ONLY when a new cognitive process begins.
        self.db.last_accessed_uids.clear()

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

    def handle_modify_lore(self, upsert_nodes=None, create_links=None, delete_uids=None):
        """Omni-Tool router. Passes batched operations to the Database Manager."""
        results = []
        
        if upsert_nodes:
            for node in upsert_nodes:
                uid = node.get("uid")
                for k, v in node.get("traits", {}).items():
                    self.db.upsert_lore(uid, k, str(v))
            results.append(f"Upserted traits for {len(upsert_nodes)} nodes")
            
        if create_links:
            for link in create_links:
                self.db.create_relationship(link["source"], link["target"], link["relation"])
            results.append(f"Created {len(create_links)} links")
            
        if delete_uids:
            for uid in delete_uids:
                self.db.delete_node(uid)
            results.append(f"Deleted {len(delete_uids)} nodes")
            
        return " | ".join(results) if results else "No modifications provided."

    def handle_inspect_entity(self, entity_id, start_time_iso=None):
        """Dual-purpose HASS inspector. Handles both state and history."""
        if start_time_iso:
            history = self.hass.get_history(entity_id, start_time_iso)
            if not history: return f"No history found for {entity_id}."
            events = history[0] if isinstance(history, list) and history else []
            timeline = [f"[{e.get('last_changed')}] {e.get('state')}" for e in events[-10:]]
            return "\n".join(timeline)
        else:
            raw_data = self.hass.get_entity_state(entity_id)
            if not raw_data: return f"Error: Entity {entity_id} not found."
            return {
                "entity_id": raw_data.get("entity_id"),
                "state": raw_data.get("state"),
                "last_changed": raw_data.get("last_changed"),
                "friendly_name": raw_data.get("attributes", {}).get("friendly_name")
            }

    def handle_get_areas(self):
        """Processes HASS areas into a high-density intelligence report."""
        # Use your hass_client method
        raw_areas = self.hass.get_area_map()
        
        if not raw_areas or "error" in raw_areas:
            return "No structured areas found in Home Assistant configuration."

        # Filter the noise: We only want Area Name -> Entities
        # This prevents the AI from getting lost in HASS internal metadata
        area_summary = {}
        for item in raw_areas:
            area_name = item.get("name", "Unassigned")
            # This logic assumes your hass_client.py returns a list of areas
            # or a mapped dict. Adjust based on your exact hass_client return.
            area_summary[area_name] = item.get("entities", [])

        return area_summary if area_summary else "Area map is empty."

    def handle_fire_event(self, event_name, event_data=None):
        """Executes a custom automation."""
        success = self.hass.fire_custom_event(event_name, event_data or {})
        if success:
            logging.info(f"[*] Custom Event Fired: {event_name}")
            return f"Event '{event_name}' successfully broadcast to Home Assistant."
        return f"Failed to fire event '{event_name}'."

    def shutdown(self):
        """Graceful termination of database links."""
        logging.info("[!] LINK-CORE Shutting down.")
        if hasattr(self, 'db'):
            self.db.close()