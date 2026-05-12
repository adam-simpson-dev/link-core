# brain.py
import json
import logging
from tools import TOOL_SCHEMAS

class MessageHistory:
    def __init__(self, max_turns=10):
        """
        Maintains the rolling context window.
        A 'turn' is a User message + Assistant response.
        """
        self.history = []
        self.max_turns = max_turns * 2

    def add_message(self, role: str, content: str, tool_calls=None, tool_results=None):
        """Standardized ingestion for future LLM formatting."""
        message = {"role": role, "content": content}
        
        # Storing tool data separately ensures the UI can render it cleanly later
        if tool_calls:
            message["tool_calls"] = tool_calls
        if tool_results:
            message["tool_results"] = tool_results

        self.history.append(message)
        self.prune()

    def prune(self):
        """Slices the oldest interactions to prevent token bloat."""
        if len(self.history) > self.max_turns:
            excess = len(self.history) - self.max_turns
            self.history = self.history[excess:]
            
            # Never start the history slice with an orphaned assistant response.
            while self.history and self.history[0].get("role") != "user":
                self.history.pop(0)

    def get_context(self):
        return self.history

class PromptManager:
    def __init__(self):
        self.system_persona = (
            "You are LINK-CORE, the central intelligence for a localized home and data environment. "
            "You are analytical, direct, and efficient. You have access to a Knowledge Graph (LORE) "
            "and Home Assistant (HASS). Execute user requests precisely using the provided tools. "
            "Output ONLY the JSON required to fire the tool, or a direct response if no tools are needed."
        )

    def compile_payload(self, user_prompt: str, context_data: str, history: list) -> dict:
        """
        Assembles the state. Returns a dictionary so the FastAPI can read the components 
        before they are flattened for the LLM.
        """
        system_instructions = f"{self.system_persona}\n\n### LORE CONTEXT ###\n{context_data}\n\n"
        
        # We inject the schemas here so the AI knows its own capabilities
        system_instructions += f"### AVAILABLE TOOLS ###\n{json.dumps(TOOL_SCHEMAS, indent=2)}"

        return {
            "system_prompt": system_instructions,
            "memory_queue": history,
            "active_intent": user_prompt
        }