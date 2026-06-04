import json
import yaml
import os
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
            self.history.pop(0)
            
            # API Constraint: History cannot start with a tool result without the originating tool call.
            # If the new head of the history is a 'system' (tool_results) or 'model' (tool_calls),
            # we must ensure it's structurally sound. Safest bet is to pop until we hit standard text.
            while self.history and (self.history[0].get("role") == "system" or "tool_calls" in self.history[0]):
                self.history.pop(0)
                
    def compress_execution_loop(self, retain_turns=4):
        """
        Purges volatile tool data from the persistent context window.
        Leaves only the human prompts and the final AI conversational responses.
        """
        compressed = []
        for msg in self.history:
            # Keep standard conversational turns. Discard anything containing a tool_call or tool_result.
            if msg.get("role") in ["user", "model"] and "tool_calls" not in msg and "tool_results" not in msg:
                compressed.append(msg)
                
        # Enforce a strict short-term memory limit to prevent context rot
        # Each "turn" is a user/model pair, so 4 turns = 8 messages.
        self.history = compressed[-(retain_turns * 2):] if len(compressed) > (retain_turns * 2) else compressed
        
    def get_context(self):
        return self.history

class PromptManager:
    def __init__(self, config_path="prompts.yaml"):
        self.config_path = config_path
        self.prompts = {}
        self.load_config()

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.prompts = yaml.safe_load(f) or {}
        else:
            logging.getLogger(__name__).error(f"[-] CRITICAL: Prompt library '{self.config_path}' missing.")

    def get_system_prompt(self, current_state: str, last_error: str, intent: str = "LORE_QUERY") -> str:
        """Assembles the operational prompt fragment dynamically based on Blackboard classification."""
        current_time_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        day_of_week = datetime.now().strftime("%A")

        base = self.prompts.get("base_persona", "")
        db_rules = self.prompts.get("db_rules", "")
        
        modules = self.prompts.get("intent_modules", {})
        active_module = modules.get(intent, modules.get("LORE_QUERY", ""))

        prompt = f"{base}\n\n"
        prompt += f"TEMPORAL ANCHOR: {day_of_week}, {current_time_iso} local time.\n\n"

        if current_state != "NOMINAL":
            prompt += f"CRITICAL SYSTEM WARNING: Operating in {current_state}. Last failure: {last_error}. Prioritize resolution.\n\n"

        prompt += f"ACTIVE INTENT CONTEXT:\n{active_module}\n\n"
        prompt += db_rules
        
        return prompt