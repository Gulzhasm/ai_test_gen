
from infrastructure.vector_db.chroma_repository import ChromaRepository

# Template/boilerplate steps that should NOT be stored or returned as references
_SKIP_PATTERNS = [
    "pre-req:",
    "launch the",
    "close the",
    "exit the",
    "log out",
    "from the home screen, select 'new file'",
    "select 'new file'",
]


def _is_template_step(action: str) -> bool:
    """Check if a step is a boilerplate template step (pre-req, launch, close, create file)."""
    lower = action.strip().lower()
    return any(pattern in lower for pattern in _SKIP_PATTERNS)


def _is_generic_step(action: str) -> bool:
    """Check if a step is too generic to be a useful reference.

    Generic steps just repeat the feature title verbatim instead of
    describing a specific UI interaction (e.g. 'Locate the Line Style
    Options — Color, Thickness, Dashed Line options in the Properties Panel').
    """
    lower = action.strip().lower()
    # Steps that just say "Locate the <feature> options" or "Verify <feature> can be controlled"
    generic_phrases = [
        "locate the",
        "verify",
        "access the",
    ]
    # If the step starts with a generic phrase AND contains no specific UI control
    # (i.e., it just restates the feature name), it's generic
    specific_controls = [
        "color picker", "dropdown", "numeric input", "checkbox", "toggle",
        "button", "slider", "radio", "tab ", "menu item", "swatch",
        "field", "dialog", "modal", "toolbar button",
    ]
    for phrase in generic_phrases:
        if lower.startswith(phrase):
            # If it contains a specific UI control mention, it's useful
            if any(ctrl in lower for ctrl in specific_controls):
                return False
            # If the step is very short or just restates a feature name, it's generic
            if len(lower) > 80 and not any(ctrl in lower for ctrl in specific_controls):
                return True
    return False


def _deduplicate_steps(steps: list[str]) -> list[str]:
    """Remove near-duplicate reference steps based on word overlap."""
    if len(steps) <= 1:
        return steps

    unique = [steps[0]]
    for candidate in steps[1:]:
        candidate_words = set(candidate.lower().split())
        is_dup = False
        for existing in unique:
            existing_words = set(existing.lower().split())
            if not candidate_words or not existing_words:
                continue
            overlap = len(candidate_words & existing_words) / len(candidate_words | existing_words)
            if overlap > 0.8:
                is_dup = True
                break
        if not is_dup:
            unique.append(candidate)
    return unique


class TestStepEmbedder:
    store = ChromaRepository("test_steps")

    def __init__(self, collection_name: str = "test_steps"):
        #Composition: Has-a relationship with chroma repository
        self.store = ChromaRepository(collection_name)

    def store_steps(self, test_cases: list[dict]) -> int:
        """Store feature-specific steps (skips boilerplate template steps)."""
        ids = []
        documents = []
        for test_case in test_cases:
            for i, step in enumerate(test_case["steps"], 1):
                action = step["action"]
                # Skip template/boilerplate steps — they add noise to reference pool
                if _is_template_step(action):
                    continue
                ids.append(f"{test_case['id']}_step_{i}")
                documents.append(action)

        if not ids:
            return 0
        self.store.add(ids, documents, metadata=None)
        return len(ids)


    def find_similar(self, step_text: str, n_results: int = 3):
        """Find similar steps to the given step text using the ChromaRepository's search functionality."""
        return self.store.query(step_text, n_results)

    def get_reference_steps(self, feature_name: str, n_results: int = 10) -> list[str]:
        """Get existing steps related to a feature, filtering out generic/duplicate noise."""
        if self.store.count() == 0:
            return []

        # Query more than needed so we still have enough after filtering
        results = self.find_similar(feature_name, n_results * 2)
        # Filter: good similarity, not template, not generic
        steps = []
        for doc, dist in zip(results['documents'][0], results['distances'][0]):
            if dist < 1.2 and not _is_template_step(doc) and not _is_generic_step(doc):
                steps.append(doc)

        # Remove near-duplicates and limit
        steps = _deduplicate_steps(steps)
        return steps[:n_results]
    

