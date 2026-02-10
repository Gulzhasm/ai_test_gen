# Quick test script infrastructure/vector_db/chroma_repository.py
from infrastructure.vector_db.chroma_repository import ChromaRepository
from core.services.embeddings.test_step_embedder import TestStepEmbedder


repo = ChromaRepository("test_steps")

# Sample test case (matches your structure)
test_cases = [
    {
        'id': '270542-AC1',
        'title': 'Hand Tool menu access',
        'steps': [
            {'step': 1, 'action': 'Launch the application', 'expected': '...'},
            {'step': 2, 'action': 'Click on the Hand Tool icon', 'expected': '...'},
        ]
    }
]

embedder = TestStepEmbedder("test_collection")
count = embedder.store_steps(test_cases)
print(f"Stored {count} steps")

# Now test find_similar
results = embedder.find_similar("click hand tool")
print(results)