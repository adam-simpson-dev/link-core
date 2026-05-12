import sqlite3
import os

class DatabaseManager:
    """
    Handles the low-level SQLite operations for the LINK-CORE graph memory.
    """
    def __init__(self, db_path="memory.sqlite"):
        self.db_path = db_path
        # Connect to SQLite (creates the file if it doesn't exist)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        # CRITICAL: SQLite does not enforce foreign keys by default.
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.last_accessed_uids = [] # Tracking data wake in GUI
        self.initialize_schema()

    def initialize_schema(self):
        """Create the Triadic Schema tables if they don't already exist."""
        cursor = self.conn.cursor()
        # Nodes: The Entities (People, Pets, Rooms)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT UNIQUE NOT NULL,
                label TEXT NOT NULL,
                display_name TEXT
            )
        ''')

        # Edges: The Relationships (Connections between Nodes)
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

        # Properties: Metadata for either Nodes or Edges
        # target_id refers to either nodes.id or edges.id based on target_type
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS properties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_type TEXT NOT NULL CHECK (target_type IN ('NODE', 'EDGE')),
                target_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                UNIQUE(target_type, target_id, key)
            )
        ''')

        self.conn.commit()
        print(f"[*] Memory Engine Initialized: {self.db_path}")

    # --- GUI FETCHERS ---
    def get_all_nodes(self):
        """Fetches every entity for the 3D visualizer."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT uid, label, display_name FROM nodes")
        return cursor.fetchall()

    def get_all_edges(self):
        """Fetches relationships using UIDs for the frontend linker."""
        cursor = self.conn.cursor()
        query = """
            SELECT e.id, n1.uid, n2.uid, e.relationship
            FROM edges e
            JOIN nodes n1 ON e.source_id = n1.id
            JOIN nodes n2 ON e.target_id = n2.id
        """
        cursor.execute(query)
        return cursor.fetchall()


    # --- LORE LOGIC ---
    def get_node_context(self, uid):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, label, display_name FROM nodes WHERE uid = ?", (uid,))
        node = cursor.fetchone()
        if not node: return f"UID '{uid}' not found."

        n_id, n_label, n_name = node
        context = [f"{n_name} ({n_label})"]

        cursor.execute("SELECT key, value FROM properties WHERE target_type = 'NODE' AND target_id = ?", (n_id,))
        props = [f"{k}: {v}" for k, v in cursor.fetchall()]
        if props: context.append(f"Traits: {', '.join(props)}")

        cursor.execute("SELECT e.relationship, n.display_name FROM edges e JOIN nodes n ON e.target_id = n.id WHERE e.source_id = ?", (n_id,))
        rels = [f"{r} {t}" for r, t in cursor.fetchall()]
        if rels: context.append(f"Connections: {' and '.join(rels)}")

        return " | ".join(context)

    def get_relevant_context(self, keywords: list) -> str:
        if not keywords: 
            return "No keywords provided."
            
        cursor = self.conn.cursor()
        uids = set() # Use a set to prevent duplicate pings on the same node

        for kw in keywords:
            like_kw = f"%{kw}%"
            
            # Search Node Names
            cursor.execute("SELECT uid FROM nodes WHERE uid LIKE ? OR label LIKE ? OR display_name LIKE ?", (like_kw, like_kw, like_kw))
            uids.update([row[0] for row in cursor.fetchall()])
            
            # Search Properties
            cursor.execute("""
                SELECT n.uid FROM properties p 
                JOIN nodes n ON p.target_id = n.id 
                WHERE p.value LIKE ? OR p.key LIKE ?
            """, (like_kw, like_kw))
            uids.update([row[0] for row in cursor.fetchall()])

            # Search Edges
            # If a link is found, we want BOTH connected nodes to light up
            cursor.execute("""
                SELECT n1.uid, n2.uid FROM edges e
                JOIN nodes n1 ON e.source_id = n1.id
                JOIN nodes n2 ON e.target_id = n2.id
                WHERE e.relationship LIKE ?
            """, (like_kw,))
            for row in cursor.fetchall():
                uids.update([row[0], row[1]])

        # Update the telemetry tracker for the 3D Radar Pings
        self.last_accessed_uids = list(uids)
        
        return "\n".join([self.get_node_context(u) for u in uids]) if uids else "No lore found."

    def get_node_data(self, uid: str):
        """Fetches structured JSON data for the UI Inspector."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, label, display_name FROM nodes WHERE uid = ?", (uid,))
        node = cursor.fetchone()
        if not node: return {"error": "Node not found."}
        
        n_id, n_label, n_name = node
        cursor.execute("SELECT key, value FROM properties WHERE target_type = 'NODE' AND target_id = ?", (n_id,))
        props = [{"key": k, "value": v} for k, v in cursor.fetchall()]
        
        return {"uid": uid, "label": n_label, "display_name": n_name, "properties": props}

    def upsert_lore(self, target_uid: str, key: str, value: str):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM nodes WHERE uid = ?", (target_uid,))
        res = cursor.fetchone()
        if not res:
            display_name = target_uid.replace("_", " ").title()
            cursor.execute("INSERT INTO nodes (uid, label, display_name) VALUES (?, ?, ?)", (target_uid, "Entity", display_name))
            n_id = cursor.lastrowid
        else:
            n_id = res[0]
        cursor.execute("INSERT OR REPLACE INTO properties (target_type, target_id, key, value) VALUES ('NODE', ?, ?, ?)", (n_id, key, value))
        self.conn.commit()
        return f"Updated {target_uid}: {key}={value}"

    def create_relationship(self, source_uid, target_uid, relationship):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM nodes WHERE uid = ?", (source_uid,))
        s_res = cursor.fetchone()
        cursor.execute("SELECT id FROM nodes WHERE uid = ?", (target_uid,))
        t_res = cursor.fetchone()

        if s_res and t_res:
            cursor.execute(
                "INSERT INTO edges (source_id, target_id, relationship) VALUES (?, ?, ?)",
                (s_res[0], t_res[0], relationship)
            )
            self.conn.commit()
            return f"Link established: {source_uid} --[{relationship}]--> {target_uid}"
        return "Error: One or both UIDs do not exist."

    def add_node(self, uid, label, display_name=None):
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO nodes (uid, label, display_name) VALUES (?, ?, ?)", (uid, label, display_name))
        self.conn.commit()

    def delete_node(self, uid: str):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM nodes WHERE uid = ?", (uid,))
        self.conn.commit()
        return f"Deleted {uid}." if cursor.rowcount > 0 else "Not found."

    def wipe_database(self):
        """Erases all data and resets auto-increment counters. Schema remains intact."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM edges")
        cursor.execute("DELETE FROM properties")
        cursor.execute("DELETE FROM nodes")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('nodes', 'edges', 'properties')")
        self.conn.commit()
        
        self.last_accessed_uids.clear() # Clear the UI telemetry buffer
        return "CRITICAL: The LORE graph has been completely wiped."

    def batch_update_lore(self, entities: list, relationships: list = None):
        """Processes a bulk JSON payload from the LLM."""
        log = []
        for entity in entities:
            uid = entity.get("uid")
            props = entity.get("properties", {})
            for key, value in props.items():
                self.upsert_lore(uid, key, str(value))
            log.append(uid)
            
        if relationships:
            for rel in relationships:
                self.create_relationship(rel.get("source_uid"), rel.get("target_uid"), rel.get("relationship"))
                
        return f"Batch processed {len(entities)} entities and {len(relationships or [])} relationships. Processed UIDs: {', '.join(log)}"

    def close(self):
        self.conn.close()