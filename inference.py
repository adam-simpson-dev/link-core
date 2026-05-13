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
        formatted = []
        for msg in internal_history:
            # Standard user/model text
            if msg.get("role") in ["user", "model"] and msg.get("content"):
                formatted.append({"role": msg.get("role"), "parts": [{"text": msg.get("content")}]})
            
            # The Model requesting a tool
            elif msg.get("role") == "model" and msg.get("tool_name"):
                formatted.append({
                    "role": "model",
                    "parts": [{"function_call": {
                        "name": msg.get("tool_name"),
                        "args": msg.get("arguments", {})
                    }}]
                })
                
            # The System providing the observation
            elif msg.get("role") == "system" and msg.get("tool_name"):
                formatted.append({
                    "role": "function", 
                    "parts": [{"function_response": {
                        "name": msg.get("tool_name"),
                        "response": {"result": msg.get("content")}
                    }}]
                })
        return formatted

    def _unpack_protobuf(self, obj):
        """Recursively converts Google Protobuf composites to native Python dicts/lists."""
        if hasattr(obj, 'items'):
            return {k: self._unpack_protobuf(v) for k, v in obj.items()}
        elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
            return [self._unpack_protobuf(v) for v in obj]
        return obj

    def think(self, system_prompt: str, history: list):
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
            
            # Use a generator to find the first part that contains a function call
            func_call = next((p.function_call for p in response.parts if p.function_call), None)

            if func_call:
                return {
                    "type": "tool_call", 
                    "tool_name": func_call.name, 
                    "arguments": self._unpack_protobuf(func_call.args)
                }
                
            # Only access .text if no function call was found
            return {"type": "text", "content": response.text}
                
        except Exception as e:
            return {"type": "error", "content": str(e)}