import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Replace with your LXC's static IP
API_BASE_URL = os.getenv("CORE_API_URL", "http://192.168.0.103:8000")

def send_command(tool_name, arguments):
    """Sends the command over the wire to the LXC API."""
    url = f"{API_BASE_URL}/command"
    payload = {
        "tool_name": tool_name,
        "arguments": arguments
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status() # Raise error if the API is down
        return response.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

def run_console():
    print("\n" + "="*50)
    print(" LINK-CORE Remote Console ".center(50, "="))
    print(f"Target: {API_BASE_URL}")
    print("="*50)

    while True:
        try:
            cmd = input("LINK-REMOTE> ")
            if cmd.lower() in ['exit', 'quit']: break
            
            parts = cmd.split(" ", 1)
            tool = parts[0]
            
            # Simple UI-side parsing for our common tools
            if tool == "control_home":
                args = [a.strip() for a in parts[1].split(",")]
                result = send_command("control_home", {
                    "domain": args[0], "service": args[1], "entity_id": args[2]
                })
            elif tool == "get_context":
                result = send_command("get_context", {"uid": parts[1].strip()})
            else:
                print("[!] Local parser doesn't support that tool yet, but sending anyway...")
                result = send_command(tool, json.loads(parts[1]))

            print(f"Server Response: {json.dumps(result, indent=2)}")

        except Exception as e:
            print(f"[!] Error: {e}")

if __name__ == "__main__":
    run_console()