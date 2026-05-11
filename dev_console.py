import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()
# Store the API URL in your environment variable for flexibility and security
API_URL = os.getenv("CORE_API_URL")

def send_command(tool_name, args, override=False):
    """Bridges the physical gap via HTTP."""
    payload = {"tool_name": tool_name, "arguments": args, "override": override}
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
            
            # Initial blind fire
            response = send_command(tool, args)
            result_data = response.get("result", {})
            
            # The Handshake Interception
            if result_data.get("status") == "pending_authorization":
                print(f"\n[!] ALERT: {result_data.get('message')}")
                auth = input(f"Authorize '{tool}'? [Y/N]: ").strip().upper()
                
                if auth == 'Y':
                    print("[*] Transmitting cryptographic override...")
                    # Re-fire with the key
                    response = send_command(tool, args, override=True)
                else:
                    print("[-] Action aborted by user.")
                    continue
            
            print(json.dumps(response, indent=2))
            
        except Exception as e:
            print(f"[!] Input Error: {e}. Format: tool_name {{'arg': 'val'}}")

if __name__ == "__main__":
    main()