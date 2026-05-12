import logging
import json
import os
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
        self.db = DatabaseManager()
        self.hass = HassClient()
        self.history = []

        # Mapping JSON Tool names (from tools.py) to internal Python methods
        self.dispatch_map = {
            "get_context": self.db.get_relevant_context,
            "update_memory": self.db.upsert_lore,
            "control_home": self.handle_home_control,
            "read_document": self.handle_read_document,
            "delete_node": self.db.delete_node
        }
        logging.info("[*] LINK-CORE Dispatcher Active. Systems Nominal.")

    def process_tool_call(self, tool_name, arguments, override=False):
        schema = get_tool_schema(tool_name)
        
        if not schema:
            logging.warning(f"[!] Attempted to call unregistered tool: {tool_name}")
            return {"status": "error", "message": f"Tool {tool_name} not found."}

        # THE CIRCUIT BREAKER: If the tool is marked as high-risk and override is not True, block execution.
        if schema.get("requires_confirmation", False) and not override:
            logging.warning(f"[!] CRITICAL: Tool '{tool_name}' intercepted. Awaiting manual override.")
            return {
                "status": "pending_authorization",
                "tool_name": tool_name,
                "arguments": arguments,
                "message": f"Execution of {tool_name} requires explicit human confirmation."
            }

        handler = self.dispatch_map.get(tool_name)
        if handler:
            self.history.append({"tool": tool_name, "args": arguments})
            logging.info(f"[*] Dispatching Tool: {tool_name} | Override: {override}")
            
            return {
                "status": "executed", 
                "data": handler(**arguments)
            }
        
        return {"status": "error", "message": "Handler missing for registered tool."}

    # --- Tool Handlers ---

    def handle_read_document(self, file_path):
        """Reads local files for deep context retrieval."""
        if not os.path.exists(file_path):
            return f"Error: File at {file_path} not found."
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                logging.info(f"[*] Read {len(content)} characters from {file_path}")
                return content
        except Exception as e:
            logging.error(f"Error reading file: {str(e)}")
            return f"Error reading file: {str(e)}"

    def handle_get_context(self, uid):
        """Retrieves and prints node context for debugging or LLM feeding."""
        context = self.db.get_node_context(uid)
        logging.info(f"[CONTEXT] {context}")
        return context

    def handle_update_memory(self, target_uid, key, value):
        """Updates the SQLite knowledge graph."""
        return self.db.set_property("NODE", target_uid, key, value)

    def handle_home_control(self, domain, service, entity_id, **kwargs):
        """
        Extracts entity_id and any optional parameters (brightness, color)
        and bundles them for the HassClient.
        """
        service_data = {"entity_id": entity_id}
        service_data.update(kwargs) # This catches brightness, color_name, etc.
        
        logging.info(f"Refined HA Call: {domain}.{service} -> {service_data}")
        return self.hass.call_service(domain, service, service_data)

    def shutdown(self):
        """Clean resource release."""
        self.db.close()
        logging.info("[*] LINK-CORE Offline.")

if __name__ == "__main__":
    import time
    core = LinkCore()
    try:
        logging.info("[*] LINK-CORE Service successfully initialized.")
        # This loop keeps the process alive so Systemd doesn't restart it.
        while True:
            # This is where a 'listener' for a queue or API will sit.
            time.sleep(60) 
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logging.error(f"[!] Critical System Error: {e}")
    finally:
        core.shutdown()