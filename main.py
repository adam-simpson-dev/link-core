import json
import os
from database import DatabaseManager
from hass_client import HassClient

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
            "update_memory": self.handle_update_memory,
            "control_home": self.handle_control_home,
            "get_context": self.handle_get_context,
            "read_document": self.handle_read_document # NEW
        }
        print("[*] LINK-CORE Dispatcher Active. Systems Nominal.")

    def process_tool_call(self, tool_name, arguments):
        handler = self.dispatch_map.get(tool_name)
        if handler:
            # We log the action to history so the AI 'remembers' it did it
            self.history.append({"tool": tool_name, "args": arguments})
            print(f"[*] Dispatching Tool: {tool_name}")
            return handler(**arguments)
        
        print(f"[!] No handler found for tool: {tool_name}")
        return False

    # --- Tool Handlers ---

    def handle_read_document(self, file_path):
        """Reads local files for deep context retrieval."""
        if not os.path.exists(file_path):
            return f"Error: File at {file_path} not found."
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"[*] Read {len(content)} characters from {file_path}")
                return content
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def handle_get_context(self, uid):
        """Retrieves and prints node context for debugging or LLM feeding."""
        context = self.db.get_node_context(uid)
        print(f"[CONTEXT] {context}")
        return context

    def handle_update_memory(self, target_uid, key, value):
        """Updates the SQLite knowledge graph."""
        return self.db.set_property("NODE", target_uid, key, value)

    def handle_control_home(self, domain, service, entity_id, **kwargs):
        """Sends commands to the Home Assistant API."""
        return self.hass.call_service(domain, service, {"entity_id": entity_id, **kwargs})

    def shutdown(self):
        """Clean resource release."""
        self.db.close()
        print("[*] LINK-CORE Offline.")

if __name__ == "__main__":
    import time
    core = LinkCore()
    try:
        print("[*] LINK-CORE Service successfully initialized.")
        # This loop keeps the process alive so Systemd doesn't restart it.
        while True:
            # This is where a 'listener' for a queue or API will sit.
            time.sleep(60) 
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[!] Critical System Error: {e}")
    finally:
        core.shutdown()