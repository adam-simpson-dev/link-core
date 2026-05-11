from main import LinkCore

def run_console():
    # Spin up the Orchestrator
    core = LinkCore()
    
    print("\n" + "="*50)
    print(" LINK-CORE Developer Console ".center(50, "="))
    print("="*50)
    print("Available Commands:")
    print("  1. get_context <uid>")
    print("  2. update_memory <target_uid>, <key>, <value>")
    print("  3. control_home <domain>, <service>, <entity_id>")
    print("Type 'exit' to shut down.\n")

    while True:
        try:
            cmd = input("LINK-BRAIN> ")
            if cmd.lower() in ['exit', 'quit']:
                break
            
            # Simple parser to split the command from its arguments
            parts = cmd.split(" ", 1)
            tool = parts[0]

            if tool == "get_context":
                uid = parts[1].strip()
                core.process_tool_call("get_context", {"uid": uid})

            elif tool == "update_memory":
                # Split arguments by comma
                args = [a.strip() for a in parts[1].split(",")]
                core.process_tool_call("update_memory", {
                    "target_uid": args[0],
                    "key": args[1],
                    "value": args[2]
                })

            elif tool == "control_home":
                args = [a.strip() for a in parts[1].split(",")]
                core.process_tool_call("control_home", {
                    "domain": args[0],
                    "service": args[1],
                    "entity_id": args[2]
                })

            else:
                print(f"[!] Unknown tool: {tool}")

        except IndexError:
            print("[!] Argument Error. Make sure you are using commas to separate values.")
        except Exception as e:
            print(f"[!] System Error: {e}")

    core.shutdown()

if __name__ == "__main__":
    run_console()