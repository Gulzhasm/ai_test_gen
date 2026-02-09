# Quick test script infrastructure/vector_db/chroma_repository.py
from infrastructure.vector_db.chroma_repository import ChromaRepository

repo = ChromaRepository("test_steps")

# Add some test steps
repo.add(
    ids=["step1", "step2", "step3"],
    documents=["Click login button", "Enter username", "Verify dashboard loads"],
    metadata={"type": "ui"}
)

# Query for similar
results = repo.query("authenticate user", n_results=2)
print(results)

# Check count
print(f"Total items: {repo.count()}")
