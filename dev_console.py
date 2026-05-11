import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("CORE_API_URL")

def send_command(tool_name, args):
    """Bridges the physical gap via HTTP."""
    payload = {"tool_name": tool_name, "arguments": args}
    try:
        response = requests.post(f"{API_URL}/command", json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

def main():
    print(f"[*] LINK-CORE Remote Active | Target: {API_URL}")
    while True:
        cmd = input("LINK-CORE > ").strip()
        if cmd in ["exit", "quit"]: break
        
        try:
            # Simple parser: 'tool_name {"key": "val"}'
            parts = cmd.split(" ", 1)
            tool = parts[0]
            args = json.loads(parts[1]) if len(parts) > 1 else {}
            
            result = send_command(tool, args)
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(f"[!] Input Error: {e}. Format: tool_name {{'arg': 'val'}}")

if __name__ == "__main__":
    main()