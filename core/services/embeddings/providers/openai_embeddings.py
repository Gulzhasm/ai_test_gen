"""
OpenAI Embedding Provider.

Uses OpenAI's text-embedding-3-small model for semantic similarity matching.
"""
import os
from typing import List, Optional

import numpy as np

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from ..embedding_interface import IEmbeddingProvider, EmbeddingResult


class OpenAIEmbeddingProvider(IEmbeddingProvider):
    """Embedding provider using OpenAI API.

    Default model: text-embedding-3-small (1536 dimensions, $0.02/1M tokens)
    Alternative: text-embedding-3-large (3072 dimensions, higher quality)
    """

    # Model dimensions mapping
    MODEL_DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,  # Legacy
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-small",
        timeout: int = 30,
        max_retries: int = 2
    ):
        """Initialize OpenAI embedding provider.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Embedding model name
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries on failure
        """
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._model = model
        self._timeout = timeout
        self._max_retries = max_retries
        self._client: Optional[OpenAI] = None
        self._dimensions = self.MODEL_DIMENSIONS.get(model, 1536)

    @property
    def provider_name(self) -> str:
        """Provider identifier."""
        return "openai"

    @property
    def model_name(self) -> str:
        """Model being used."""
        return self._model

    @property
    def dimensions(self) -> int:
        """Embedding vector dimensions."""
        return self._dimensions

    @property
    def client(self) -> Optional[OpenAI]:
        """Lazy initialization of OpenAI client."""
        if self._client is None and OPENAI_AVAILABLE and self._api_key:
            self._client = OpenAI(
                api_key=self._api_key,
                timeout=self._timeout,
                max_retries=self._max_retries
            )
        return self._client

    def embed(self, text: str) -> Optional[EmbeddingResult]:
        """Generate embedding for single text.

        Args:
            text: Text to embed

        Returns:
            EmbeddingResult or None on failure
        """
        if not self.is_available():
            return None

        try:
            # Clean text - OpenAI recommends replacing newlines
            clean_text = text.replace("\n", " ").strip()

            if not clean_text:
                return None

            response = self.client.embeddings.create(
                model=self._model,
                input=clean_text
            )

            embedding_data = response.data[0]
            vector = np.array(embedding_data.embedding)

            return EmbeddingResult(
                text=text,
                vector=vector,
                model=self._model,
                dimensions=len(vector),
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0
                }
            )

        except Exception as e:
            print(f"OpenAI embedding error: {e}")
            return None

    def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate embeddings for multiple texts efficiently.

        OpenAI API accepts up to 2048 inputs in a single request.

        Args:
            texts: List of texts to embed

        Returns:
            List of EmbeddingResults
        """
        if not self.is_available() or not texts:
            return []

        try:
            # Clean texts
            clean_texts = [t.replace("\n", " ").strip() for t in texts]
            # Filter empty
            valid_pairs = [(i, t) for i, t in enumerate(clean_texts) if t]

            if not valid_pairs:
                return []

            indices, valid_texts = zip(*valid_pairs)

            response = self.client.embeddings.create(
                model=self._model,
                input=list(valid_texts)
            )

            results = []
            for i, embedding_data in enumerate(response.data):
                original_idx = indices[i]
                vector = np.array(embedding_data.embedding)
                results.append(EmbeddingResult(
                    text=texts[original_idx],
                    vector=vector,
                    model=self._model,
                    dimensions=len(vector),
                    usage={
                        "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                        "total_tokens": response.usage.total_tokens if response.usage else 0
                    } if i == 0 else None  # Only include usage for first result
                ))

            return results

        except Exception as e:
            print(f"OpenAI batch embedding error: {e}")
            return []

    def is_available(self) -> bool:
        """Check if provider is configured and reachable."""
        if not OPENAI_AVAILABLE:
            return False

        if not self._api_key:
            return False

        return self.client is not None
