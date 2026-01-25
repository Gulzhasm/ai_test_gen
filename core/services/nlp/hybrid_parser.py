"""
Hybrid AC parser combining spaCy NLP with regex fallback.

Provides domain-agnostic parsing with graceful degradation.
"""
import re
from typing import List, Optional, Tuple

from core.interfaces.semantic_parser import ISemanticParser, SemanticComponents
from core.services.ac_parser import ACParser, ACSemantics
from .spacy_parser import SpacySemanticParser, SPACY_AVAILABLE


class HybridACParser(ISemanticParser):
    """Hybrid parser combining spaCy NLP with regex fallback.

    Uses spaCy for domain-agnostic semantic extraction when confidence
    is high enough, falling back to regex patterns for specific domains.
    """

    def __init__(
        self,
        prefer_nlp: bool = True,
        confidence_threshold: float = 0.7,
        spacy_model: str = "en_core_web_sm"
    ):
        """Initialize hybrid parser.

        Args:
            prefer_nlp: Prefer spaCy over regex when both available
            confidence_threshold: Minimum confidence to accept spaCy results
            spacy_model: spaCy model to use
        """
        self._prefer_nlp = prefer_nlp
        self._confidence_threshold = confidence_threshold

        # Initialize parsers
        self._spacy_parser = SpacySemanticParser(model=spacy_model)
        self._regex_parser = ACParser()

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

    def parse(self, text: str) -> SemanticComponents:
        """Parse AC text using best available method.

        Args:
            text: Raw AC text

        Returns:
            SemanticComponents with extracted semantics
        """
        # Clean the text
        clean_text = self._clean_text(text)

        # Try spaCy first if available and preferred
        if self._prefer_nlp and self._spacy_parser.is_available:
            spacy_result = self._spacy_parser.parse(clean_text)

            if spacy_result.confidence >= self._confidence_threshold:
                self._last_method = "spacy"
                return spacy_result

        # Fall back to regex parser
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

    def get_both_results(self, text: str) -> dict:
        """Get results from both parsers for comparison.

        Useful for debugging and evaluation.

        Args:
            text: Raw AC text

        Returns:
            Dictionary with both parser results
        """
        clean_text = self._clean_text(text)

        results = {
            "text": clean_text,
            "regex": None,
            "spacy": None
        }

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


def create_parser(
    prefer_nlp: bool = True,
    confidence_threshold: float = 0.7
) -> HybridACParser:
    """Factory function to create a hybrid parser.

    Args:
        prefer_nlp: Prefer spaCy over regex
        confidence_threshold: Minimum confidence for spaCy results

    Returns:
        Configured HybridACParser
    """
    return HybridACParser(
        prefer_nlp=prefer_nlp,
        confidence_threshold=confidence_threshold
    )
