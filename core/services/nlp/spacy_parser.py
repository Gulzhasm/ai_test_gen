"""
spaCy-based semantic parser for acceptance criteria.

Uses dependency parsing for domain-agnostic semantic extraction.
"""
from typing import List, Optional, Tuple

from core.interfaces.semantic_parser import ISemanticParser, SemanticComponents

# Try to import spaCy (catch all errors including runtime/compatibility issues)
try:
    import spacy
    from spacy.tokens import Doc, Token, Span
    SPACY_AVAILABLE = True
except Exception:
    # Catches ImportError, compatibility errors (Python 3.14+), etc.
    SPACY_AVAILABLE = False
    spacy = None
    Doc = None
    Token = None
    Span = None


class SpacySemanticParser(ISemanticParser):
    """spaCy-based semantic parser using dependency parsing."""

    # Dependency labels for subjects
    SUBJECT_DEPS = {"nsubj", "nsubjpass", "csubj", "csubjpass", "agent", "expl"}

    # Dependency labels for objects
    OBJECT_DEPS = {"dobj", "pobj", "iobj", "attr", "oprd"}

    # Verbs indicating actions
    ACTION_VERBS = {
        "click", "select", "enter", "type", "submit", "press", "navigate",
        "open", "close", "expand", "collapse", "drag", "drop", "scroll",
        "enable", "disable", "show", "hide", "display", "toggle", "check",
        "uncheck", "choose", "pick", "add", "remove", "delete", "create",
        "update", "edit", "modify", "save", "cancel", "confirm", "verify",
        "validate", "view", "see", "appear", "disappear", "load", "refresh"
    }

    # Modal verbs
    MODALS = {"should", "must", "can", "could", "will", "would", "may", "might"}

    # Negation words
    NEGATION_WORDS = {"not", "no", "never", "neither", "nor", "cannot", "n't"}

    def __init__(self, model: str = "en_core_web_sm"):
        """Initialize spaCy parser.

        Args:
            model: spaCy model name to load
        """
        self._model_name = model
        self._nlp = None

    @property
    def nlp(self):
        """Lazy load spaCy model."""
        if self._nlp is None and SPACY_AVAILABLE:
            try:
                self._nlp = spacy.load(self._model_name)
            except OSError:
                print(f"spaCy model '{self._model_name}' not found.")
                print(f"Install with: python -m spacy download {self._model_name}")
        return self._nlp

    @property
    def is_available(self) -> bool:
        """Check if spaCy is available."""
        if not SPACY_AVAILABLE:
            return False
        return self.nlp is not None

    @property
    def parser_name(self) -> str:
        """Name of the parser."""
        return "spacy"

    def parse(self, text: str) -> SemanticComponents:
        """Extract semantic components using dependency parsing.

        Args:
            text: Raw AC text

        Returns:
            SemanticComponents with extracted semantics
        """
        if not self.is_available:
            return SemanticComponents(
                subject="",
                action_verb="",
                direct_object="",
                confidence=0.0,
                method="spacy_unavailable"
            )

        doc = self.nlp(text)

        # Find the root verb (main action)
        root = self._find_root_verb(doc)

        # Extract subject
        subject = self._extract_subject(doc, root)

        # Extract verb/action
        action_verb = root.lemma_ if root else ""

        # Extract direct object
        direct_object = self._extract_direct_object(doc, root)

        # Extract indirect object
        indirect_object = self._extract_indirect_object(doc, root)

        # Extract modifiers (prepositional phrases, adverbs)
        modifiers = self._extract_modifiers(doc, root)

        # Extract preposition-object pairs
        prepositions = self._extract_prepositions(doc, root)

        # Detect negation
        negation = self._detect_negation(doc, root)

        # Detect modal
        modal = self._detect_modal(doc, root)

        # Detect tense
        tense = self._detect_tense(root) if root else "present"

        # Calculate confidence
        confidence = self._calculate_confidence(root, subject, direct_object)

        return SemanticComponents(
            subject=subject,
            action_verb=action_verb,
            direct_object=direct_object,
            indirect_object=indirect_object,
            modifiers=modifiers,
            prepositions=prepositions,
            negation=negation,
            modal=modal,
            tense=tense,
            confidence=confidence,
            method="spacy"
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
        components = self.parse(text)
        return components.to_action_target_outcome()

    def extract_entities(self, text: str) -> List[str]:
        """Extract named entities from text.

        Args:
            text: Raw text

        Returns:
            List of entity strings
        """
        if not self.is_available:
            return []

        doc = self.nlp(text)
        return [ent.text for ent in doc.ents]

    def _find_root_verb(self, doc: "Doc") -> Optional["Token"]:
        """Find the main verb (ROOT or first VERB).

        Args:
            doc: spaCy Doc

        Returns:
            Root verb token or None
        """
        # First try to find ROOT that is a verb
        for token in doc:
            if token.dep_ == "ROOT" and token.pos_ == "VERB":
                return token

        # Try to find ROOT regardless of POS
        for token in doc:
            if token.dep_ == "ROOT":
                # If ROOT is not a verb, look for a verb child
                for child in token.children:
                    if child.pos_ == "VERB":
                        return child
                return token

        # Fallback: first verb in sentence
        for token in doc:
            if token.pos_ == "VERB":
                return token

        return None

    def _extract_subject(self, doc: "Doc", root: Optional["Token"]) -> str:
        """Extract subject from dependency tree.

        Args:
            doc: spaCy Doc
            root: Root verb token

        Returns:
            Subject string
        """
        if root is None:
            return ""

        # Look for subject in root's children
        for child in root.children:
            if child.dep_ in self.SUBJECT_DEPS:
                # Include compound nouns
                subject_span = self._get_noun_chunk(child)
                return subject_span

        # Look for passive subject (by + agent)
        for child in root.children:
            if child.dep_ == "agent":
                for grandchild in child.children:
                    if grandchild.dep_ == "pobj":
                        return self._get_noun_chunk(grandchild)

        # Default to "user" for imperative sentences (no explicit subject)
        if root and root.pos_ == "VERB" and root.tag_ == "VB":
            return "user"

        return ""

    def _extract_direct_object(
        self,
        doc: "Doc",
        root: Optional["Token"]
    ) -> str:
        """Extract direct object from dependency tree.

        Args:
            doc: spaCy Doc
            root: Root verb token

        Returns:
            Direct object string
        """
        if root is None:
            return ""

        # Look for direct object
        for child in root.children:
            if child.dep_ == "dobj":
                return self._get_noun_chunk(child)

        # Look for prepositional object if no direct object
        for child in root.children:
            if child.dep_ == "prep":
                for grandchild in child.children:
                    if grandchild.dep_ == "pobj":
                        return self._get_noun_chunk(grandchild)

        # Look for attribute (for linking verbs)
        for child in root.children:
            if child.dep_ == "attr":
                return self._get_noun_chunk(child)

        return ""

    def _extract_indirect_object(
        self,
        doc: "Doc",
        root: Optional["Token"]
    ) -> Optional[str]:
        """Extract indirect object from dependency tree.

        Args:
            doc: spaCy Doc
            root: Root verb token

        Returns:
            Indirect object string or None
        """
        if root is None:
            return None

        for child in root.children:
            if child.dep_ == "iobj" or child.dep_ == "dative":
                return self._get_noun_chunk(child)

        return None

    def _extract_modifiers(
        self,
        doc: "Doc",
        root: Optional["Token"]
    ) -> List[str]:
        """Extract modifiers (adverbs, prepositional phrases).

        Args:
            doc: spaCy Doc
            root: Root verb token

        Returns:
            List of modifier strings
        """
        modifiers = []

        if root is None:
            return modifiers

        # Adverbs
        for child in root.children:
            if child.dep_ == "advmod":
                modifiers.append(child.text)

        # Prepositional phrases (as conditions)
        for child in root.children:
            if child.dep_ == "prep":
                prep_phrase = child.text
                for grandchild in child.children:
                    if grandchild.dep_ == "pobj":
                        prep_phrase += " " + self._get_noun_chunk(grandchild)
                modifiers.append(prep_phrase)

        # Conditional clauses
        for token in doc:
            if token.dep_ == "mark" and token.text.lower() in ("if", "when", "while", "after", "before"):
                # Get the clause
                clause = " ".join([t.text for t in token.head.subtree])
                modifiers.append(clause)

        return modifiers

    def _extract_prepositions(
        self,
        doc: "Doc",
        root: Optional["Token"]
    ) -> List[Tuple[str, str]]:
        """Extract preposition-object pairs.

        Args:
            doc: spaCy Doc
            root: Root verb token

        Returns:
            List of (preposition, object) tuples
        """
        preps = []

        if root is None:
            return preps

        for child in root.children:
            if child.dep_ == "prep":
                prep = child.text
                for grandchild in child.children:
                    if grandchild.dep_ == "pobj":
                        obj = self._get_noun_chunk(grandchild)
                        preps.append((prep, obj))

        return preps

    def _detect_negation(
        self,
        doc: "Doc",
        root: Optional["Token"]
    ) -> bool:
        """Detect negation in the sentence.

        Args:
            doc: spaCy Doc
            root: Root verb token

        Returns:
            True if negation detected
        """
        if root is None:
            return False

        # Check for negation modifier on root
        for child in root.children:
            if child.dep_ == "neg":
                return True

        # Check for negation words anywhere
        for token in doc:
            if token.text.lower() in self.NEGATION_WORDS:
                return True
            if token.text.lower().endswith("n't"):
                return True

        return False

    def _detect_modal(
        self,
        doc: "Doc",
        root: Optional["Token"]
    ) -> Optional[str]:
        """Detect modal verb.

        Args:
            doc: spaCy Doc
            root: Root verb token

        Returns:
            Modal verb string or None
        """
        if root is None:
            return None

        # Check for auxiliary modal
        for child in root.children:
            if child.dep_ == "aux" and child.text.lower() in self.MODALS:
                return child.text.lower()

        return None

    def _detect_tense(self, root: "Token") -> str:
        """Detect verb tense.

        Args:
            root: Root verb token

        Returns:
            Tense string (past, present, future)
        """
        if root is None:
            return "present"

        tag = root.tag_
        morph = root.morph.to_dict()

        # Check morphological features
        tense = morph.get("Tense", "Pres")

        if tense == "Past":
            return "past"
        elif "will" in [c.text.lower() for c in root.children if c.dep_ == "aux"]:
            return "future"
        else:
            return "present"

    def _get_noun_chunk(self, token: "Token") -> str:
        """Get full noun phrase for a token.

        Args:
            token: Token to expand

        Returns:
            Full noun phrase string
        """
        # Collect compound nouns and modifiers
        parts = []

        # Get left modifiers (compounds, adjectives)
        for child in token.children:
            if child.dep_ in ("compound", "amod", "det", "nummod", "poss"):
                if child.i < token.i:  # Only left children
                    parts.append(child.text)

        parts.append(token.text)

        # Get right modifiers (prepositional phrases for compound nouns)
        for child in token.children:
            if child.dep_ == "prep" and child.text.lower() == "of":
                for grandchild in child.children:
                    if grandchild.dep_ == "pobj":
                        parts.append("of")
                        parts.append(grandchild.text)

        return " ".join(parts)

    def _calculate_confidence(
        self,
        root: Optional["Token"],
        subject: str,
        direct_object: str
    ) -> float:
        """Calculate extraction confidence.

        Args:
            root: Root verb token
            subject: Extracted subject
            direct_object: Extracted direct object

        Returns:
            Confidence score (0-1)
        """
        confidence = 0.0

        # Has root verb
        if root is not None:
            confidence += 0.4

        # Has subject
        if subject:
            confidence += 0.3

        # Has direct object
        if direct_object:
            confidence += 0.3

        return confidence
