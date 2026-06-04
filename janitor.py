import sqlite3
import json
import logging
from core_logger import setup_core_logger
from database import DatabaseManager
from inference import InferenceEngine
from datetime import datetime

setup_core_logger()
logger = logging.getLogger("JANITOR")

def heal_grid():
    logger.info("[*] Waking Janitor Agent for Grid Healing...")
    db = DatabaseManager()
    # Explicitly restrict the daemon to memory modification. Strip all hardware control capabilities.
    ai = InferenceEngine(allowed_tools=["modify_lore"])

    # Fetch the Orphans
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT n.uid, n.display_name, n.system_pointers, n.traits 
        FROM nodes n
        JOIN edges e ON n.uid = e.source_uid
        WHERE e.target_uid = 'unassigned_inbox'
    """)
    orphans = cursor.fetchall()

    if not orphans:
        logger.info("[*] Grid Optimal. Inbox empty. Terminating.")
        return

    orphan_data = [
        {"uid": o[0], "name": o[1], "pointers": json.loads(o[2]), "traits": json.loads(o[3])} 
        for o in orphans
    ]

    # Fetch Valid Targets (The Map)
    cursor.execute("SELECT uid, display_name FROM nodes WHERE node_type IN ('location', 'concept', 'hardware')")
    valid_targets = [{"uid": row[0], "name": row[1]} for row in cursor.fetchall()]

    # The Sterile System Prompt
    janitor_prompt = (
        "You are the LINK-CORE Janitor daemon. Your sole purpose is to organize orphan nodes. "
        "Review the provided JSON list of UNASSIGNED NODES. "
        "Use the 'modify_lore' tool to link these nodes to their logical parent using ONLY the UIDs provided in the VALID TARGETS list. "
        "Under no circumstances are you to hallucinate a UID. If a logical target does not exist in the VALID TARGETS list, leave the node unassigned. "
        "You MUST populate the 'agent_reasoning' field in the tool call with a brief logical justification for your mappings so human admins can audit your deductions. "
        "Do not output conversational text. Output ONLY the tool call."
    )

    # Execution
    payload = (
        f"VALID TARGETS: {json.dumps(valid_targets, indent=2)}\n\n"
        f"UNASSIGNED NODES: {json.dumps(orphan_data, indent=2)}"
    )
    
    logger.info(f"[*] Analyzing {len(orphan_data)} orphan nodes against {len(valid_targets)} valid targets...")
    
    decision = ai.think(janitor_prompt, [{"role": "user", "content": payload}], tool_mode="ANY")

    actions_taken = []

    if decision["type"] == "tool_call" and decision["tool_name"] == "modify_lore":
        args = decision["arguments"]
        
        # Extract the AI's internal reasoning
        reasoning = args.get("agent_reasoning", "No logical justification provided by the agent.")
        actions_taken.append(f"LOGIC AUDIT: {reasoning}")
        
        # Execute the AI's re-mapping
        if "create_links" in args:
            for link in args["create_links"]:
                try:
                    db.create_relationship(link["source"], link["target"], link["relation"])
                    db.delete_relationship(link["source"], "unassigned_inbox", "requires_triage")
                    actions_taken.append(f"ACTION: Linked {link['source']} to {link['target']} via {link['relation']}.")
                except Exception as e:
                    logger.warning(f"[!] Janitor failed to create link {link['source']} -> {link['target']}: {e}")
            
            db.conn.commit()
            logger.info(f"[*] Grid Healed: Mapped {len(args['create_links'])} orphans.")
        else:
            logger.info("[*] Janitor analyzed orphans but made no changes.")
            actions_taken.append("ACTION: Analyzed inbox. No logical mappings found.")
    else:
        logger.warning(f"[!] Janitor failed to generate valid tool execution: {decision}")
        actions_taken.append("FATAL: Failed to generate valid mapping strategy.")

    # Write the Machine Log to Core Memory
    current_time_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    db.upsert_lore(
        uid="sys_core_memory",
        new_traits={
            "last_janitor_run": current_time_iso,
            "janitor_latest_actions": actions_taken
        }
    )
    logger.info("[*] Janitor Report written to Core Memory. Terminating.")

if __name__ == "__main__":
    heal_grid()