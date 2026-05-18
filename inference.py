import os
from dotenv import load_dotenv
import google.generativeai as genai
from tools import TOOL_SCHEMAS

load_dotenv()

class InferenceEngine:
    def __init__(self, allowed_tools: list = None):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("[-] CRITICAL: GEMINI_API_KEY missing from .env")
        
        genai.configure(api_key=self.api_key)
        
        # Filter schemas based on authorization whitelist
        self.gemini_tools = [{"function_declarations": []}]
        for schema in TOOL_SCHEMAS:
            if allowed_tools is None or schema["name"] in allowed_tools:
                self.gemini_tools[0]["function_declarations"].append({
                    "name": schema["name"],
                    "description": schema["description"],
                    "parameters": schema["parameters"]
                })

    def format_history(self, internal_history):
        formatted = []
        for msg in internal_history:
            # Standard conversational text
            if msg.get("role") in ["user", "model"] and msg.get("content"):
                formatted.append({"role": msg.get("role"), "parts": [{"text": msg.get("content")}]})
            
            # The Model requesting to use a tool
            elif msg.get("role") == "model" and msg.get("tool_calls"):
                parts = []
                for tc in msg["tool_calls"]:
                    parts.append({
                        "function_call": {
                            "name": tc["tool_name"],
                            "args": tc["arguments"]
                        }
                    })
                formatted.append({"role": "model", "parts": parts})
                
            # The System feeding the tool's result back to the Model
            elif msg.get("role") == "system" and msg.get("tool_results"):
                parts = []
                for tr in msg["tool_results"]:
                    parts.append({
                        "function_response": {
                            "name": tr["tool_name"],
                            # Gemini requires the response to be nested under a generic key like 'result' or 'content'
                            "response": {"content": tr["content"]} 
                        }
                    })
                # Gemini strictly enforces that function_responses originate from the "user" role
                formatted.append({"role": "user", "parts": parts})
                
        return formatted

    def _unpack_protobuf(self, obj):
        """Recursively converts Google Protobuf composites to native Python dicts/lists."""
        if hasattr(obj, 'items'):
            return {k: self._unpack_protobuf(v) for k, v in obj.items()}
        elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
            return [self._unpack_protobuf(v) for v in obj]
        return obj

    def think(self, system_prompt: str, history: list, tool_mode: str = "AUTO"):
        """The cognitive bridge. Sends the state and waits for a decision."""
        
        # Initialize the model dynamically with the current system state & LORE
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_prompt,
            tools=self.gemini_tools
        )

        gemini_history = self.format_history(history)

        # Safely omit the config in AUTO mode to prevent SDK dictionary crashes
        kwargs = {}
        if tool_mode != "AUTO":
            kwargs["tool_config"] = {"function_calling_config": {"mode": tool_mode}}

        # Build the conversation payload
        gemini_history = self.format_history(history)
        
        try:
            response = model.generate_content(gemini_history, **kwargs)
            
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