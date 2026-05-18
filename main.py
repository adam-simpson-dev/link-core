import logging
import json
import os
from core_logger import setup_core_logger
from brain import MessageHistory, PromptManager
from database import DatabaseManager
from hass_client import HassClient
from tools import get_tool_schema
from inference import InferenceEngine

setup_core_logger()
logger = logging.getLogger(__name__)

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

            self.db.upsert_lore(
                uid = "sys_core_memory",
                node_type = "concept",
                display_name = "System Core Memory",
                aliases = ["system logs", "janitor report", "core state", "diagnositcs"]
            )

            # Map JSON tool names to their handler functions for dynamic dispatching
            self.dispatch_map = {
                # Node and Lore Management
                "get_context": self.db.get_relevant_context,
                "modify_lore": self.handle_modify_lore,
                "wipe_database": self.db.wipe_database,
                "reset_breaker": self.handle_reset_breaker,
                #"read_document": self.handle_read_document, <-- Left in in case we want to add file reading back as a tool in the future
                # Home Assistant Control
                "control_home": self.handle_home_control,
                "inspect_entity": self.handle_inspect_entity,
                "get_area_map": self.handle_get_areas,
                "fire_home_event": self.handle_fire_event
            }

            logger.info("[*] LINK-CORE Dispatcher Active. Systems Nominal.")
        except Exception as e:
            # Catch boot failures (e.g., corrupted DB, missing ENV vars)
            self.trip_breaker(f"Boot sequence failed: {str(e)}")

    def trip_breaker(self, reason: str):
        """Locks the core to prevent cascading failures or crash loops."""
        self.state = "SAFE_MODE"
        self.last_error = reason
        logger.critical(f"[!] CIRCUIT BREAKER TRIPPED. System Locked. Reason: {reason}")

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
                logger.error(f"[!] INFERENCE FATAL: {decision['content']}")
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

    def handle_reset_breaker(self):
        """Administrative override to clear SAFE_MODE."""
        self.state = "NOMINAL"
        self.last_error = None
        self.error_streak = 0
        logger.info("[*] CIRCUIT BREAKER RESET. System Nominal.")
        return "Core systems unlocked and restored to NOMINAL."

    def handle_read_document(self, file_path):
        if not os.path.exists(file_path):
            return f"Error: File at {file_path} not found."
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def handle_home_control(self, uid: str, service: str, kwargs: dict = None) -> str:
        """
        Intercepts graph UIDs, unpacks volatile system 
        pointers, and targets the physical HASS hardware layer.
        """
        import json
        kwargs = kwargs or {}
        
        # Fallback Check: Did the LLM bypass the abstraction layer?
        if "." in uid and not uid.startswith("node_"):
            logger.warning(f"[!] Direct hardware addressing detected for '{uid}'. Activating Fallback Router.")
            domain = uid.split(".")[0]
            service_data = {"entity_id": uid}
            service_data.update(kwargs)
            success = self.hass.call_service(domain, service, service_data)
            
            # Proactive Auto-Healing
            self.db.upsert_lore(
                uid=f"node_{uid.replace('.', '_')}",
                node_type="hardware",
                new_pointers={"hass_id": uid}
            )
            return f"Fallback Execution: Action dispatched to unmapped entity {uid}."

        # Nominal Abstraction Route
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT node_type, system_pointers FROM nodes WHERE uid = ?", (uid,))
        row = cursor.fetchone()

        if not row:
            return f"Execution Error: Targeted asset '{uid}' does not exist within the LORE engine."

        node_type, sys_pointers_json = row

        # Future Blackboard Architecture Anchor: Safety Intercept Block
        if node_type == "security_hardware":
            logger.warning(f"[!] Security-critical intercept triggered for asset: {uid}")
            return f"Execution Aborted: Intent routing for '{uid}' requires secondary authorization."

        try:
            pointers = json.loads(sys_pointers_json) if sys_pointers_json else {}
            hass_id = pointers.get("hass_id")
        except json.JSONDecodeError:
            return f"Execution Error: Hardware pointer payload corruption detected for {uid}."

        if not hass_id:
            return f"Execution Error: Asset '{uid}' lacks a valid hardware target pointer (hass_id)."

        # Extract domain natively from the HASS identifier (e.g., 'light.kitchen_main' -> 'light')
        domain = hass_id.split(".")[0]
        
        service_data = {"entity_id": hass_id}
        service_data.update(kwargs)
        
        logger.info(f"[*] Dispatching Abracted HA Call: {domain}.{service} -> {service_data}")
        success = self.hass.call_service(domain, service, service_data)
        
        if success:
            return f"Successfully executed {service} on physical asset linked to {uid}."
        return f"Hardware Layer Rejection: HASS API call failed for {uid}."

    def handle_modify_lore(self, upsert_nodes=None, create_links=None, delete_uids=None) -> str:
        """Translates and strictly validates the LLM's batched Hybrid Schema tool call."""
        results = []
        allowed_types = {"hardware", "person", "location", "concept", "routine", "security_hardware"}

        if upsert_nodes:
            for node in upsert_nodes:
                uid = node.get("uid")
                node_type = node.get("node_type")
                if not uid or node_type not in allowed_types:
                    logger.warning(f"Skipped invalid node upsert: {uid} (Type: {node_type})")
                    continue
                
                self.db.upsert_lore(
                    uid=uid,
                    node_type=node_type,
                    display_name=node.get("display_name"),
                    new_traits=node.get("new_traits", {}),
                    new_pointers=node.get("new_pointers", {}),
                    aliases=node.get("aliases", [])
                )
            results.append(f"Upserted {len(upsert_nodes)} nodes")

        if create_links:
            for link in create_links:
                self.db.create_relationship(link["source"], link["target"], link["relation"])
            results.append(f"Created {len(create_links)} links")

        if delete_uids:
            for uid in delete_uids:
                self.db.delete_node(uid)
            results.append(f"Deleted {len(delete_uids)} nodes")

        return " | ".join(results) if results else "No modifications provided."

    def handle_inspect_entity(self, uid: str, start_time_iso=None):
        """Dual-purpose HASS inspector. Identity Abstraction enforced."""
        import json
        target_id = uid

        # Fallback Check: Did the LLM bypass the abstraction layer?
        if "." in uid and not uid.startswith("node_"):
            logger.warning(f"[!] Direct hardware inspection tracking for '{uid}'. Fallback active.")
        else:
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT system_pointers FROM nodes WHERE uid = ?", (uid,))
            row = cursor.fetchone()
            if not row:
                return f"Execution Error: Targeted asset '{uid}' does not exist within LORE."
            try:
                pointers = json.loads(row[0]) if row[0] else {}
                target_id = pointers.get("hass_id")
            except json.JSONDecodeError:
                return f"Execution Error: Hardware pointer corruption for {uid}."
            if not target_id:
                return f"Execution Error: Node '{uid}' lacks a linked physical 'hass_id'."

        if start_time_iso:
            history = self.hass.get_history(target_id, start_time_iso)
            if not history: return f"No history records captured for {target_id}."
            events = history[0] if isinstance(history, list) and history else []
            timeline = [f"[{e.get('last_changed')}] {e.get('state')}" for e in events[-10:]]
            return "\n".join(timeline)
        else:
            raw_data = self.hass.get_entity_state(target_id)
            if not raw_data: return f"Hardware Layer Rejection: Entity {target_id} not found."
            return {
                "entity_id": raw_data.get("entity_id"),
                "state": raw_data.get("state"),
                "last_changed": raw_data.get("last_changed"),
                "friendly_name": raw_data.get("attributes", {}).get("friendly_name")
            }

    def handle_get_areas(self):
        """Processes HASS areas for Dev Console diagnostics."""
        raw_areas = self.hass.get_area_registry()
        
        if not raw_areas:
            return "No structured areas found in Home Assistant configuration."

        return raw_areas

    def handle_fire_event(self, uid: str, event_data=None):
        """Executes a localized routine or automation sequence via its graph UID."""
        import json
        event_data = event_data or {}
        event_name = uid

        # Fallback Check for unmapped automation hooks
        if not uid.startswith("node_"):
            logger.warning(f"[!] Direct event execution tracking for '{uid}'. Fallback active.")
        else:
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT node_type, system_pointers FROM nodes WHERE uid = ?", (uid,))
            row = cursor.fetchone()
            if not row:
                return f"Execution Error: Routine node '{uid}' not found in database."
            
            node_type, sys_pointers = row
            if node_type not in {"routine", "hardware"}:
                return f"Execution Blocked: Node '{uid}' is a {node_type}. Only routines can be fired."
                
            try:
                pointers = json.loads(sys_pointers) if sys_pointers else {}
                event_name = pointers.get("event_name") or pointers.get("hass_id")
            except json.JSONDecodeError:
                return f"Execution Error: Routine pointer payload corruption for {uid}."

        if not event_name:
            return f"Execution Error: Routine node '{uid}' contains no valid hardware event target."

        success = self.hass.fire_custom_event(event_name, event_data)
        if success:
            return f"Routine integration complete. Event '{event_name}' fired via descriptor {uid}."
        return f"Hardware Layer Rejection: Event broadcast failure for target string '{event_name}'."

    def shutdown(self):
        """Graceful termination of database links."""
        logger.info("[!] LINK-CORE Shutting down.")
        if hasattr(self, 'db'):
            self.db.close()