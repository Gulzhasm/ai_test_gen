"""
Hybrid AC parser combining embedding, spaCy NLP, and regex fallback.

Provides domain-agnostic parsing with graceful degradation:
1. Embedding (highest quality) - semantic similarity matching
2. spaCy (good quality) - linguistic dependency parsing
3. Regex (fallback) - pattern matching
"""
import os
import re
from typing import List, Optional, Tuple

from core.interfaces.semantic_parser import ISemanticParser, SemanticComponents
from core.services.ac_parser import ACParser, ACSemantics
from .spacy_parser import SpacySemanticParser, SPACY_AVAILABLE


class HybridACParser(ISemanticParser):
    """Hybrid parser combining embedding, spaCy NLP, and regex fallback.

    Uses a three-layer fallback chain:
    1. Embedding parser (if enabled and confidence >= threshold)
    2. spaCy parser (if available and confidence >= threshold)
    3. Regex parser (always available as fallback)
    """

    def __init__(
        self,
        prefer_nlp: bool = True,
        confidence_threshold: float = 0.7,
        spacy_model: str = "en_core_web_sm",
        embedding_enabled: Optional[bool] = None,
        embedding_threshold: float = 0.80
    ):
        """Initialize hybrid parser.

        Args:
            prefer_nlp: Prefer spaCy over regex when both available
            confidence_threshold: Minimum confidence to accept spaCy results
            spacy_model: spaCy model to use
            embedding_enabled: Enable embedding parser (default from env)
            embedding_threshold: Minimum confidence for embedding results
        """
        self._prefer_nlp = prefer_nlp
        self._confidence_threshold = confidence_threshold
        self._embedding_threshold = embedding_threshold

        # Check embedding enabled from env if not specified
        if embedding_enabled is None:
            embedding_enabled = os.getenv("EMBEDDING_ENABLED", "false").lower() == "true"
        self._embedding_enabled = embedding_enabled

        # Initialize parsers
        self._spacy_parser = SpacySemanticParser(model=spacy_model)
        self._regex_parser = ACParser()

        # Initialize embedding parser if enabled
        self._embedding_parser = None
        if self._embedding_enabled:
            try:
                from .embedding_parser import EmbeddingSemanticParser
                self._embedding_parser = EmbeddingSemanticParser(
                    threshold=embedding_threshold
                )
                if not self._embedding_parser.is_available:
                    print("Warning: Embedding parser enabled but not available")
                    self._embedding_parser = None
            except Exception as e:
                print(f"Warning: Failed to initialize embedding parser: {e}")
                self._embedding_parser = None

        # Track which parser was used
        self._last_method = "none"

    @property
    def is_available(self) -> bool:
        """Check if at least one parser is available."""
        return True  # Regex is always available

    @property
    def parser_name(self) -> str:
        """Name of the parser."""
        return "hybrid"

    @property
    def last_method(self) -> str:
        """Get the method used for the last parse."""
        return self._last_method

    @property
    def embedding_available(self) -> bool:
        """Check if embedding parser is available."""
        return self._embedding_parser is not None and self._embedding_parser.is_available

    def parse(self, text: str) -> SemanticComponents:
        """Parse AC text using best available method.

        Fallback chain: embedding → spaCy → regex

        Args:
            text: Raw AC text

        Returns:
            SemanticComponents with extracted semantics
        """
        # Clean the text
        clean_text = self._clean_text(text)

        # Layer 1: Try embedding first if available
        if self._embedding_parser and self._embedding_parser.is_available:
            embedding_result = self._embedding_parser.parse(clean_text)

            if embedding_result.confidence >= self._embedding_threshold:
                self._last_method = "embedding"
                return embedding_result

        # Layer 2: Try spaCy if available and preferred
        if self._prefer_nlp and self._spacy_parser.is_available:
            spacy_result = self._spacy_parser.parse(clean_text)

            if spacy_result.confidence >= self._confidence_threshold:
                self._last_method = "spacy"
                return spacy_result

        # Layer 3: Fall back to regex parser
        regex_result = self._parse_with_regex(clean_text)
        self._last_method = "regex"

        return regex_result

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
        components = self.parse(text)
        return components.to_action_target_outcome()

    def extract_entities(self, text: str) -> List[str]:
        """Extract named entities from text.

        Args:
            text: Raw text

        Returns:
            List of entity strings
        """
        if self._spacy_parser.is_available:
            return self._spacy_parser.extract_entities(text)

        # Fallback: extract capitalized words
        words = re.findall(r'\b[A-Z][a-zA-Z]*\b', text)
        return list(set(words))

    def parse_legacy(self, text: str) -> ACSemantics:
        """Parse using legacy ACParser for backward compatibility.

        Args:
            text: Raw AC text

        Returns:
            ACSemantics (legacy format)
        """
        return self._regex_parser.parse(text)

    def _clean_text(self, text: str) -> str:
        """Clean and normalize AC text.

        Args:
            text: Raw text

        Returns:
            Cleaned text
        """
        # Remove leading numbers/bullets
        text = re.sub(r'^\d+[\.)]\s*', '', text).strip()

        # Remove "Acceptance Criteria" header
        text = re.sub(
            r'^Acceptance Criteria:?\s*',
            '',
            text,
            flags=re.IGNORECASE
        )

        # Normalize whitespace
        text = ' '.join(text.split())

        return text

    def _parse_with_regex(self, text: str) -> SemanticComponents:
        """Parse using regex patterns.

        Args:
            text: Clean AC text

        Returns:
            SemanticComponents converted from regex result
        """
        # Use legacy parser
        ac_semantics = self._regex_parser.parse(text)

        # Convert to SemanticComponents
        return self._convert_from_legacy(ac_semantics)

    def _convert_from_legacy(
        self,
        ac_semantics: ACSemantics
    ) -> SemanticComponents:
        """Convert ACSemantics to SemanticComponents.

        Args:
            ac_semantics: Legacy ACSemantics

        Returns:
            SemanticComponents
        """
        # Extract action verb from action string
        action_parts = ac_semantics.action.split()
        action_verb = action_parts[0] if action_parts else ""

        return SemanticComponents(
            subject="user",  # Default subject
            action_verb=action_verb,
            direct_object=ac_semantics.target,
            indirect_object=None,
            modifiers=ac_semantics.conditions,
            prepositions=[],
            negation=ac_semantics.negation,
            modal=None,
            tense="present",
            confidence=0.6,  # Lower confidence for regex
            method="regex"
        )

    def get_all_results(self, text: str) -> dict:
        """Get results from all available parsers for comparison.

        Useful for debugging and evaluation.

        Args:
            text: Raw AC text

        Returns:
            Dictionary with all parser results
        """
        clean_text = self._clean_text(text)

        results = {
            "text": clean_text,
            "embedding": None,
            "spacy": None,
            "regex": None
        }

        # Get embedding result if available
        if self._embedding_parser and self._embedding_parser.is_available:
            embedding_result = self._embedding_parser.parse(clean_text)
            results["embedding"] = embedding_result.to_dict()

        # Get regex result
        regex_semantics = self._regex_parser.parse(clean_text)
        results["regex"] = {
            "action": regex_semantics.action,
            "target": regex_semantics.target,
            "outcome": regex_semantics.outcome,
            "conditions": regex_semantics.conditions,
            "negation": regex_semantics.negation,
            "boundary_cases": regex_semantics.boundary_cases
        }

        # Get spaCy result if available
        if self._spacy_parser.is_available:
            spacy_result = self._spacy_parser.parse(clean_text)
            results["spacy"] = spacy_result.to_dict()

        return results

    # Backward compatibility alias
    def get_both_results(self, text: str) -> dict:
        """Alias for get_all_results for backward compatibility."""
        return self.get_all_results(text)


def create_parser(
    prefer_nlp: bool = True,
    confidence_threshold: float = 0.7,
    embedding_enabled: Optional[bool] = None,
    embedding_threshold: float = 0.80
) -> HybridACParser:
    """Factory function to create a hybrid parser.

    Args:
        prefer_nlp: Prefer spaCy over regex
        confidence_threshold: Minimum confidence for spaCy results
        embedding_enabled: Enable embedding parser (default from env)
        embedding_threshold: Minimum confidence for embedding results

    Returns:
        Configured HybridACParser
    """
    return HybridACParser(
        prefer_nlp=prefer_nlp,
        confidence_threshold=confidence_threshold,
        embedding_enabled=embedding_enabled,
        embedding_threshold=embedding_threshold
    )
