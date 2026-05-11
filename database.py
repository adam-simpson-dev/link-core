import sqlite3
import os

class DatabaseManager:
    """
    Handles the low-level SQLite operations for the LINK-CORE graph memory.
    """
    def __init__(self, db_path="memory.sqlite"):
        self.db_path = db_path
        # Connect to SQLite (creates the file if it doesn't exist)
        self.conn = sqlite3.connect(self.db_path)
        # CRITICAL: SQLite does not enforce foreign keys by default.
        self.conn.execute("PRAGMA foreign_keys = ON;")
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

    def add_node(self, label, display_name, uid=None):
        """Adds a new entity to the graph."""
        # If no UID is provided, we lowercase the display name and swap spaces for underscores
        if not uid:
            uid = display_name.lower().replace(" ", "_")
        
        query = "INSERT INTO nodes (uid, label, display_name) VALUES (?, ?, ?)"
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (uid, label, display_name))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            print(f"[!] Node with UID '{uid}' already exists.")
            return None

    def add_edge(self, source_uid, target_uid, relationship):
        """Creates a link between two nodes using their UIDs."""
        cursor = self.conn.cursor()
        
        # We need to find the IDs for the UIDs provided
        cursor.execute("SELECT id FROM nodes WHERE uid = ?", (source_uid,))
        source_res = cursor.fetchone()
        
        cursor.execute("SELECT id FROM nodes WHERE uid = ?", (target_uid,))
        target_res = cursor.fetchone()

        if not source_res or not target_res:
            print("[!] Could not find one or both nodes to link.")
            return None

        query = "INSERT INTO edges (source_id, target_id, relationship) VALUES (?, ?, ?)"
        cursor.execute(query, (source_res[0], target_res[0], relationship))
        self.conn.commit()
        return cursor.lastrowid

    def set_property(self, target_type, target_uid, key, value):
        """
        Sets a property for a node or an edge. 
        If it exists, it updates; if not, it creates.
        """
        cursor = self.conn.cursor()
        
        # Resolve the ID based on the target_type
        if target_type == 'NODE':
            cursor.execute("SELECT id FROM nodes WHERE uid = ?", (target_uid,))
        else:
            # For EDGES, we'd typically need a more complex lookup, 
            # but for now, we'll assume target_uid is the Edge ID.
            # We will refine Edge property setting later.
            pass

        result = cursor.fetchone()
        if not result:
            print(f"[!] Could not find {target_type} with UID {target_uid}")
            return False

        target_id = result[0]

        # The UPSERT command
        query = """
            INSERT INTO properties (target_type, target_id, key, value)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(target_type, target_id, key) 
            DO UPDATE SET value = excluded.value;
        """
        cursor.execute(query, (target_type, target_id, key, str(value)))
        self.conn.commit()
        return True

    def get_node_context(self, uid):
        """
        Retrieves everything the system knows about a specific UID 
        and flattens it into a descriptive string.
        """
        cursor = self.conn.cursor()

        # Get basic Node info
        cursor.execute("SELECT id, label, display_name FROM nodes WHERE uid = ?", (uid,))
        node = cursor.fetchone()
        if not node:
            return f"I have no record of an entity with UID '{uid}'."

        n_id, n_label, n_name = node
        context_parts = [f"{n_name} (a {n_label})"]

        # Get all Properties
        cursor.execute("SELECT key, value FROM properties WHERE target_type = 'NODE' AND target_id = ?", (n_id,))
        properties = cursor.fetchall()
        if properties:
            prop_list = ", ".join([f"{k}: {v}" for k, v in properties])
            context_parts.append(f"Traits: {prop_list}.")

        # Get all Relationships (Edges)
        # We look for connections where this node is either the source or the target
        cursor.execute('''
            SELECT e.relationship, n.display_name 
            FROM edges e
            JOIN nodes n ON e.target_id = n.id
            WHERE e.source_id = ?
        ''', (n_id,))
        relationships = cursor.fetchall()
        
        if relationships:
            rel_list = " and ".join([f"{rel} {target}" for rel, target in relationships])
            context_parts.append(f"Connections: {n_name} currently {rel_list}.")

        return " ".join(context_parts)

    def get_relevant_context(self, keywords: list) -> str:
        """Pulls only nodes that match specific keywords to prevent token bloat."""
        if not keywords:
            return "No keywords provided for context retrieval."
            
        cursor = self.conn.cursor()
        # Dynamic SQL query with multiple LIKE clauses
        conditions = " OR ".join(["uid LIKE ? OR label LIKE ? OR display_name LIKE ?" for _ in keywords])
        
        # Multiply keywords by 3 because we check 3 columns per keyword
        wildcard_keywords = []
        for kw in keywords:
            wildcard_keywords.extend([f"%{kw}%", f"%{kw}%", f"%{kw}%"])
            
        query = f"SELECT uid, label, display_name FROM nodes WHERE {conditions}"
        cursor.execute(query, wildcard_keywords)
        uids = [row[0] for row in cursor.fetchall()]
        
        if not uids:
            return "No relevant LORE found for those keywords."
            
        # Compile full context for all found nodes
        return "\n".join([self.get_node_context(uid) for uid in uids])
            
        return context_string

    def upsert_lore(self, target_uid: str, key: str, value: str):
        """Intelligently updates memory. Creates the node if it doesn't exist."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM nodes WHERE uid = ?", (target_uid,))
        result = cursor.fetchone()

        if not result:
            # Create a generic node if the AI is learning something entirely new
            display_name = target_uid.replace("_", " ").title()
            self.add_node(uid=target_uid, label="Entity", display_name=display_name)

        # Apply the property update
        success = self.set_property("NODE", target_uid, key, value)
        return "Memory updated successfully." if success else "Failed to update memory."

    def delete_node(self, uid: str):
        """Permanently erases a node and all connected edges via CASCADE."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM nodes WHERE uid = ?", (uid,))
        self.conn.commit()
        if cursor.rowcount > 0:
            return f"Node {uid} and its relationships deleted successfully."
        return f"No node found with UID {uid}."

    def close(self):
        """Safely close the connection."""
        self.conn.close()

if __name__ == "__main__":
    db = DatabaseManager()
    db.close()