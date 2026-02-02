"""
Embedding-based semantic parser for AC text.

Uses embedding similarity to match input text against canonical patterns,
enabling recognition of novel phrasings and synonyms.
"""
import os
from typing import List, Optional, Tuple

from core.interfaces.semantic_parser import ISemanticParser, SemanticComponents
from core.services.embeddings import (
    IEmbeddingProvider,
    EmbeddingCache,
    EmbeddingPatternIndex,
    SemanticMatcher,
    SimilarityMatch,
    create_embedding_provider,
)


class EmbeddingSemanticParser(ISemanticParser):
    """Semantic parser using embedding similarity matching.

    Embeds input AC text and finds the most similar canonical patterns
    using cosine similarity. Enables matching of:
    - Novel phrasings ("move above other objects" → "bring to front")
    - Synonyms ("elevate z-order" → "bring to front")
    - Paraphrases ("put in front of everything" → "bring to front")

    Usage:
        parser = EmbeddingSemanticParser()
        result = parser.parse("User can move the shape above all other objects")
        print(f"Action: {result.action_verb}")  # "bring"
        print(f"Confidence: {result.confidence}")  # 0.92
    """

    def __init__(
        self,
        provider: Optional[IEmbeddingProvider] = None,
        cache: Optional[EmbeddingCache] = None,
        pattern_index: Optional[EmbeddingPatternIndex] = None,
        threshold: float = 0.80,
        patterns_file: str = "patterns/ac_patterns.json"
    ):
        """Initialize embedding parser.

        Args:
            provider: Embedding provider (defaults to OpenAI)
            cache: Embedding cache (defaults to file-based)
            pattern_index: Pre-loaded pattern index
            threshold: Minimum similarity for match (0.0-1.0)
            patterns_file: Path to patterns JSON file
        """
        self._threshold = threshold
        self._patterns_file = patterns_file
        self._initialized = False

        # Check if embedding is enabled via environment
        embedding_enabled = os.getenv("EMBEDDING_ENABLED", "false").lower() == "true"
        if not embedding_enabled:
            self._provider = None
            self._cache = None
            self._index = None
            self._matcher = None
            return

        # Initialize provider
        self._provider = provider or create_embedding_provider()
        if self._provider is None or not self._provider.is_available():
            self._cache = None
            self._index = None
            self._matcher = None
            return

        # Initialize cache
        self._cache = cache or EmbeddingCache()

        # Initialize pattern index
        if pattern_index:
            self._index = pattern_index
        else:
            self._index = EmbeddingPatternIndex(
                self._provider,
                self._cache,
                patterns_file
            )
            try:
                self._index.load_patterns()
            except FileNotFoundError as e:
                print(f"Warning: Could not load patterns: {e}")
                self._index = None

        # Initialize matcher
        if self._index:
            self._matcher = SemanticMatcher(
                self._provider,
                self._index,
                self._cache,
                threshold
            )
            self._initialized = True
        else:
            self._matcher = None

    @property
    def is_available(self) -> bool:
        """Check if parser is ready to use."""
        return (
            self._initialized and
            self._provider is not None and
            self._provider.is_available() and
            self._matcher is not None
        )

    @property
    def parser_name(self) -> str:
        """Parser identifier."""
        return "embedding"

    @property
    def threshold(self) -> float:
        """Current similarity threshold."""
        return self._threshold

    def parse(self, text: str) -> SemanticComponents:
        """Parse AC text using embedding similarity.

        Args:
            text: Raw AC text

        Returns:
            SemanticComponents with extracted semantics
        """
        if not self.is_available:
            return self._empty_result()

        # Find matching action pattern
        action_match = self._matcher.match_action(text)

        # Find matching outcome pattern
        outcome_match = self._matcher.match_outcome(text)

        # Find matching boundary pattern
        boundary_match = self._matcher.match_boundary(text)

        # Calculate overall confidence
        confidence = self._calculate_confidence(action_match, outcome_match)

        # Extract action verb from matched pattern
        action_verb = self._extract_action_verb(action_match)

        # Build modifiers from boundary match
        modifiers = []
        if boundary_match:
            modifiers.append(boundary_match.pattern_text)

        # Determine negation from patterns
        negation = self._detect_negation(action_match, outcome_match)

        return SemanticComponents(
            subject="user",
            action_verb=action_verb,
            direct_object=action_match.pattern_text if action_match else "",
            indirect_object=outcome_match.pattern_text if outcome_match else None,
            modifiers=modifiers,
            prepositions=[],
            negation=negation,
            modal=None,
            tense="present",
            confidence=confidence,
            method="embedding"
        )

    def extract_action_target_outcome(
        self,
        text: str
    ) -> Tuple[str, str, str]:
        """Extract action-target-outcome triple.

        Args:
            text: Raw AC text

        Returns:
            Tuple of (action, target, outcome)
        """
        result = self.parse(text)
        return result.to_action_target_outcome()

    def extract_entities(self, text: str) -> List[str]:
        """Extract entities (not supported by embedding parser).

        Args:
            text: Raw text

        Returns:
            Empty list (entity extraction requires NER)
        """
        return []

    def _calculate_confidence(
        self,
        action_match: Optional[SimilarityMatch],
        outcome_match: Optional[SimilarityMatch]
    ) -> float:
        """Calculate overall confidence from matches.

        Action match is weighted more heavily (60%) than outcome (40%).

        Args:
            action_match: Best action pattern match
            outcome_match: Best outcome pattern match

        Returns:
            Confidence score 0.0-1.0
        """
        if not action_match and not outcome_match:
            return 0.0

        scores = []
        weights = []

        if action_match:
            scores.append(action_match.similarity_score)
            weights.append(0.6)

        if outcome_match:
            scores.append(outcome_match.similarity_score)
            weights.append(0.4)

        # Weighted average
        total_weight = sum(weights)
        weighted_sum = sum(s * w for s, w in zip(scores, weights))
        return weighted_sum / total_weight

    def _extract_action_verb(
        self,
        action_match: Optional[SimilarityMatch]
    ) -> str:
        """Extract action verb from matched pattern.

        Args:
            action_match: Matched action pattern

        Returns:
            Action verb string
        """
        if not action_match:
            return ""

        # Get canonical pattern text
        pattern_text = action_match.pattern_text

        # Extract first word as action verb
        # "bring to front" → "bring"
        # "enable" → "enable"
        parts = pattern_text.split()
        return parts[0] if parts else ""

    def _detect_negation(
        self,
        action_match: Optional[SimilarityMatch],
        outcome_match: Optional[SimilarityMatch]
    ) -> bool:
        """Detect if this is a negative scenario.

        Args:
            action_match: Matched action pattern
            outcome_match: Matched outcome pattern

        Returns:
            True if negative scenario
        """
        negative_patterns = {
            "disable", "hide", "is disabled", "is hidden",
            "cannot", "no selection"
        }

        if action_match and action_match.pattern_text.lower() in negative_patterns:
            return True

        if outcome_match and outcome_match.pattern_text.lower() in negative_patterns:
            return True

        return False

    def _empty_result(self) -> SemanticComponents:
        """Return empty result when parser unavailable."""
        return SemanticComponents(
            subject="",
            action_verb="",
            direct_object="",
            confidence=0.0,
            method="embedding"
        )

    def explain_parse(self, text: str) -> str:
        """Get detailed explanation of parse result.

        Useful for debugging and understanding match decisions.

        Args:
            text: Input text

        Returns:
            Human-readable explanation
        """
        if not self.is_available:
            return "Embedding parser not available"

        lines = [f"Parse explanation for: '{text}'", "=" * 50]

        # Action matches
        lines.append("\nAction matches:")
        action_matches = self._matcher.find_similar(
            text, category="action", top_k=3, include_below_threshold=True
        )
        for m in action_matches:
            status = "MATCH" if m.similarity_score >= self._threshold else "below"
            lines.append(f"  [{status}] {m.pattern_text}: {m.similarity_score:.3f}")

        # Outcome matches
        lines.append("\nOutcome matches:")
        outcome_matches = self._matcher.find_similar(
            text, category="outcome", top_k=3, include_below_threshold=True
        )
        for m in outcome_matches:
            status = "MATCH" if m.similarity_score >= self._threshold else "below"
            lines.append(f"  [{status}] {m.pattern_text}: {m.similarity_score:.3f}")

        return "\n".join(lines)
