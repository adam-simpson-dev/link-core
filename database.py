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
        """Pulls properties and strictly Depth-1 edges."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT node_type, display_name, system_pointers, traits FROM nodes WHERE uid = ?", (uid,))
        node = cursor.fetchone()
        if not node: return ""
        
        n_type, name, pointers, traits = node
        
        cursor.execute("SELECT relationship, target_uid FROM edges WHERE source_uid = ?", (uid,))
        outgoing = [f"-[{row[0]}]-> {row[1]}" for row in cursor.fetchall()]

        cursor.execute("SELECT relationship, source_uid FROM edges WHERE target_uid = ?", (uid,))
        incoming = [f"<-[{row[0]}]- {row[1]}" for row in cursor.fetchall()]
        
        return (
            f"--- NODE ({n_type.upper()}): {uid} ({name}) ---\n"
            f"System Pointers: {pointers}\n"
            f"Traits: {traits}\n"
            f"Outgoing Links: {', '.join(outgoing) if outgoing else 'None'}\n"
            f"Incoming Links: {', '.join(incoming) if incoming else 'None'}\n"
        )

    def create_relationship(self, source_uid, target_uid, relationship):
        import time
        cursor = self.conn.cursor()
        
        for check_uid in [source_uid, target_uid]:
            cursor.execute("SELECT uid FROM nodes WHERE uid = ?", (check_uid,))
            if not cursor.fetchone():
                # I/O Buffer Fallback: Give SQLite 50ms to flush the commit before throwing a fatal error
                time.sleep(0.05)
                cursor.execute("SELECT uid FROM nodes WHERE uid = ?", (check_uid,))
                if not cursor.fetchone():
                    raise ValueError(f"Relational Error: Node '{check_uid}' does not exist. Upsert it first.")
        
        cursor.execute("INSERT INTO edges (source_uid, target_uid, relationship) VALUES (?, ?, ?)", 
                       (source_uid, target_uid, relationship))
        self.conn.commit()
        
        return f"Link created: {source_uid} -> {relationship} -> {target_uid}"
    
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

    def close(self):
        self.conn.close()