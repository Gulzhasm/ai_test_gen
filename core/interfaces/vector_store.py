from abc import ABC, abstractmethod


class IVectorStore(ABC):
    """Interface for a simple vector store."""

    @abstractmethod
    def add(self, ids: list[str], documents: list[str], metadata: dict[str, str] | None = None):
        """Add documents to the vector store."""

    @abstractmethod
    def query(self, query_text: str, n_results: int = 5) -> list[dict[str,str]]:
        """Query the vector store and return relevant documents."""

    @abstractmethod
    def delete(self, ids: str):
        """Delete documents from the vector store by thier IDs"""

    @abstractmethod
    def count(self) -> int:
        """Return the number of items in the vector store."""
