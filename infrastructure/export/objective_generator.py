"""
Objective Generator Module

Generates formatted objectives for test cases with configurable key term patterns.
Supports dependency injection for project-specific bolding patterns.
"""
import re
from typing import Dict, List, Optional, Protocol


class IObjectiveConfig(Protocol):
    """Protocol for objective configuration."""
    @property
    def key_term_patterns(self) -> List[str]: ...


class ObjectiveGenerator:
    """
    Generates objectives mapped 1:1 to test cases.

    Supports configurable key term patterns for bolding important terms.
    """

    # Default key term patterns for bolding (generic patterns)
    DEFAULT_KEY_TERM_PATTERNS = [
        # UI elements
        r'\b(menu|toolbar|panel|dialog|window|button|tab|field|dropdown)\b',
        # Actions
        r'\b(click|select|navigate|open|close|save|delete|create|edit|update)\b',
        # Platforms
        r'\b(Windows|Mac|iPad|Android|iOS|tablet|mobile|desktop)\b',
        # Accessibility
        r'\b(VoiceOver|TalkBack|NVDA|JAWS|Narrator|screen reader)\b',
        # States
        r'\b(enabled|disabled|visible|hidden|active|inactive)\b',
    ]

    def __init__(self, key_term_patterns: Optional[List[str]] = None):
        """
        Initialize objective generator with optional key term patterns.

        Args:
            key_term_patterns: List of regex patterns for terms to bold
        """
        self._patterns = key_term_patterns or self.DEFAULT_KEY_TERM_PATTERNS

    @property
    def key_term_patterns(self) -> List[str]:
        """Get key term patterns for bolding."""
        return self._patterns

    def format_objective_for_ado(self, objective_text: str) -> str:
        """
        Format objective for ADO Summary field (System.Description).

        RULES:
        1. Format: <b>Objective:</b> Verify that [rest of text]
        2. "Objective:" is always bold at the start
        3. Remove "Verify that" duplication if already present
        4. Important test-related terms are bolded using patterns
        5. Multiple bold tags are allowed
        6. Nested bold tags are automatically cleaned up

        Args:
            objective_text: Raw objective text

        Returns:
            Formatted HTML string for ADO
        """
        # Remove "Verify that" if already at start (avoid duplication)
        objective_text = objective_text.strip()
        if objective_text.lower().startswith('verify that '):
            objective_text = objective_text[12:]

        # Format: <b>Objective:</b> Verify that [rest of text]
        formatted = f"<b>Objective:</b> Verify that {objective_text}"

        # Apply bold formatting to important terms
        formatted = self._apply_bold_patterns(formatted)

        return formatted

    def _apply_bold_patterns(self, text: str) -> str:
        """
        Apply bold tags to terms matching patterns.

        Args:
            text: Input text

        Returns:
            Text with bold tags applied to matching terms
        """
        for term_pattern in self._patterns:
            pattern = re.compile(term_pattern, re.IGNORECASE)
            matches = list(pattern.finditer(text))

            if matches:
                # Process matches in reverse to maintain positions
                for match in reversed(matches):
                    start, end = match.span()
                    prefix = text[:start]
                    open_tags = prefix.count('<b>') - prefix.count('</b>')

                    if open_tags == 0:
                        # Not within bold tags, add bold
                        matched_text = match.group(0)
                        text = text[:start] + f'<b>{matched_text}</b>' + text[end:]

        return text

    def generate_objectives_file(
        self,
        test_cases: List[Dict],
        output_file: str
    ) -> None:
        """
        Generate 1:1 mapped objectives file.

        MANDATORY FORMAT:
        1. First line: <TEST_CASE_ID>: <Full Test Case Title WITHOUT ID prefix>
        2. Second line: Objective: Verify that [objective text]
        3. Blank line between test cases

        Args:
            test_cases: List of test case dictionaries
            output_file: Output file path
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            for tc in test_cases:
                self._write_objective_entry(f, tc)

    def generate_objectives_string(self, test_cases: List[Dict]) -> str:
        """
        Generate objectives as a string.

        Args:
            test_cases: List of test case dictionaries

        Returns:
            Objectives content as string
        """
        lines = []
        for tc in test_cases:
            lines.extend(self._format_objective_entry(tc))
        return '\n'.join(lines)

    def _write_objective_entry(self, f, tc: Dict) -> None:
        """Write a single objective entry to file."""
        lines = self._format_objective_entry(tc)
        for line in lines:
            f.write(line + '\n')

    def _format_objective_entry(self, tc: Dict) -> List[str]:
        """
        Format a single objective entry.

        Args:
            tc: Test case dictionary

        Returns:
            List of lines for this entry
        """
        test_id = tc.get('id', '')
        full_title = tc.get('title', '')

        # Remove ID prefix from title if present
        title_without_id = full_title
        if ': ' in full_title:
            title_without_id = full_title.split(': ', 1)[1]

        # Get objective
        objective = tc.get('objective', '').strip()
        if not objective:
            # Generate default objective from title
            feature = title_without_id.split('/')[0].strip() if '/' in title_without_id else title_without_id
            objective = f"the {feature} works as expected"

        if not objective.lower().startswith('verify that'):
            objective = f"Verify that {objective}"

        # Format objective with bold tags
        formatted_objective = self.format_objective_for_ado(objective)

        return [
            f"{test_id}: {title_without_id}",
            formatted_objective,
            ""  # Blank line separator
        ]

    def create_objective_from_title(self, title: str) -> str:
        """
        Create an objective from a test case title.

        Args:
            title: Test case title in format "Feature / Area / Scenario"

        Returns:
            Formatted objective text
        """
        parts = title.split('/')
        if len(parts) >= 3:
            feature = parts[0].strip()
            area = parts[1].strip()
            scenario = parts[2].strip()
            return f"the {scenario.lower()} in {area} for {feature} works correctly"
        elif len(parts) >= 2:
            feature = parts[0].strip()
            scenario = parts[1].strip()
            return f"the {scenario.lower()} for {feature} works correctly"
        else:
            return f"the {title.lower()} works correctly"
