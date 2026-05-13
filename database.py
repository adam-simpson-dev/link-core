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

    def get_relevant_context(self, keywords: list) -> str:
        """Hybrid Semantic Retrieval."""
        if not keywords: return "No context."
        uids = set()
        query_string = " ".join(keywords)
        
        # Semantic Check
        uids.update(self.vector.query_semantic_uids(query_string))
        
        # Keyword Check
        cursor = self.conn.cursor()
        for kw in keywords:
            like_kw = f"%{kw}%"
            cursor.execute("SELECT uid FROM nodes WHERE uid LIKE ? OR display_name LIKE ?", (like_kw, like_kw))
            uids.update([row[0] for row in cursor.fetchall()])

        self.last_accessed_uids = list(uids)
        return "\n".join([self.get_node_context(u) for u in uids]) if uids else "Empty LORE."

    def get_node_context(self, uid: str) -> str:
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, display_name FROM nodes WHERE uid = ?", (uid,))
        node = cursor.fetchone()
        if not node: return ""
        
        n_id, name = node
        # Ensure we filter by NODE type here as well
        cursor.execute("SELECT key, value FROM properties WHERE target_id = ? AND target_type = 'NODE'", (n_id,))
        props = [f"{row[0]}: {row[1]}" for row in cursor.fetchall()]
        
        cursor.execute("""
            SELECT e.relationship, n.uid FROM edges e 
            JOIN nodes n ON e.target_id = n.id WHERE e.source_id = ?
        """, (n_id,))
        rels = [f"{uid} {row[0]} {row[1]}" for row in cursor.fetchall()]
        
        return f"Node: {uid} ({name})\nProperties: {', '.join(props)}\nRelationships: {', '.join(rels)}"

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
    
    def close(self):
        self.conn.close()