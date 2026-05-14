import sqlite3
import logging
from vector_memory import VectorManager

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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT UNIQUE NOT NULL,
                label TEXT NOT NULL,
                display_name TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS properties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_type TEXT NOT NULL DEFAULT 'NODE',
                target_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                FOREIGN KEY (target_id) REFERENCES nodes (id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                relationship TEXT NOT NULL,
                FOREIGN KEY (source_id) REFERENCES nodes (id) ON DELETE CASCADE,
                FOREIGN KEY (target_id) REFERENCES nodes (id) ON DELETE CASCADE
            )
        ''')
        self.conn.commit()

    def upsert_lore(self, target_uid: str, key: str, value: str, target_type='NODE'):
        """Standardized property setter"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM nodes WHERE uid = ?", (target_uid,))
        res = cursor.fetchone()
        
        if not res:
            display_name = target_uid.replace("_", " ").title()
            cursor.execute("INSERT INTO nodes (uid, label, display_name) VALUES (?, ?, ?)", 
                           (target_uid, "Entity", display_name))
            n_id = cursor.lastrowid
        else:
            n_id = res[0]

        cursor.execute("INSERT OR REPLACE INTO properties (target_type, target_id, key, value) VALUES (?, ?, ?, ?)", 
                       (target_type, n_id, key, value))
        self.conn.commit()
        
        # Refresh Vector Index
        self.vector.upsert_node_vector(target_uid, self.get_node_context(target_uid))
        return f"Updated {target_uid}: {key}={value}"

    def batch_update_lore(self, entities: list = None, relationships: list = None):
        """Processes bulk data."""
        log = []
        if entities:
            for entity in entities:
                uid = entity.get("uid")
                props = entity.get("properties", {})
                for key, value in props.items():
                    self.upsert_lore(uid, key, str(value))
                log.append(uid)
            
        if relationships:
            for rel in relationships:
                self.create_relationship(rel.get("source_uid"), rel.get("target_uid"), rel.get("relationship"))
                
        return f"Batch sync complete. Nodes affected: {len(log)}"

    def get_all_nodes(self):
        """Feeds the WebGL UI node graph."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT uid, label, display_name FROM nodes")
        return cursor.fetchall()

    def get_all_edges(self):
        """Feeds the WebGL UI edge graph."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT e.id, s.uid, t.uid, e.relationship 
            FROM edges e
            JOIN nodes s ON e.source_id = s.id
            JOIN nodes t ON e.target_id = t.id
        """)
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
                logging.warning(f"[!] CONTEXT PRUNED: Hit {max_tokens} token limit at node '{uid}'.")
                break
                
            final_context_blocks.append(node_data)
            current_token_weight += block_weight

        return "\n".join(final_context_blocks) if final_context_blocks else "Empty LORE."

    def get_node_data(self, uid: str) -> dict:
        """Feeds the frontend GUI Inspector panel. Over-delivers keys for UI compatibility."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, display_name, label FROM nodes WHERE uid = ?", (uid,))
        node = cursor.fetchone()
        
        if not node:
            return {"error": f"Node {uid} not found"}
            
        n_id, display_name, label = node
        
        # Fetch Properties
        cursor.execute("SELECT key, value FROM properties WHERE target_id = ? AND target_type = 'NODE'", (n_id,))
        raw_props = cursor.fetchall()
        properties_array = [{"key": row[0], "value": row[1]} for row in raw_props]

        # Fetch Outgoing Edges
        cursor.execute("""
            SELECT e.relationship, n.uid, n.display_name 
            FROM edges e 
            JOIN nodes n ON e.target_id = n.id 
            WHERE e.source_id = ?
        """, (n_id,))
        outgoing = [{"relationship": row[0], "target_uid": row[1], "target_name": row[2]} for row in cursor.fetchall()]
        
        # Fetch Incoming Edges
        cursor.execute("""
            SELECT e.relationship, n.uid, n.display_name 
            FROM edges e 
            JOIN nodes n ON e.source_id = n.id 
            WHERE e.target_id = ?
        """, (n_id,))
        incoming = [{"relationship": row[0], "source_uid": row[1], "source_name": row[2]} for row in cursor.fetchall()]

        return {
            "id": uid,
            "uid": uid,
            "name": display_name,
            "display_name": display_name,
            "label": label,
            "class": label,
            "properties": properties_array,
            "outgoing_edges": outgoing,
            "incoming_edges": incoming
        }

    def get_node_context(self, uid: str) -> str:
        """Pulls properties and strictly Depth-1 edges."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, display_name FROM nodes WHERE uid = ?", (uid,))
        node = cursor.fetchone()
        if not node: return ""
        
        n_id, name = node

        # Property search
        cursor.execute("SELECT key, value FROM properties WHERE target_id = ? AND target_type = 'NODE'", (n_id,))
        props = [f"{row[0]}: {row[1]}" for row in cursor.fetchall()]
        
        # Edges (Depth 1)
        cursor.execute("""
            SELECT e.relationship, n.uid FROM edges e 
            JOIN nodes n ON e.target_id = n.id WHERE e.source_id = ?
        """, (n_id,))
        outgoing = [f"-[{row[0]}]-> {row[1]}" for row in cursor.fetchall()]

        cursor.execute("""
            SELECT e.relationship, n.uid FROM edges e 
            JOIN nodes n ON e.source_id = n.id WHERE e.target_id = ?
        """, (n_id,))
        incoming = [f"<-[{row[0]}]- {row[1]}" for row in cursor.fetchall()]
        
        return (
            f"--- NODE: {uid} ({name}) ---\n"
            f"Properties: {', '.join(props) if props else 'None'}\n"
            f"Outgoing Links: {', '.join(outgoing) if outgoing else 'None'}\n"
            f"Incoming Links: {', '.join(incoming) if incoming else 'None'}\n"
        )

    def create_relationship(self, source_uid, target_uid, relationship):
        cursor = self.conn.cursor()
        # Ensure nodes exist
        for uid in [source_uid, target_uid]:
            cursor.execute("SELECT id FROM nodes WHERE uid = ?", (uid,))
            if not cursor.fetchone():
                self.upsert_lore(uid, "status", "initialized")
        
        cursor.execute("SELECT id FROM nodes WHERE uid = ?", (source_uid,))
        s_id = cursor.fetchone()[0]
        cursor.execute("SELECT id FROM nodes WHERE uid = ?", (target_uid,))
        t_id = cursor.fetchone()[0]
        
        cursor.execute("INSERT INTO edges (source_id, target_id, relationship) VALUES (?, ?, ?)", 
                       (s_id, t_id, relationship))
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
        # Clear SQLite
        cursor.execute("DELETE FROM nodes")
        cursor.execute("DELETE FROM properties")
        cursor.execute("DELETE FROM edges")
        self.conn.commit()

        # Clear ChromaDB Collection
        # We delete the collection and recreate it to ensure a zero-byte state
        self.vector.client.delete_collection("lore_vectors")
        self.vector.collection = self.vector.client.create_collection(
            name="lore_vectors", 
            embedding_function=self.vector.embed_fn
        )

        self.last_accessed_uids.clear()
        logging.warning("[!] LORE GRAPH AND VECTOR MEMORY WIPED BY USER COMMAND.")
        return "System memory reset to factory defaults. All nodes and vectors purged."

    def close(self):
        self.conn.close()