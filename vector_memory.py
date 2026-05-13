import chromadb
from chromadb.utils import embedding_functions
import os

class VectorManager:
    def __init__(self, path="./chroma_db"):
        # We use a local, lightweight embedding model (~300MB RAM)
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection(
            name="lore_vectors", 
            embedding_function=self.embed_fn
        )

    def upsert_node_vector(self, uid, text_content):
        """Indexes a node's meaning so it can be found semantically."""
        self.collection.upsert(
            ids=[uid],
            documents=[text_content],
            metadatas=[{"uid": uid}]
        )

    def query_semantic_uids(self, query_text, n_results=5):
        """Finds the most relevant UIDs based on meaning, not just keywords."""
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        # Extract the UIDs from metadata
        return [meta['uid'] for meta in results['metadatas'][0]]

    def delete_vector(self, uid):
        """Purge from vector memory."""
        try:
            self.collection.delete(ids=[uid])
        except:
            pass