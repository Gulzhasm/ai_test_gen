from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class IVectorStore(ABC):
    """Interface for a simple vector store."""

    @abstractmethod
    def add(self, ids: List[str], documents: List[str], metadata: Optional[Dict[str, str]] = None):
        """Add documents to the vector store."""
        pass

    @abstractmethod
    def query(self, query_text: str, n_results: int = 5) -> List[Dict[str,str]]:
        """Query the vector store and return relevant documents."""
        pass

    @abstractmethod
    def delete(self, ids: str):
        """Delete documents from the vector store by thier IDs"""
        pass

    @abstractmethod
    def count(self) -> int:
        """Return the number of items in the vector store."""
        pass