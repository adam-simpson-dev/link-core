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
    print("[*] Aliases: 'lore <query>', 'remove <uid>', 'wipe lore'")
    
    while True:
        cmd = input("LINK-CORE > ").strip()
        if not cmd: continue
        if cmd.lower() in ["exit", "quit"]: break
        
        parts = cmd.split(" ", 1)
        base_cmd = parts[0].lower()
        arg_str = parts[1] if len(parts) > 1 else ""
        
        # --- HUMAN ALIAS ROUTER ---
        if base_cmd in ["help", "-h", "--help", "?"]:
            print("\n--- LINK-CORE COMMAND MANUAL ---")
            print("lore <keywords>    | Semantic & graph lookup (e.g., 'lore object')")
            print("remove <uid>       | Permanent node deletion (e.g., 'remove object')")
            print("wipe lore          | Full database factory reset (Safety locked)")
            print("health             | Poll system state and circuit breaker")
            print("unlock breaker     | Emergency breaker reset (recovers from fatal errors)")
            print("areas              | Fetch HASS area map (Room structure)")
            print("inspect <entity>   | Fetch HASS entity state (e.g., 'inspect light.kitchen')")
            print("control <args>     | e.g., 'control light turn_on light.kitchen'")
            print("event <name>       | Trigger HASS event (e.g., 'event protocol_alpha')")
            print("exit / quit        | Terminate uplink\n")
            continue # Skip execution for the help command
        
        elif base_cmd == "health":
            try:
                res = requests.get(f"{API_URL}/health")
                if res.status_code == 200:
                    data = res.json()
                    print(f"[*] SYSTEM STATUS: {data.get('status', 'UNKNOWN')}")
                    print(f"[*] VERSION: {data.get('version', 'N/A')}")
                    if data.get('last_error'):
                        print(f"[!] LAST ERROR: {data.get('last_error')}")
                else:
                    print(f"[-] Health endpoint returned {res.status_code}")
            except Exception as e:
                print(f"[FATAL] Health check failed: {e}")
            continue

        elif base_cmd == "lore":
            tool = "get_context"
            args = {"keywords": arg_str.split()}
            
        elif base_cmd == "remove":
            tool = "delete_node"
            args = {"uid": arg_str.strip()}
            
        elif base_cmd == "wipe" and arg_str.strip() == "lore":
            confirm = input("[!] CRITICAL: This will destroy all memory. Proceed? [Y/N]: ")
            if confirm.lower() == 'y':
                tool = "wipe_database"
                args = {"confirm_wipe": True}
            else:
                print("[-] Wipe aborted.")
                continue

        elif base_cmd == "unlock" and arg_str.strip() == "breaker":
            tool = "reset_breaker"
            args = {}

        # --- HASS DIAGNOSTIC ALIASES ---
        elif base_cmd == "areas":
            tool = "get_area_map"
            args = {}

        elif base_cmd == "inspect":
            tool = "inspect_entity"
            parts = arg_str.split(" ", 1)
            args = {"uid": parts[0]}
            if len(parts) > 1:
                args["start_time_iso"] = parts[1]

        elif base_cmd == "control":
            # Syntax: control light turn_on light.kitchen_main {"brightness": 255}
            tool = "control_home"
            parts = arg_str.split(" ", 3)
            if len(parts) >= 3:
                args = {
                    "domain": parts[0],
                    "service": parts[1],
                    "entity_id": parts[2]
                }
                # Safely parse optional kwargs (like brightness or colors)
                if len(parts) == 4: 
                    try:
                        args["kwargs"] = json.loads(parts[3])
                    except json.JSONDecodeError:
                        print("[-] Invalid JSON for kwargs. Executing without kwargs.")
                        continue
            else:
                print("[-] Usage: control <domain> <service> <entity_id> [kwargs_json]")
                continue

        elif base_cmd == "event":
            tool = "fire_home_event"
            parts = arg_str.split(" ", 1)
            args = {"event_name": parts[0]}
            if len(parts) > 1:
                try:
                    args["event_data"] = json.loads(parts[1])
                except json.JSONDecodeError:
                    print("[-] Invalid JSON for event_data.")
                    continue

        else:
            # Fallback to standard explicit API calls if raw JSON is provided
            tool = base_cmd
            try:
                args = json.loads(arg_str) if arg_str else {}
            except json.JSONDecodeError:
                print("[-] Invalid command alias or JSON payload.")
                continue
        
        # --- EXECUTION ---
        try:
            response = send_command(tool, args)
            result_data = response.get("result", {})

            if result_data.get("status") == "executed":
                data = result_data.get('data')
                print("[*] Result:")
                
                # Human-readable dictionary unpacking
                if isinstance(data, dict):
                    for key, val in data.items():
                        if isinstance(val, list):
                            print(f"  > {key}:")
                            for item in val:
                                print(f"      - {item}")
                        else:
                            print(f"  > {key}: {val}")
                            
                # Human-readable list unpacking
                elif isinstance(data, list):
                    for item in data:
                        print(f"  > {item}")
                        
                # Standard string fallback
                else:
                    print(f"  > {data}")
            else:
                print(f"[!] Error: {result_data.get('message', 'Unknown failure')}")
                
        except Exception as e:
            print(f"[FATAL] Connection to Core failed: {e}")

if __name__ == "__main__":
    main()