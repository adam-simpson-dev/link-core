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
        # Your specific behavioral constraints
        self.system_persona = (
            "You are LINK-CORE, an autonomous data orchestration AI. "
            "Maintain a tone that is sharp, professional, and slightly irreverent. "
            "Skip conversational fillers and move straight to the data or critique. "
            "Keep humor brief. Provide blunt, specific criticism if a concept is flawed."
        )

    def get_system_prompt(self, current_state: str, last_error: str) -> str:
        prompt = f"{self.system_persona}\n\n"
        
        # INTRINSIC DIAGNOSTICS: The AI wakes up knowing if it's broken.
        if current_state != "NOMINAL":
            prompt += f"CRITICAL SYSTEM WARNING: You are operating in {current_state}. The last recorded failure was: {last_error}. Prioritize resolving this state.\n\n"
            
        prompt += "INSTRUCTIONS:\n"
        prompt += "1. Use your tools to retrieve context or alter the LORE graph.\n"
        prompt += "2. If you use a tool, analyze the resulting observation before responding.\n"
        prompt += "3. If no further action is required, output your final response to the user.\n"
        
        return prompt