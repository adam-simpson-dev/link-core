import json
import logging
from core_logger import setup_core_logger
from database import DatabaseManager
from inference import InferenceEngine

setup_core_logger()
logger = logging.getLogger("LIBRARIAN")

def run_compression():
    logger.info("[*] Waking Librarian Daemon for Semantic Compression...")
    db = DatabaseManager()
    
    # Execute the Vector Radar
    clusters = db.scan_semantic_clusters()
    tier_1 = clusters.get("tier_1", [])
    tier_2 = clusters.get("tier_2", [])
    
    if not tier_1 and not tier_2:
        logger.info("[*] Topology is dense. No compression required.")
        return

    logger.info(f"[*] Radar detected {len(tier_1)} Auto-Merge clusters and {len(tier_2)} Review clusters.")
    
    # Process Tier 1 (Autonomous AI Synthesis)
    if tier_1:
        ai = InferenceEngine()
        
        system_prompt = (
            "You are the LINK-CORE Librarian daemon. Your strict directive is semantic compression. "
            "You will receive a JSON array representing redundant conceptual nodes. "
            "Your task is to synthesize them into a single, high-density JSON payload. "
            "CRITICAL: Return ONLY valid JSON matching this schema: "
            "{ \"master_display_name\": \"Shortest, most concise common name\", \"synthesized_traits\": { ...combined properties... } } "
            "Do not output markdown or conversational text. Output pure JSON."
        )

        cursor = db.conn.cursor()
        
        for cluster in tier_1:
            cluster_data = []
            for uid in cluster:
                cursor.execute("SELECT display_name, traits FROM nodes WHERE uid = ?", (uid,))
                row = cursor.fetchone()
                if row:
                    try:
                        traits = json.loads(row[1]) if row[1] else {}
                    except json.JSONDecodeError:
                        traits = {}
                    cluster_data.append({"uid": uid, "name": row[0], "traits": traits})
            
            logger.info(f"[*] Requesting Cognitive Synthesis for cluster: {cluster}...")
            
            payload = json.dumps(cluster_data, indent=2)
            # Temporarily unrestrict tools to prevent inference crashing on empty arrays
            decision = ai.think(system_prompt, [{"role": "user", "content": payload}], tool_mode="NONE")
            
            if decision["type"] == "error":
                logger.error(f"[!] Synthesis failed for {cluster}: {decision['content']}")
                continue
                
            try:
                # Discard markdown formatting if the model hallucinates a wrapper
                clean_json = decision["content"].replace('```json', '').replace('```', '').strip()
                result = json.loads(clean_json)
                
                master_name = result.get("master_display_name", cluster_data[0]["name"])
                merged_traits = result.get("synthesized_traits", {})
                
                # Anchor the new master UID to the shortest, cleanest identifier in the cluster
                shortest_uid = sorted(cluster, key=len)[0]
                
                logger.info(f"[*] Synthesis successful. Splice Target: {shortest_uid} ({master_name})")
                
                db.merge_nodes(
                    target_uids=cluster, 
                    master_uid=shortest_uid, 
                    display_name=master_name, 
                    synthesized_traits=merged_traits
                )
                
            except Exception as e:
                logger.error(f"[!] Failed to parse Librarian output for {cluster}: {e}\nRaw Output: {decision.get('content')}")

    # Process Tier 2 (Queue for Human Authorization)
    if tier_2:
        actions_taken = []
        for cluster in tier_2:
            actions_taken.append(f"REVIEW REQUIRED: Cluster collision detected at {cluster}")
            
        if actions_taken:
            db.upsert_lore(
                uid="sys_core_memory",
                new_traits={"pending_lint_reviews": actions_taken}
            )
            logger.info(f"[*] Queued {len(tier_2)} clusters into sys_core_memory for manual authorization.")

    logger.info("[*] Librarian cycle complete.")

if __name__ == "__main__":
    run_compression()