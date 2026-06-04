import logging
import json
import os
from core_logger import setup_core_logger
from brain import MessageHistory, PromptManager
from database import DatabaseManager
from hass_client import HassClient
from tools import get_tool_schema
from inference import InferenceEngine
from nlp_engine import NLPEngine

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
        self.nlp_engine = NLPEngine()

        try:
            self.db = DatabaseManager()
            self.hass = HassClient()
            self.ai = InferenceEngine()

            self.db.upsert_lore(
                uid = "sys_core_memory",
                node_type = "concept",
                display_name = "System Core Memory",
                aliases = ["system logs", "janitor report", "core state", "diagnostics"]
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
        """Natural Language Pipeline Routing."""
        if self.state == "SAFE_MODE": return "System locked."
        self.db.last_accessed_uids.clear()

        # Blackboard Intent Analysis (Offline)
        intent = self.nlp_engine.classify_intent(user_input)
        logger.info(f"[*] Blackboard Classified Input Intent as: [{intent}]")

        # Air-Gapped Security Intercept
        if intent == "SECURITY_BYPASS":
            logger.warning("[!] SECURITY INTERCEPT: Unauthenticated administrative command blocked.")
            return "Physical or native application authentication required for security hardware modifications. Override denied."

        self.history.add_message("user", user_input)
        iteration = 0
        max_iterations = 5

        while iteration < max_iterations:
            iteration += 1
            
            # Dynamic Prompt Assembly based on the NLP intent
            system_prompt = self.brain.get_system_prompt(self.state, self.last_error, intent=intent)
            decision = self.ai.think(system_prompt, self.history.get_context())
            
            if decision["type"] == "error":
                logger.error(f"[!] INFERENCE FATAL: {decision['content']}")
                return "API ERROR. Check core logs."
                
            elif decision["type"] == "text":
                self.history.add_message("model", decision["content"])
                return decision["content"]
                
            elif decision["type"] == "tool_call":
                t_name, t_args = decision["tool_name"], decision["arguments"]
                self.history.add_message("model", "", tool_calls=[decision])
                
                result = self.process_tool_call(t_name, t_args)
                obs_data = result.get("data", result.get("message", "Executed."))
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
        
        # Fallback Check in case the LLM bypassed the abstraction layer
        if "." in uid:
            logger.warning(f"[!] Direct hardware addressing detected for '{uid}'. Activating Fallback Router.")
            domain, name = uid.split(".", 1)
            
            # Strip known suffixes to keep keys aligned with graph_sync.py
            base_name = name
            for suffix in ["_light", "_battery", "_power", "_switch", "_sensor"]:
                if base_name.endswith(suffix):
                    base_name = base_name[:-len(suffix)]
                    break
                    
            clean_uid = f"{domain}_{base_name}"
            service_data = {"entity_id": uid}
            service_data.update(kwargs)
            self.hass.call_service(domain, service, service_data)
            
            self.db.upsert_lore(uid=clean_uid, node_type="hardware", new_pointers={"hass_id": uid})
            return f"Fallback Execution: Action dispatched to unmapped entity {uid}."

        # Nominal Abstraction Route
        cursor = self.db.conn.cursor()
        # Pull traits to identify domain
        cursor.execute("SELECT node_type, system_pointers, traits FROM nodes WHERE uid = ?", (uid,))
        row = cursor.fetchone()

        if not row:
            return f"Execution Error: Targeted asset '{uid}' does not exist within the LORE engine."

        node_type, sys_pointers_json, traits_json = row

        # Air Gap security_hardware to push authentication to the physical device
        if node_type == "security_hardware":
            logger.warning(f"[!] Security-critical intercept triggered for asset: {uid}")
            return f"Execution Aborted: Intent routing for '{uid}' requires secondary authorization."

        try:
            pointers = json.loads(sys_pointers_json) if sys_pointers_json else {}
            traits = json.loads(traits_json) if traits_json else {}
            
            # Smart pointer resolution
            hass_id = pointers.get("hass_id")
            domain = traits.get("domain")
            
            if not hass_id and domain:
                hass_id = pointers.get(f"{domain}_id")
            if not hass_id and pointers:
                # Ultimate fallback: grab the first value that matches the domain string
                hass_id = next((v for v in pointers.values() if isinstance(v, str) and v.startswith(f"{domain}.")), list(pointers.values())[0])
                
        except json.JSONDecodeError:
            return f"Execution Error: Hardware pointer payload corruption detected for {uid}."

        if not hass_id:
            return f"Execution Error: Asset '{uid}' lacks a valid hardware target pointer."

        # Extract domain natively from the HASS identifier
        exec_domain = hass_id.split(".")[0]
        
        service_data = {"entity_id": hass_id}
        service_data.update(kwargs)
        
        logger.info(f"[*] Dispatching Abracted HA Call: {exec_domain}.{service} -> {service_data}")
        success = self.hass.call_service(exec_domain, service, service_data)
        
        if success:
            return f"Successfully executed {service} on physical asset linked to {uid}."
        return f"Hardware Layer Rejection: HASS API call failed for {uid}."

    def handle_modify_lore(self, upsert_nodes=None, create_links=None, delete_links=None, delete_uids=None, rename_uids=None, **kwargs) -> str:
        """Translates and strictly validates the LLM's batched Hybrid Schema tool call."""
        results = []
        allowed_types = {"hardware", "person", "location", "concept", "routine", "security_hardware", "pet"}

        if upsert_nodes:
            for node in upsert_nodes:
                raw_uid = node.get("uid")
                node_type = node.get("node_type")
                if not raw_uid or node_type not in allowed_types: continue
                
                # Maps node_type to the strict graph namespace
                prefix_map = {
                    "location": "loc_",
                    "person": "person_",
                    "pet": "pet_",
                    "concept": "concept_",
                    "routine": "routine_"
                }
                
                uid = raw_uid
                if node_type in prefix_map:
                    expected_prefix = prefix_map[node_type]
                    if not uid.startswith(expected_prefix):
                        # Strip any rogue prefixes the LLM might have guessed
                        for val in prefix_map.values():
                            if uid.startswith(val):
                                uid = uid.replace(val, "", 1)
                                break
                        # Enforce the mathematical boundary
                        uid = f"{expected_prefix}{uid}"
                
                self.db.upsert_lore(
                    uid=uid, node_type=node_type, display_name=node.get("display_name"),
                    new_traits=node.get("new_traits", {}), new_pointers=node.get("new_pointers", {}),
                    aliases=node.get("aliases")
                )
            results.append(f"Upserted {len(upsert_nodes)} nodes")

        if create_links:
            for link in create_links:
                self.db.create_relationship(link["source"], link["target"], link["relation"])
            results.append(f"Created {len(create_links)} links")

        if delete_links:
            cursor = self.db.conn.cursor()
            for link in delete_links:
                cursor.execute("""
                    DELETE FROM edges 
                    WHERE source_uid = ? AND target_uid = ? AND relationship = ?
                """, (link["source"], link["target"], link["relation"]))
            self.db.conn.commit()
            results.append(f"Severed {len(delete_links)} relationships")

        # Primary Key Migration Protocol
        if rename_uids:
            cursor = self.db.conn.cursor()
            for remap in rename_uids:
                old_uid = remap["old_uid"]
                new_uid = remap["new_uid"]
                
                # Verify structural source exists in SQLite
                cursor.execute("SELECT node_type, display_name, aliases, system_pointers, traits FROM nodes WHERE uid = ?", (old_uid,))
                row = cursor.fetchone()
                if not row: continue
                
                node_type, display_name, aliases, system_pointers, traits = row
                
                # Mint the new identity envelope
                cursor.execute("""
                    INSERT INTO nodes (uid, node_type, display_name, aliases, system_pointers, traits)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (new_uid, node_type, display_name, aliases, system_pointers, traits))
                
                # Re-route relational edges before deleting to protect foreign key constraints
                cursor.execute("UPDATE edges SET source_uid = ? WHERE source_uid = ?", (new_uid, old_uid))
                cursor.execute("UPDATE edges SET target_uid = ? WHERE target_uid = ?", (new_uid, old_uid))
                
                # Safely purge legacy row identifier
                cursor.execute("DELETE FROM nodes WHERE uid = ?", (old_uid,))
                self.db.conn.commit()
                
                # Synchronize Vector Space to stop ghost lookups
                self.db.vector.delete_vector(old_uid)
                envelope_text = self.db.generate_semantic_envelope(new_uid, display_name, aliases)
                self.db.vector.upsert_node_vector(new_uid, envelope_text)
                
            results.append(f"Migrated {len(rename_uids)} primary keys")

        if delete_uids:
            for uid in delete_uids:
                self.db.delete_node(uid)
            results.append(f"Deleted {len(delete_uids)} nodes")

        return " | ".join(results) if results else "No modifications provided."

    def handle_inspect_entity(self, uid: str, start_time_iso=None):
        """Dual-purpose HASS inspector. Identity Abstraction enforced."""
        import json
        target_id = uid

        # Check the LLM didn't bypass the abstraction layer
        if "." in uid:
            logger.warning(f"[!] Direct hardware inspection tracking for '{uid}'. Fallback active.")
        else:
            cursor = self.db.conn.cursor()
            # Pull traits to identify domain
            cursor.execute("SELECT system_pointers, traits FROM nodes WHERE uid = ?", (uid,))
            row = cursor.fetchone()
            if not row:
                return f"Execution Error: Targeted asset '{uid}' does not exist within LORE."
            try:
                pointers = json.loads(row[0]) if row[0] else {}
                traits = json.loads(row[1]) if row[1] else {}
                
                # Smart pointer resolution
                target_id = pointers.get("hass_id")
                domain = traits.get("domain")
                if not target_id and domain:
                    target_id = pointers.get(f"{domain}_id")
                if not target_id and pointers:
                    target_id = next((v for v in pointers.values() if isinstance(v, str) and v.startswith(f"{domain}.")), list(pointers.values())[0])
                    
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

        #Check that the LLM didn't bypass the abstraction layer
        if "." in uid:
            logger.warning(f"[!] Direct event execution tracking for '{uid}'. Fallback active.")
        else:
            cursor = self.db.conn.cursor()
            # Pull traits to identify domain
            cursor.execute("SELECT node_type, system_pointers, traits FROM nodes WHERE uid = ?", (uid,))
            row = cursor.fetchone()
            if not row:
                return f"Execution Error: Routine node '{uid}' not found in database."
            
            # Safety check to prevent firing devices
            node_type, sys_pointers, traits_json = row
            if node_type not in {"routine", "hardware"}:
                return f"Execution Blocked: Node '{uid}' is a {node_type}. Only routines can be fired."
                
            try:
                pointers = json.loads(sys_pointers) if sys_pointers else {}
                traits = json.loads(traits_json) if traits_json else {}
                
                # Smart pointer routing
                event_name = pointers.get("event_name") or pointers.get("hass_id")
                domain = traits.get("domain")
                if not event_name and domain:
                    event_name = pointers.get(f"{domain}_id")
                    
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