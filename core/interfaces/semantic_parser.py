"""
Semantic parser interface for domain-agnostic AC parsing.

Abstracts NLP-based semantic extraction to enable different implementations
(spaCy, regex, hybrid, etc.).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class SemanticComponents:
    """Domain-agnostic semantic structure extracted from text."""

    # Core SVO (Subject-Verb-Object) components
    subject: str           # Who/what performs action (e.g., "user", "system")
    action_verb: str       # Core action (e.g., "click", "enable", "display")
    direct_object: str     # What is acted upon (e.g., "button", "menu item")

    # Extended components
    indirect_object: Optional[str] = None  # Secondary target
    modifiers: List[str] = field(default_factory=list)  # Conditions, constraints
    prepositions: List[Tuple[str, str]] = field(default_factory=list)  # (prep, obj) pairs

    # Semantic flags
    negation: bool = False          # Negative scenario indicator
    modal: Optional[str] = None     # Modal verb (should, must, can)
    tense: str = "present"          # Verb tense

    # Quality metrics
    confidence: float = 1.0         # Extraction confidence (0-1)
    method: str = "unknown"         # Parser method used

    def to_action_target_outcome(self) -> Tuple[str, str, str]:
        """Convert to action-target-outcome triple.

        Returns:
            Tuple of (action, target, outcome)
        """
        # Action is the verb
        action = self.action_verb

        # Target is the direct object
        target = self.direct_object

        # Outcome is derived from the verb and any modifiers
        if self.negation:
            outcome = f"is not {self.action_verb}d" if self.action_verb else "does not occur"
        else:
            outcome = f"is {self.action_verb}d" if self.action_verb else "occurs"

        return (action, target, outcome)

    def to_dict(self) -> dict:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "subject": self.subject,
            "action_verb": self.action_verb,
            "direct_object": self.direct_object,
            "indirect_object": self.indirect_object,
            "modifiers": self.modifiers,
            "prepositions": self.prepositions,
            "negation": self.negation,
            "modal": self.modal,
            "tense": self.tense,
            "confidence": self.confidence,
            "method": self.method
        }


class ISemanticParser(ABC):
    """Interface for semantic parsing of acceptance criteria."""

    @abstractmethod
    def parse(self, text: str) -> SemanticComponents:
        """Extract semantic components from text.

        Args:
            text: Raw AC text to parse

        Returns:
            SemanticComponents with extracted semantics
        """
        pass

    @abstractmethod
    def extract_action_target_outcome(
        self,
        text: str
    ) -> Tuple[str, str, str]:
        """Extract action-target-outcome triple.

        Convenience method for simple extraction.

        Args:
            text: Raw AC text

        Returns:
            Tuple of (action, target, outcome)
        """
        pass

    @abstractmethod
    def extract_entities(self, text: str) -> List[str]:
        """Extract named entities from text.

        Args:
            text: Raw text

        Returns:
            List of entity strings
        """
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if parser is ready and configured.

        Returns:
            True if parser can be used
        """
        pass

    @property
    @abstractmethod
    def parser_name(self) -> str:
        """Name of the parser implementation.

        Returns:
            Parser name string
        """
        pass
