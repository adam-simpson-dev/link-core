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
    ai = InferenceEngine()

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

    # The Sterile System Prompt
    janitor_prompt = (
        "You are the LINK-CORE Janitor daemon. Your sole purpose is to organize orphan nodes. "
        "Review the provided JSON list of unassigned hardware and concepts. "
        "Use the 'modify_lore' tool to link these nodes to their logical parent concepts, locations, or hardware using the 'create_links' array. "
        "If you cannot logically deduce where a node belongs, do not guess. Leave it alone. "
        "Do not output conversational text. Output ONLY the tool call."
    )

    # Execution
    payload = f"UNASSIGNED NODES: {json.dumps(orphan_data, indent=2)}"
    logger.info(f"[*] Analyzing {len(orphan_data)} orphan nodes...")
    
    # Enforce Constrained Decoding to mathematically prevent JSON schema hallucinations
    decision = ai.think(janitor_prompt, [{"role": "user", "content": payload}], tool_mode="ANY")

    actions_taken = []

    if decision["type"] == "tool_call" and decision["tool_name"] == "modify_lore":
        args = decision["arguments"]
        
        # Execute the AI's re-mapping
        if "create_links" in args:
            for link in args["create_links"]:
                try:
                    db.create_relationship(link["source"], link["target"], link["relation"])
                    # Sever the tie to the inbox once mapped
                    cursor.execute("DELETE FROM edges WHERE source_uid = ? AND target_uid = 'unassigned_inbox'", (link["source"],))
                    actions_taken.append(f"Linked {link['source']} to {link['target']} via {link['relation']}.")
                except Exception as e:
                    logger.warning(f"[!] Janitor failed to create link {link['source']} -> {link['target']}: {e}")
            
            db.conn.commit()
            logger.info(f"[*] Grid Healed: Mapped {len(args['create_links'])} orphans.")
        else:
            logger.info("[*] Janitor analyzed orphans but made no changes.")
            actions_taken.append("Analyzed inbox. No logical mappings found.")
    else:
        logger.warning(f"[!] Janitor failed to generate valid tool execution: {decision}")
        actions_taken.append("Failed to generate valid mapping strategy.")

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