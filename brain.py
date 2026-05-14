import json
import logging
from tools import TOOL_SCHEMAS
from datetime import datetime

class MessageHistory:
    def __init__(self, max_tokens=4000):
        """
        Maintains the rolling context window based on estimated token weight,
        ensuring local LLMs do not suffer OOM crashes.
        """
        self.history = []
        self.max_tokens = max_tokens



    def _estimate_tokens(self, text: str) -> float:
        """Fast heuristic for token weight."""
        return len(str(text).split()) * 1.3

    def _calculate_history_weight(self):
        """Weighs the active conversation, including hidden tool data."""
        weight = 0
        for msg in self.history:
            weight += self._estimate_tokens(msg.get("content", ""))
            if "tool_calls" in msg:
                weight += self._estimate_tokens(str(msg["tool_calls"]))
            if "tool_results" in msg:
                weight += self._estimate_tokens(str(msg["tool_results"]))
        return weight

    def add_message(self, role: str, content: str, tool_calls=None, tool_results=None):
        """Standardized ingestion."""
        message = {"role": role, "content": content}
        
        if tool_calls:
            message["tool_calls"] = tool_calls
        if tool_results:
            message["tool_results"] = tool_results

        self.history.append(message)
        self.prune()

    def prune(self):
        """Weight-based slicing. Drops oldest context when token limit is breached."""
        while self.history and self._calculate_history_weight() > self.max_tokens:
            # Drop the oldest message
            self.history.pop(0)
            
            # Formatting constraint: Gemini/OpenAI both violently reject histories 
            # that start with a floating tool response or assistant reply.
            # We must aggressively purge until we find the next clean user prompt.
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
            "CRITICAL DATA RULE: All UIDs must be strictly lowercase snake_case (e.g., 'john_robinson'). "
            "DELETION PROTOCOL: Use 'delete_node' ONLY when an object is confirmed destroyed or when explicitly commanded by the user."
        )

    def get_system_prompt(self, current_state: str, last_error: str) -> str:
        # Establish the Temporal Anchor
        current_time_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        day_of_week = datetime.now().strftime("%A")
        
        prompt = f"{self.system_persona}\n\n"

        # Inject the time anchor
        prompt += f"TEMPORAL ANCHOR: It is currently {day_of_week}, {current_time_iso} local time. "
        prompt += "Use this baseline to calculate 'start_time_iso' for history inspections.\n\n"

        # INTRINSIC DIAGNOSTICS: The AI wakes up knowing if it's broken.        
        if current_state != "NOMINAL":
            prompt += f"CRITICAL SYSTEM WARNING: You are operating in {current_state}. The last recorded failure was: {last_error}. Prioritize resolving this state.\n\n"
            
        prompt += "INSTRUCTIONS:\n"
        prompt += "1. READ BEFORE WRITE: Use 'get_context' to resolve generic nouns to UIDs before modifying memory.\n"
        prompt += "2. OMNI-TOOL EFFICIENCY: Batch your memory updates using 'modify_lore' whenever possible.\n"
        prompt += "3. PRECISION STRIKES: Do not guess HASS entity IDs. If unknown, check lore context first and avoid duplicates.\n"
        prompt += "4. HANDLE REDUNDANT PROMPTs: If not tool is required, respond with a concise answer and avoid unnecessary tool calls.\n"
        
        return prompt