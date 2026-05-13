import os
import google.generativeai as genai
from tools import TOOL_SCHEMAS

class InferenceEngine:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("[-] CRITICAL: GEMINI_API_KEY missing from .env")
        
        genai.configure(api_key=self.api_key)
        
        # Translate LINK-CORE tools into Gemini's native OpenAPI format
        self.gemini_tools = [{"function_declarations": []}]
        for schema in TOOL_SCHEMAS:
            self.gemini_tools[0]["function_declarations"].append({
                "name": schema["name"],
                "description": schema["description"],
                "parameters": schema["parameters"]
            })

    def format_history(self, internal_history):
        """Translates the memory queue into Gemini's exact message structure."""
        formatted = []
        for msg in internal_history:
            # We filter out system/dev console logs so the LLM only sees the active conversation
            if msg.get("role") in ["user", "model"] and msg.get("content"):
                formatted.append({"role": msg["role"], "parts": [{"text": msg.get("content")}]})
            
            # Formatting the tool execution results for Gemini's context window
            elif msg.get("role") == "system" and msg.get("tool_name"):
                formatted.append({
                    "role": "function",
                    "parts": [{"function_response": {
                        "name": msg.get("tool_name"),
                        "response": {"result": msg.get("content")}
                    }}]
                })
        return formatted

    def think(self, system_prompt: str, history: list, user_text: str):
        """The cognitive bridge. Sends the state and waits for a decision."""
        
        # Initialize the model dynamically with the current system state & LORE
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_prompt,
            tools=self.gemini_tools
        )

        # Build the conversation payload
        gemini_history = self.format_history(history)
        
        try:
            response = model.generate_content(gemini_history)

            if response.parts and response.parts[0].function_call:
                fc = response.parts[0].function_call
                args = {key: val for key, val in fc.args.items()}
                return {"type": "tool_call", "tool_name": fc.name, "arguments": args}
            else:
                return {"type": "text", "content": response.text}
                
        except Exception as e:
            return {"type": "error", "content": str(e)}