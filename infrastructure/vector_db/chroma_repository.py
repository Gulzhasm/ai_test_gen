import chromadb

from core.interfaces.vector_store import IVectorStore


class ChromaRepository(IVectorStore):
    def __init__ (self, collection_name: str):
        self.client = chromadb.PersistentClient(path="./db")
        self.collection_name = collection_name
        self.collection = self.client.get_or_create_collection(name=self.collection_name)

    def add(self, ids, documents, metadata):
        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=[metadata] * len(ids) if metadata else None
        )

    def query(self, query_text, n_results=5):
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        return results
    
    
    def delete(self, ids):
        self.collection.delete(ids=ids)
    
    def count(self):
        return self.collection.count()

    
