"""
Semantic matcher for finding similar patterns using embedding similarity.

Uses cosine similarity to match input text against pre-computed pattern embeddings.
"""
from typing import List, Optional

import numpy as np

from .embedding_interface import (
    IEmbeddingProvider,
    SimilarityMatch,
    cosine_similarity
)
from .embedding_cache import EmbeddingCache
from .pattern_index import EmbeddingPatternIndex, PatternEntry


class SemanticMatcher:
    """Find similar patterns using embedding cosine similarity.

    Compares input text embedding against pre-computed pattern embeddings
    and returns best matches above a threshold.

    Usage:
        provider = create_embedding_provider()
        index = EmbeddingPatternIndex(provider)
        index.load_patterns()

        matcher = SemanticMatcher(provider, index)
        matches = matcher.find_similar("move above other objects", category="action")
        print(f"Best match: {matches[0].pattern_text}")  # "bring to front"
    """

    def __init__(
        self,
        provider: IEmbeddingProvider,
        pattern_index: EmbeddingPatternIndex,
        cache: Optional[EmbeddingCache] = None,
        threshold: float = 0.80
    ):
        """Initialize semantic matcher.

        Args:
            provider: Embedding provider for computing vectors
            pattern_index: Pre-computed pattern embeddings
            cache: Optional cache for input text embeddings
            threshold: Minimum similarity score to consider a match (0.0-1.0)
        """
        self._provider = provider
        self._index = pattern_index
        self._cache = cache or EmbeddingCache()
        self._threshold = threshold

    @property
    def threshold(self) -> float:
        """Current similarity threshold."""
        return self._threshold

    @threshold.setter
    def threshold(self, value: float) -> None:
        """Set similarity threshold."""
        self._threshold = max(0.0, min(1.0, value))

    def find_similar(
        self,
        text: str,
        category: Optional[str] = None,
        top_k: int = 5,
        include_below_threshold: bool = False
    ) -> List[SimilarityMatch]:
        """Find most similar patterns to input text.

        Args:
            text: Input text to match
            category: Optional category filter (action, outcome, boundary)
            top_k: Maximum number of matches to return
            include_below_threshold: If True, include matches below threshold

        Returns:
            List of SimilarityMatch sorted by score (highest first)
        """
        # Get or compute embedding for input text
        query_vector = self._get_embedding(text)
        if query_vector is None:
            return []

        # Get patterns to compare
        if category:
            patterns = self._index.get_patterns_by_category(category)
        else:
            patterns = self._index.get_all_patterns()

        if not patterns:
            return []

        # Compute similarities against all patterns
        matches = []
        for pattern in patterns:
            # Compare against canonical embedding
            score = cosine_similarity(query_vector, pattern.embedding)

            # Also compare against synonym embeddings and take best
            for syn_emb in pattern.synonym_embeddings:
                syn_score = cosine_similarity(query_vector, syn_emb)
                score = max(score, syn_score)

            # Apply threshold
            if score >= self._threshold or include_below_threshold:
                matches.append(SimilarityMatch(
                    pattern_id=pattern.pattern_id,
                    pattern_text=pattern.canonical,
                    category=pattern.category,
                    similarity_score=score,
                    metadata={
                        "subcategory": pattern.subcategory,
                        "regex_fallback": pattern.regex_fallback
                    }
                ))

        # Sort by score descending
        matches.sort(key=lambda m: m.similarity_score, reverse=True)

        return matches[:top_k]

    def _get_embedding(self, text: str) -> Optional[np.ndarray]:
        """Get embedding for text, using cache if available.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if failed
        """
        # Check cache
        cached = self._cache.get(text, self._provider.model_name)
        if cached:
            return cached.vector

        # Compute new embedding
        result = self._provider.embed(text)
        if result is None:
            return None

        # Cache and return
        self._cache.set(result)
        return result.vector

    def match_action(self, text: str) -> Optional[SimilarityMatch]:
        """Find best matching action pattern.

        Args:
            text: Input text

        Returns:
            Best SimilarityMatch or None if no match above threshold
        """
        matches = self.find_similar(text, category="action", top_k=1)
        return matches[0] if matches else None

    def match_outcome(self, text: str) -> Optional[SimilarityMatch]:
        """Find best matching outcome pattern.

        Args:
            text: Input text

        Returns:
            Best SimilarityMatch or None if no match above threshold
        """
        matches = self.find_similar(text, category="outcome", top_k=1)
        return matches[0] if matches else None

    def match_boundary(self, text: str) -> Optional[SimilarityMatch]:
        """Find best matching boundary condition pattern.

        Args:
            text: Input text

        Returns:
            Best SimilarityMatch or None if no match above threshold
        """
        matches = self.find_similar(text, category="boundary", top_k=1)
        return matches[0] if matches else None

    def match_all_categories(self, text: str) -> dict:
        """Find best match in each category.

        Args:
            text: Input text

        Returns:
            Dict with keys 'action', 'outcome', 'boundary' and SimilarityMatch values
        """
        return {
            "action": self.match_action(text),
            "outcome": self.match_outcome(text),
            "boundary": self.match_boundary(text)
        }

    def calculate_confidence(
        self,
        action_match: Optional[SimilarityMatch],
        outcome_match: Optional[SimilarityMatch]
    ) -> float:
        """Calculate overall confidence from action and outcome matches.

        Uses weighted average of match scores.

        Args:
            action_match: Best action match
            outcome_match: Best outcome match

        Returns:
            Confidence score 0.0-1.0
        """
        scores = []
        weights = []

        if action_match:
            scores.append(action_match.similarity_score)
            weights.append(0.6)  # Action is more important

        if outcome_match:
            scores.append(outcome_match.similarity_score)
            weights.append(0.4)

        if not scores:
            return 0.0

        # Weighted average
        total_weight = sum(weights)
        weighted_sum = sum(s * w for s, w in zip(scores, weights))
        return weighted_sum / total_weight

    def explain_match(
        self,
        text: str,
        category: Optional[str] = None,
        top_k: int = 3
    ) -> str:
        """Get human-readable explanation of matching results.

        Useful for debugging and understanding match decisions.

        Args:
            text: Input text
            category: Optional category filter
            top_k: Number of top matches to show

        Returns:
            Formatted string explaining matches
        """
        matches = self.find_similar(
            text, category, top_k, include_below_threshold=True
        )

        if not matches:
            return f"No matches found for: '{text}'"

        lines = [f"Matches for: '{text}'", "-" * 40]

        for i, match in enumerate(matches, 1):
            status = "MATCH" if match.similarity_score >= self._threshold else "below threshold"
            lines.append(
                f"{i}. [{status}] {match.pattern_text} "
                f"(score: {match.similarity_score:.3f}, category: {match.category})"
            )

        return "\n".join(lines)
