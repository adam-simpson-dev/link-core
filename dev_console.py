import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()
# Store the API URL in your environment variable for flexibility and security
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
        if cmd.lower() in ["exit", "quit"]: break
        
        try:
            parts = cmd.split(" ", 1)
            tool = parts[0]
            args = json.loads(parts[1]) if len(parts) > 1 else {}
            
            # Direct execution
            response = send_command(tool, args)
            result_data = response.get("result", {})

            # Handle Display (Extract the 'data' or show the error)
            if result_data.get("status") == "executed":
                print(f"[*] Result:\n{result_data.get('data')}")
            else:
                print(f"[!] Error: {result_data.get('message', 'Unknown failure')}")
            
        except Exception as e:
            print(f"[!] Input Error: {e}. Format: tool_name {{'arg': 'val'}}")

if __name__ == "__main__":
    main()