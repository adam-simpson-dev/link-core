import sqlite3
import logging
from core_logger import setup_core_logger
from vector_memory import VectorManager

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path="memory.sqlite"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.vector = VectorManager() 
        self.last_accessed_uids = []
        self.initialize_schema()

    def initialize_schema(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nodes (
                uid TEXT PRIMARY KEY,
                node_type TEXT NOT NULL,
                display_name TEXT NOT NULL,
                aliases TEXT DEFAULT '[]',
                system_pointers TEXT DEFAULT '{}',
                traits TEXT DEFAULT '{}'
            )
        ''')
        
        # Edges map strictly to the UID text primary keys
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_uid TEXT NOT NULL,
                target_uid TEXT NOT NULL,
                relationship TEXT NOT NULL,
                FOREIGN KEY (source_uid) REFERENCES nodes (uid) ON DELETE CASCADE,
                FOREIGN KEY (target_uid) REFERENCES nodes (uid) ON DELETE CASCADE
            )
        ''')
        self.conn.commit()

    def upsert_lore(self, uid: str, node_type: str = "concept", display_name: str = None, new_traits: dict = None, new_pointers: dict = None, aliases: list = None):
        """Merges volatile JSON payloads without destroying the Identity Envelope."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT node_type, display_name, aliases, system_pointers, traits FROM nodes WHERE uid = ?", (uid,))
        row = cursor.fetchone()
        
        import json
        if row:
            db_type, db_name, db_aliases, db_pointers, db_traits = row
            
            merged_traits = json.loads(db_traits) if db_traits else {}
            if new_traits: 
                merged_traits.update(new_traits)
                # Null-stripping: Allow the AI to delete traits by passing null
                merged_traits = {k: v for k, v in merged_traits.items() if v is not None}
            
            merged_pointers = json.loads(db_pointers) if db_pointers else {}
            if new_pointers: 
                merged_pointers.update(new_pointers)
                # Null-stripping for pointers
                merged_pointers = {k: v for k, v in merged_pointers.items() if v is not None}
            
            final_aliases = json.dumps(aliases) if aliases is not None else db_aliases
            final_name = display_name or db_name
            final_type = node_type if node_type != "concept" else db_type

            cursor.execute("""
                UPDATE nodes 
                SET node_type = ?, display_name = ?, aliases = ?, system_pointers = ?, traits = ?
                WHERE uid = ?
            """, (final_type, final_name, final_aliases, json.dumps(merged_pointers), json.dumps(merged_traits), uid))
        else:
            final_name = display_name or uid.replace("_", " ").title()
            final_aliases = json.dumps(aliases or [])
            merged_pointers = json.dumps(new_pointers or {})
            merged_traits = json.dumps(new_traits or {})
            
            cursor.execute("""
                INSERT INTO nodes (uid, node_type, display_name, aliases, system_pointers, traits) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (uid, node_type, final_name, final_aliases, merged_pointers, merged_traits))

        self.conn.commit()
        
        # Shield ChromaDB from semantic noise
        envelope_text = self.generate_semantic_envelope(uid, final_name, final_aliases)
        self.vector.upsert_node_vector(uid, envelope_text)
        return f"Synchronized node: {uid}"

    def get_all_nodes(self):
        """Feeds the WebGL UI node graph."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT uid, node_type, display_name FROM nodes")
        return cursor.fetchall()

    def get_all_edges(self):
        """Feeds the WebGL UI edge graph."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, source_uid, target_uid, relationship FROM edges")
        return cursor.fetchall()

    def _estimate_tokens(self, text: str) -> float:
        """Fast heuristic for token weight without loading a heavy ML tokenizer."""
        return len(text.split()) * 1.3

    def get_relevant_context(self, keywords: list, max_tokens: int = 1500) -> str:
        """
        Hybrid Semantic Retrieval with Radial Constraints.
        """
        if not keywords: return "No context."
        seed_uids = set()
        query_string = " ".join(keywords)
        
        # The Compass: ChromaDB finds the entry points (Top 2 only to limit sprawl)
        seed_uids.update(self.vector.query_semantic_uids(query_string, n_results=2))

        # Keyword Fallback: Ensure explicit targets aren't missed
        cursor = self.conn.cursor()
        for kw in keywords:
            like_kw = f"%{kw}%"
            cursor.execute("SELECT uid FROM nodes WHERE uid LIKE ? OR display_name LIKE ? LIMIT 2", (like_kw, like_kw))
            seed_uids.update([row[0] for row in cursor.fetchall()])

        # The Map & The Guillotine: Assemble context until the token limit is hit
        self.last_accessed_uids = list(seed_uids)
        
        final_context_blocks = []
        current_token_weight = 0.0

        for uid in seed_uids:
            node_data = self.get_node_context(uid)
            block_weight = self._estimate_tokens(node_data)
            
            # If adding this node blows the limit, halt expansion.
            if current_token_weight + block_weight > max_tokens:
                logger.warning(f"[!] CONTEXT PRUNED: Hit {max_tokens} token limit at node '{uid}'.")
                break
                
            final_context_blocks.append(node_data)
            current_token_weight += block_weight

        return "\n".join(final_context_blocks) if final_context_blocks else "Empty LORE."

    def generate_semantic_envelope(self, uid: str, display_name: str, aliases: str) -> str:
        """
        Semantic Noise Isolation.
        Forces ChromaDB to index ONLY the identity envelope, blinding it to volatile traits.
        """
        import json
        try:
            alias_list = json.loads(aliases) if aliases else []
            alias_str = ", ".join(alias_list) if alias_list else "None"
        except Exception:
            alias_str = "None"
            
        return f"UID: {uid} | Name: {display_name} | Aliases: {alias_str}"

    def get_node_data(self, uid: str) -> dict:
        """Feeds the Panopticon GUI. Unpacks JSON payloads into UI-compatible arrays."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT display_name, node_type, system_pointers, traits FROM nodes WHERE uid = ?", (uid,))
        node = cursor.fetchone()
        
        if not node:
            return {"error": f"Node {uid} not found"}
            
        display_name, node_type, sys_pointers, traits = node
        
        import json
        try:
            traits_dict = json.loads(traits) if traits else {}
            pointers_dict = json.loads(sys_pointers) if sys_pointers else {}
        except json.JSONDecodeError:
            traits_dict, pointers_dict = {}, {}

        properties_array = [{"key": k, "value": str(v)} for k, v in traits_dict.items()]
        for k, v in pointers_dict.items():
            properties_array.append({"key": f"SYS_{k.upper()}", "value": str(v)})

        # Edges are strictly text UID matching
        cursor.execute("SELECT relationship, target_uid FROM edges WHERE source_uid = ?", (uid,))
        outgoing = [{"relationship": row[0], "target_uid": row[1], "target_name": row[1]} for row in cursor.fetchall()]
        
        cursor.execute("SELECT relationship, source_uid FROM edges WHERE target_uid = ?", (uid,))
        incoming = [{"relationship": row[0], "source_uid": row[1], "source_name": row[1]} for row in cursor.fetchall()]

        return {
            "id": uid, "uid": uid, "name": display_name, "display_name": display_name,
            "label": node_type, "class": node_type,
            "properties": properties_array,
            "outgoing_edges": outgoing, "incoming_edges": incoming
        }

    def get_node_context(self, uid: str) -> str:
        """Pulls properties and strictly Depth-1 edges, enriched with display names."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT node_type, display_name, system_pointers, traits FROM nodes WHERE uid = ?", (uid,))
        node = cursor.fetchone()
        if not node: return ""
        
        n_type, name, pointers, traits = node
        
        # Enriched Outgoing Links
        cursor.execute("""
            SELECT e.relationship, e.target_uid, n.display_name 
            FROM edges e 
            JOIN nodes n ON e.target_uid = n.uid 
            WHERE e.source_uid = ?
        """, (uid,))
        outgoing = [f"-[{row[0]}]-> {row[1]} ({row[2]})" for row in cursor.fetchall()]

        # Enriched Incoming Links
        cursor.execute("""
            SELECT e.relationship, e.source_uid, n.display_name 
            FROM edges e 
            JOIN nodes n ON e.source_uid = n.uid 
            WHERE e.target_uid = ?
        """, (uid,))
        incoming = [f"<-[{row[0]}]- {row[1]} ({row[2]})" for row in cursor.fetchall()]
        
        return (
            f"--- NODE ({n_type.upper()}): {uid} ({name}) ---\n"
            f"System Pointers: {pointers}\n"
            f"Traits: {traits}\n"
            f"Outgoing Links: {', '.join(outgoing) if outgoing else 'None'}\n"
            f"Incoming Links: {', '.join(incoming) if incoming else 'None'}\n"
        )

    def create_relationship(self, source_uid, target_uid, relationship):
        cursor = self.conn.cursor()
        
        for check_uid in [source_uid, target_uid]:
            cursor.execute("SELECT uid FROM nodes WHERE uid = ?", (check_uid,))
            if not cursor.fetchone():
                # Auto-Heal: Mint a stub immediately if the node is missing
                logger.warning(f"[!] Ghost Node Detected: '{check_uid}'. Auto-minting stub to preserve topography.")
                cursor.execute("INSERT INTO nodes (uid, node_type, display_name) VALUES (?, ?, ?)", (check_uid, "concept", check_uid))
                self.conn.commit()
        
        cursor.execute("INSERT INTO edges (source_uid, target_uid, relationship) VALUES (?, ?, ?)", 
                       (source_uid, target_uid, relationship))
        self.conn.commit()
        
        return f"Link created: {source_uid} -> {relationship} -> {target_uid}"
    
    def delete_relationship(self, source_uid: str, target_uid: str, relationship: str) -> bool:
        """Safely severs a specific topological edge."""
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM edges 
            WHERE source_uid = ? AND target_uid = ? AND relationship = ?
        """, (source_uid, target_uid, relationship))
        self.conn.commit()
        return cursor.rowcount > 0

    def rename_node(self, old_uid: str, new_uid: str) -> bool:
        """Migrates a primary key while preserving edges and vector synchronization."""
        cursor = self.conn.cursor()
        
        # Verify structural source exists
        cursor.execute("SELECT node_type, display_name, aliases, system_pointers, traits FROM nodes WHERE uid = ?", (old_uid,))
        row = cursor.fetchone()
        if not row: 
            return False
        
        node_type, display_name, aliases, system_pointers, traits = row
        
        # Mint the new identity envelope
        cursor.execute("""
            INSERT INTO nodes (uid, node_type, display_name, aliases, system_pointers, traits)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (new_uid, node_type, display_name, aliases, system_pointers, traits))
        
        # Re-route relational edges before deleting to protect foreign key constraints
        cursor.execute("UPDATE edges SET source_uid = ? WHERE source_uid = ?", (new_uid, old_uid))
        cursor.execute("UPDATE edges SET target_uid = ? WHERE target_uid = ?", (new_uid, old_uid))
        
        # Safely purge legacy row identifier
        cursor.execute("DELETE FROM nodes WHERE uid = ?", (old_uid,))
        self.conn.commit()
        
        # Synchronize Vector Space to stop ghost lookups
        self.vector.delete_vector(old_uid)
        envelope_text = self.generate_semantic_envelope(new_uid, display_name, aliases)
        self.vector.upsert_node_vector(new_uid, envelope_text)
        
        return True

    def delete_node(self, uid: str):
        """Standardized deletion for SQLite and Vector memory."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM nodes WHERE uid = ?", (uid,))
        if cursor.rowcount == 0:
            return f"Node '{uid}' not found."
            
        self.conn.commit()
        # Synchronize: Remove the semantic embedding so it doesn't haunt future searches
        self.vector.delete_vector(uid)
        return f"Node '{uid}' and all associated LORE permanently purged."

    def merge_nodes(self, target_uids: list, master_uid: str, display_name: str, synthesized_traits: dict):
        """
        Collapse multiple nodes into a single master identity,
        re-routing all edges and deduplicating overlapping connections.
        """
        import json
        cursor = self.conn.cursor()
        
        # Aggregate legacy aliases and pointers to ensure zero data loss
        master_aliases = set()
        master_pointers = {}
        
        for uid in target_uids:
            cursor.execute("SELECT aliases, system_pointers FROM nodes WHERE uid = ?", (uid,))
            row = cursor.fetchone()
            if row:
                try:
                    aliases = json.loads(row[0]) if row[0] else []
                    master_aliases.update(aliases)
                    pointers = json.loads(row[1]) if row[1] else {}
                    master_pointers.update(pointers)
                except Exception:
                    pass
                    
            # Inject old UIDs as aliases to absorb legacy searches
            master_aliases.add(uid.replace("_", " "))
        
        master_aliases.add(display_name)
            
        # Mint the new master node (or update if inheriting an existing primary key)
        self.upsert_lore(
            uid=master_uid,
            node_type="concept",
            display_name=display_name,
            new_traits=synthesized_traits,
            new_pointers=master_pointers,
            aliases=list(master_aliases)
        )
        
        # The Topological Splice: Re-route all adjacent edges to the master node
        placeholders = ','.join('?' for _ in target_uids)
        cursor.execute(f"UPDATE edges SET source_uid = ? WHERE source_uid IN ({placeholders})", [master_uid] + target_uids)
        cursor.execute(f"UPDATE edges SET target_uid = ? WHERE target_uid IN ({placeholders})", [master_uid] + target_uids)
        
        # Edge Deduplication (Scrub redundant links generated by the merger)
        cursor.execute("""
            DELETE FROM edges 
            WHERE id NOT IN (
                SELECT MIN(id) 
                FROM edges 
                GROUP BY source_uid, target_uid, relationship
            )
        """)
        
        # Execute the Purge
        for uid in target_uids:
            # Shield check: Do not delete the master if it anchored the original targets
            if uid != master_uid:
                self.delete_node(uid)
                
        self.conn.commit()
        return f"Spliced {len(target_uids)} nodes into {master_uid}."

    def wipe_database(self, confirm_wipe: bool = False):
        """CRITICAL: Full system reset."""
        if not confirm_wipe:
            return "Wipe aborted. Confirmation boolean missing."

        cursor = self.conn.cursor()
        
        # Purge legacy schema if it exists to permanently resolve the mismatch
        cursor.execute("DROP TABLE IF EXISTS properties")
        # Clear child tables first to respect strict foreign key constraints
        cursor.execute("DELETE FROM edges")
        # Clear parent table
        cursor.execute("DELETE FROM nodes")
        
        self.conn.commit()

        # Clear ChromaDB Collection
        # We delete the collection and recreate it to ensure a zero-byte state
        self.vector.client.delete_collection("lore_vectors")
        self.vector.collection = self.vector.client.create_collection(
            name="lore_vectors", 
            embedding_function=self.vector.embed_fn
        )

        self.last_accessed_uids.clear()
        logger.warning("[!] LORE GRAPH AND VECTOR MEMORY WIPED BY USER COMMAND.")
        return "System memory reset to factory defaults. All nodes and vectors purged."

    def scan_semantic_clusters(self, tier_1_threshold=0.90, tier_2_threshold=0.80):
        """
        Phase 18 Vector Radar: Scans concept nodes and groups them into merge tiers.
        """
        cursor = self.conn.cursor()
        # Restrict strict jurisdiction strictly to concept nodes
        cursor.execute("SELECT uid, display_name, aliases FROM nodes WHERE node_type = 'concept'")
        concept_nodes = cursor.fetchall()
        
        processed_uids = set()
        tier_1_clusters = [] # Auto-Merge Band
        tier_2_clusters = [] # Human Review Band
        
        for uid, name, aliases in concept_nodes:
            if uid in processed_uids: continue
                
            # The Core Shield: Do not compress root system architecture or the inbox
            if uid.startswith("sys_") or uid == "unassigned_inbox":
                continue

            # Regenerate the exact envelope text used for vector indexing
            envelope = self.generate_semantic_envelope(uid, name, aliases)
            
            # Fetch similarities from the vector engine
            matches = self.vector.get_similarity_scores(envelope, n_results=5)
            
            current_t1_cluster = [uid]
            current_t2_cluster = [uid]
            
            for match_uid, score in matches:
                if match_uid == uid or match_uid in processed_uids: continue
                    
                # Double-check jurisdiction: Do not merge hardware/locations
                cursor.execute("SELECT node_type FROM nodes WHERE uid = ?", (match_uid,))
                row = cursor.fetchone()
                if not row or row[0] != 'concept': continue
                
                if score >= tier_1_threshold:
                    current_t1_cluster.append(match_uid)
                    processed_uids.add(match_uid)
                elif score >= tier_2_threshold:
                    current_t2_cluster.append(match_uid)
                    processed_uids.add(match_uid)
            
            # Only append clusters if redundancies were actually found
            if len(current_t1_cluster) > 1:
                tier_1_clusters.append(current_t1_cluster)
            elif len(current_t2_cluster) > 1:
                tier_2_clusters.append(current_t2_cluster)
                
            processed_uids.add(uid)
            
        return {"tier_1": tier_1_clusters, "tier_2": tier_2_clusters}

    def close(self):
        self.conn.close()