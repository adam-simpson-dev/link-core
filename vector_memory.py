import chromadb
from chromadb.utils import embedding_functions
import os

class VectorManager:
    def __init__(self, path="data/chroma_db"):
        # Local embedding model (~300MB RAM)
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection(
            name="lore_vectors", 
            embedding_function=self.embed_fn
        )

    def upsert_node_vector(self, uid, text_content):
        self.collection.upsert(ids=[uid], documents=[text_content], metadatas=[{"uid": uid}])

    def query_semantic_uids(self, query_text, n_results=5):
        results = self.collection.query(query_texts=[query_text], n_results=n_results)
        return [meta['uid'] for meta in results['metadatas'][0]]

    def delete_vector(self, uid):
        try: 
            self.collection.delete(ids=[uid])
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[!] Failed to purge vector for '{uid}'. Semantic ghost may persist. Error: {e}")

    def get_similarity_scores(self, query_text: str, n_results: int = 5):
        """
        Queries Chroma and converts L2 squared distance to Cosine Similarity.
        Returns a list of tuples: [(uid, similarity_score_float)]
        """
        results = self.collection.query(
            query_texts=[query_text], 
            n_results=n_results,
            include=["metadatas", "distances"]
        )
        
        matches = []
        if not results.get('distances') or not results['distances'][0]: 
            return matches
            
        for meta, distance in zip(results['metadatas'][0], results['distances'][0]):
            # SentenceTransformers output normalized vectors.
            # L2 Squared distance to Cosine Similarity conversion: S = 1 - (D / 2)
            similarity = 1.0 - (distance / 2.0)
            matches.append((meta['uid'], round(similarity, 4)))
            
        return matches