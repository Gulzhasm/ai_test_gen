
from infrastructure.vector_db.chroma_repository import ChromaRepository


class TestStepEmbedder:
    store = ChromaRepository("test_steps")

    def __init__(self, collection_name: str = "test_steps"):
        #Composition: Has-a relationship with chroma repository
        self.store = ChromaRepository(collection_name)

    def store_steps(self, test_cases: list[dict]) -> int:
        # Delegates the storage of steps to the ChromaRepository
        ids = []
        documents = []
        for test_case in test_cases:
            for i, step in enumerate(test_case["steps"], 1):  # enumerate gives step number
                ids.append(f"{test_case['id']}_step_{i}")
                documents.append(step["action"])

        self.store.add(ids, documents, metadata=None)
        return len(ids)
       

    def find_similar(self, step_text: str, n_results: int = 3):
        """Find similar steps to the given step text using the ChromaRepository's search functionality."""
        return self.store.query(step_text, n_results)
    
    def get_reference_steps(self, feature_name: str, n_results: int = 10) -> list[str]:
        """Get existing steps related to a feature"""
        if self.store.count() == 0:
            return []
        
        results = self.find_similar(feature_name, n_results)
        # Filter to only return steps with good similarity scores (distance < 1.5)
        steps = []
        for doc, dist in zip(results['documents'][0], results['distances'][0]):
            if dist < 1.5:  
                steps.append(doc)
        return steps
    

