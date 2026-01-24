"""
Objective Generator Module
Generates 1:1 mapped objectives for test cases.
"""
import re
from typing import Dict, List

import config


class ObjectiveGenerator:
    """Generates objectives 1:1 mapped to test cases."""
    
    def format_objective_for_ado(self, objective_text: str) -> str:
        """Format objective for ADO Summary field (System.Description).

        RULES:
        1. Format: <b>Objective:</b> Verify that [rest of text]
        2. "Objective:" is always bold at the start
        3. Remove "Verify that" duplication if already present
        4. Important test-related terms are bolded using generic patterns (UI elements, actions, platforms, etc.)
        5. Multiple bold tags are allowed (key terms within the objective text)
        6. Nested bold tags are automatically cleaned up
        """
        # Remove "Verify that" if it's already at the start (to avoid duplication)
        objective_text = objective_text.strip()
        if objective_text.lower().startswith('verify that '):
            objective_text = objective_text[12:]  # Remove "Verify that "
        
        # Format: <b>Objective:</b> Verify that [rest of text]
        formatted = f"<b>Objective:</b> Verify that {objective_text}"
        
        # Apply bold formatting to important test-related terms using generic patterns
        # Process patterns in order, but avoid bolding text that's already bolded
        for term_pattern in config.OBJECTIVE_KEY_TERM_PATTERNS:
            pattern = re.compile(term_pattern, re.IGNORECASE)

            # Find all matches and replace them, but skip if already within bold tags
            def replace_if_not_bold(match):
                start_pos = match.start()
                # Check if this match is already within a bold tag
                # by looking backwards for opening tag
                prefix = formatted[:start_pos]
                # Count unclosed bold tags before this position
                open_tags = prefix.count('<b>') - prefix.count('</b>')

                if open_tags > 0:
                    # Already within a bold tag, don't add another
                    return match.group(0)
                else:
                    # Not within bold tag, add bold
                    return f'<b>{match.group(0)}</b>'

            # We need to use a different approach - mark positions first, then replace
            matches = list(pattern.finditer(formatted))
            if matches:
                # Build new string by processing matches in reverse to maintain positions
                for match in reversed(matches):
                    start, end = match.span()
                    prefix = formatted[:start]
                    open_tags = prefix.count('<b>') - prefix.count('</b>')

                    if open_tags == 0:
                        # Not within bold tags, add bold
                        matched_text = match.group(0)
                        formatted = formatted[:start] + f'<b>{matched_text}</b>' + formatted[end:]

        return formatted
    
    def generate_objectives_file(self, test_cases: List[Dict], output_file: str):
        """Generate 1:1 mapped objectives file.

        MANDATORY FORMAT:
        1. First line: <TEST_CASE_ID>: <Full Test Case Title WITHOUT ID prefix>
        2. Second line: Objective: Verify that [objective text]
        3. Blank line between test cases

        Example:
            272889-AC1: Object Transformation Tools / Tools Menu / Commands Available
            Objective: Verify that <b>Rotate</b>, <b>Mirror Horizontally</b>, and <b>Mirror Vertically</b> commands are available in the <b>Tools Menu</b>

        NO DUPLICATE IDs in title line.
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            for tc in test_cases:
                # Extract test ID and title
                test_id = tc['id']
                full_title = tc['title']

                # Remove ID prefix from title if present (to avoid duplication)
                # Title format: "272889-AC1: Feature / Area / Scenario"
                # We want: "Feature / Area / Scenario"
                title_without_id = full_title
                if ': ' in full_title:
                    title_without_id = full_title.split(': ', 1)[1]

                # Write first line: ID: Title (no ID duplication)
                f.write(f"{test_id}: {title_without_id}\n")

                # Get objective and ensure it starts with "Verify that"
                objective = tc.get('objective', '').strip()
                if not objective:
                    # Generate default objective from title
                    objective = f"the {title_without_id.split('/')[0].strip()} works as expected"

                if not objective.lower().startswith('verify that'):
                    objective = f"Verify that {objective}"

                # Format objective: "Objective:" prefix + bold key terms
                formatted_objective = self.format_objective_for_ado(objective)
                f.write(f"{formatted_objective}\n\n")
