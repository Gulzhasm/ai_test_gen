"""Observable Extractor - Extract testable observables from AC text.

This module extracts what-to-test from AC bullets WITHOUT hardcoding scenarios.
Instead of assuming "fullscreen mode" or "diameter measurement", it dynamically
extracts:
- Primary action (what user does)
- Target (what changes)
- Expected outcomes (what to verify)
- Constraints (limits, rules)
"""

from dataclasses import dataclass
from typing import List, Optional
from core.services.story_type_classifier import StoryType


@dataclass
class Observable:
    """A testable observable extracted from an AC bullet.

    Attributes:
        action: Generic action type (enter, exit, create, enable, disable, toggle, verify, etc.)
        target: What is being acted upon (e.g., "fullscreen mode", "diameter measurement", "selected object")
        outcomes: What should be verified (e.g., ["OS UI hidden", "App UI visible"])
        constraints: Optional limits or rules (e.g., ["for selected ellipse", "on all platforms"])
        requires_object: Whether this action requires an existing object
        raw_ac: Original AC text for reference
    """
    action: str
    target: str
    outcomes: List[str]
    constraints: List[str]
    requires_object: bool
    raw_ac: str


class ObservableExtractor:
    """Extract testable observables from AC bullets without hardcoding scenarios."""

    # Action verb mapping: maps various phrasings to canonical action types
    # NOTE: Order matters! More specific actions should come first to avoid false matches
    ACTION_VERBS = {
        'activate': ['activates', 'activated', 'activation'],  # Tool-specific (check before 'enable')
        'enable': ['enable', 'enables', 'enabled'],  # Separate from 'enter'
        'disable': ['disable', 'disables', 'disabled'],  # Separate from 'exit'
        'rotate': ['rotate', 'rotates', 'rotated', 'rotating', 'rotation'],  # Tool-specific
        'drag': ['drag', 'dragging', 'dragged', 'by dragging'],  # Tool-specific
        'enter': ['enter', 'entering', 'enters', 'turn on', 'start', 'open into'],
        'exit': ['exit', 'exiting', 'exits', 'close', 'leave', 'restore', 'restores'],
        'toggle': ['toggle', 'toggles', 'switch', 'alternate'],
        'create': ['create', 'creates', 'add', 'insert', 'draw', 'place'],
        'remove': ['remove', 'removes', 'delete', 'clear', 'erase'],
        'modify': ['change', 'update', 'edit', 'adjust', 'set'],
        'select': ['select', 'selects', 'choose', 'pick'],
        'verify': ['verify', 'verifies', 'check', 'confirm', 'ensure'],
        'display': ['display', 'displays', 'show', 'shows', 'render', 'present'],
        'hide': ['hide', 'hides', 'hidden', 'conceal', 'suppress'],
        'resize': ['resize', 'resizes', 'scale', 'fit', 'fill'],
        'move': ['move', 'moves', 'reposition', 'relocate'],  # Removed 'drag' from here
        'measure': ['measure', 'measures', 'calculate', 'compute'],
        'accessible': ['accessible', 'available', 'reachable']
    }

    # Signals that an action requires an existing object
    REQUIRES_OBJECT_SIGNALS = [
        'selected', 'existing', 'current', 'active',
        'for ellipse', 'for circle', 'for shape', 'for object',
        'to object', 'on object', 'with object'
    ]

    def extract(self, ac_bullet: str, story_type: StoryType) -> Observable:
        """Extract observable from AC bullet.

        Args:
            ac_bullet: Acceptance criteria bullet text
            story_type: Classified story type for context

        Returns:
            Observable containing action, target, outcomes, and constraints
        """
        ac_lower = ac_bullet.lower()

        # Extract action
        action = self._extract_action(ac_lower)

        # Extract target
        target = self._extract_target(ac_bullet, action, story_type)

        # Extract outcomes
        outcomes = self._extract_outcomes(ac_bullet, action, target)

        # Extract constraints
        constraints = self._extract_constraints(ac_bullet)

        # Determine if object is required
        requires_object = self._requires_object(ac_lower, story_type)

        return Observable(
            action=action,
            target=target,
            outcomes=outcomes,
            constraints=constraints,
            requires_object=requires_object,
            raw_ac=ac_bullet
        )

    def _extract_action(self, ac_lower: str) -> str:
        """Extract primary action from AC text.

        Returns canonical action type (enter, exit, create, etc.)
        """
        # Check each action type
        for canonical_action, verb_list in self.ACTION_VERBS.items():
            for verb in verb_list:
                if verb in ac_lower:
                    return canonical_action

        # Default to 'verify' if no specific action found
        return 'verify'

    def _extract_target(self, ac_text: str, action: str, story_type: StoryType) -> str:
        """Extract what is being acted upon.

        Args:
            ac_text: Original AC text (with capitalization)
            action: Extracted action type
            story_type: Story type for context

        Returns:
            Target description (e.g., "fullscreen mode", "diameter measurement")
        """
        import re
        ac_lower = ac_text.lower()

        # Pattern 0: "User can <verb> the <target>" - Handle this FIRST
        # "User can rotate the object" → "object"
        # "User can drag the rotation handle" → "rotation handle"
        user_can_match = re.search(r'user can (?:\w+\s+)?(?:the\s+)?([a-z][a-z\s]+?)(?:\s+by|\s+to|\s+and|\.|\,|$)', ac_lower)
        if user_can_match:
            target = user_can_match.group(1).strip()
            # Clean up common trailing words
            target = re.sub(r'\s+(by|to|and|for|with|using)$', '', target)
            if len(target) > 3 and len(target) < 50:  # Sanity check
                return target

        # Pattern 1: "<verb> the <target> by dragging" - Tool actions
        # "rotate the object by dragging" → "object"
        if action in ['rotate', 'drag', 'move']:
            verb_match = re.search(rf'{action}[sd]?\s+the\s+([a-z][a-z\s]+?)(?:\s+by|\s+to|\.|\,|$)', ac_lower)
            if verb_match:
                return verb_match.group(1).strip()

        # Pattern 2: Direct object after action verb
        # "entering fullscreen uses..." → "fullscreen"
        # "enable diameter measurement" → "diameter measurement"
        if action in ['enter', 'entering']:
            if 'fullscreen' in ac_lower or 'full screen' in ac_lower:
                return 'fullscreen mode'

        if action in ['exit', 'exiting']:
            if 'fullscreen' in ac_lower or 'full screen' in ac_lower:
                return 'fullscreen mode'

        # Pattern 3: Mode/Layout story types
        if story_type == StoryType.MODE_LAYOUT:
            # Extract mode name from phrases like "System Full Screen Mode"
            if 'full screen mode' in ac_lower or 'fullscreen mode' in ac_lower:
                return 'fullscreen mode'
            elif 'mode' in ac_lower:
                # Extract capitalized words before "mode"
                match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+[Mm]ode', ac_text)
                if match:
                    return f"{match.group(1).lower()} mode"

        # Pattern 4: Measurement story types
        if story_type == StoryType.MEASUREMENT:
            if 'diameter' in ac_lower:
                return 'diameter measurement'
            elif 'radius' in ac_lower:
                return 'radius measurement'
            elif 'dimension' in ac_lower:
                return 'dimension measurement'

        # Pattern 5: Tool story types - default to "object" or specific tool target
        if story_type == StoryType.TOOL:
            # Check for specific tool targets
            if 'rotation handle' in ac_lower or 'handle' in ac_lower:
                return 'rotation handle'
            elif 'rotation angle' in ac_lower or 'angle' in ac_lower:
                return 'rotation angle'
            elif 'object' in ac_lower or 'shape' in ac_lower:
                return 'selected object'
            else:
                # Default for tool stories
                return 'selected object'

        # Pattern 6: Look for noun phrases after "the"
        # "the application enters fullscreen" → "application"
        # "the canvas fills" → "canvas"
        match = re.search(r'\bthe\s+([a-z]+(?:\s+[a-z]+){0,2})', ac_lower)
        if match:
            target = match.group(1).strip()
            if len(target) > 3:  # Avoid "the is", "the to", etc.
                return target

        # Fallback: return story type as target
        return story_type.name.lower().replace('_', ' ')

    def _extract_outcomes(self, ac_text: str, action: str, target: str) -> List[str]:
        """Extract expected outcomes to verify.

        Args:
            ac_text: Original AC text
            action: Extracted action
            target: Extracted target

        Returns:
            List of verifiable outcomes
        """
        import re
        outcomes = []
        ac_lower = ac_text.lower()

        # Pattern 1: Explicit verification phrases
        # "OS UI is hidden" → "OS UI hidden"
        # "App UI remains visible" → "App UI visible"
        # Look for "X is Y" patterns
        is_patterns = re.findall(r'([A-Z][A-Za-z\s\-]+?)\s+(?:is|are|remains?)\s+([a-z]+)', ac_text)
        for subject, state in is_patterns:
            subject = subject.strip()
            state = state.strip()
            outcomes.append(f"{subject} {state}")

        # Pattern 2: "shows <X>" or "displays <X>"
        # "shows the current rotation angle" → "rotation angle is displayed"
        show_match = re.search(r'(?:shows|displays|presents)\s+(?:the\s+)?([a-zA-Z\s]+?)(?:\.|\,|$)', ac_text, re.IGNORECASE)
        if show_match:
            shown_item = show_match.group(1).strip()
            if len(shown_item) < 50:  # Sanity check
                outcomes.append(f"{shown_item} is displayed")

        # Pattern 3: "provides <X>" - Tool feedback
        # "provides visual feedback" → "visual feedback is provided"
        provides_match = re.search(r'provides?\s+([a-zA-Z\s]+?)(?:\s+showing|\s+for|\.|\,|$)', ac_lower)
        if provides_match:
            provided_item = provides_match.group(1).strip()
            if len(provided_item) < 50:
                outcomes.append(f"{provided_item} is provided")

        # Pattern 4: Comma-separated outcomes
        # "hides taskbar, window borders, title bar"
        if 'hidden' in ac_lower or 'hide' in ac_lower:
            # Extract what is hidden
            hidden_match = re.search(r'hid(?:es?|den)\s+([^\.]+)', ac_lower)
            if hidden_match:
                hidden_items = hidden_match.group(1)
                # Split by commas and "and"
                items = re.split(r',|\sand\s', hidden_items)
                for item in items:
                    item = item.strip()
                    if item and len(item) < 50:  # Sanity check
                        outcomes.append(f"{item} hidden")

        # Pattern 5: "X should Y" patterns
        should_patterns = re.findall(r'([A-Za-z\s]+?)\s+should\s+([a-z]+[^,\.]+)', ac_lower)
        for subject, action_desc in should_patterns:
            subject = subject.strip()
            action_desc = action_desc.strip()
            outcomes.append(f"{subject} {action_desc}")

        # Pattern 6: Measurement-specific outcomes
        # Look for "line visible", "label visible", "line and label"
        if 'measurement' in target.lower() or 'diameter' in target.lower() or 'radius' in target.lower():
            if 'line' in ac_lower and 'label' in ac_lower:
                outcomes.append(f"{target} line is visible")
                outcomes.append(f"{target} label is visible")
            elif 'line' in ac_lower:
                outcomes.append(f"{target} line is visible")
            elif 'label' in ac_lower:
                outcomes.append(f"{target} label is visible")

        # Pattern 7: Tool activation outcomes
        # "tool activates" → "tool is activated"
        if action == 'activate' and not outcomes:
            outcomes.append(f"tool is activated")
            # Check for "when" conditions
            when_match = re.search(r'when\s+([a-z][a-z\s]+?)(?:is|are)\s+([a-z]+)', ac_lower)
            if when_match:
                condition_subject = when_match.group(1).strip()
                condition_state = when_match.group(2).strip()
                outcomes.append(f"{condition_subject} is {condition_state}")

        # Pattern 8: Default outcomes based on action
        if not outcomes:
            if action == 'enter':
                outcomes.append(f"{target} is active")
            elif action == 'exit':
                outcomes.append(f"{target} is exited")
                outcomes.append("previous state is restored")
            elif action == 'create':
                outcomes.append(f"{target} is created")
            elif action == 'enable':
                outcomes.append(f"{target} is enabled")
            elif action == 'disable':
                outcomes.append(f"{target} is disabled")
            elif action == 'rotate':
                outcomes.append(f"{target} is rotated")
            elif action == 'drag':
                outcomes.append(f"{target} is moved")
            elif action == 'resize':
                outcomes.append(f"{target} resizes correctly")
            elif action == 'accessible':
                outcomes.append(f"{target} is accessible")
            elif action == 'display':
                outcomes.append(f"{target} is displayed")

        return outcomes if outcomes else [f"{action} completes successfully"]

    def _extract_constraints(self, ac_text: str) -> List[str]:
        """Extract constraints or rules from AC.

        Args:
            ac_text: Original AC text

        Returns:
            List of constraints (e.g., ["on all platforms", "for phase 1"])
        """
        constraints = []
        ac_lower = ac_text.lower()

        # Pattern 1: Platform constraints
        if 'windows' in ac_lower:
            constraints.append('on Windows')
        if 'ipad' in ac_lower:
            constraints.append('on iPad')
        if 'android' in ac_lower:
            constraints.append('on Android')

        # Pattern 2: Object type constraints
        if 'ellipse' in ac_lower:
            constraints.append('for ellipse')
        if 'circle' in ac_lower:
            constraints.append('for circle')
        if 'selected' in ac_lower:
            constraints.append('for selected object')

        # Pattern 3: Phase constraints
        import re
        phase_match = re.search(r'phase\s+(\d+)', ac_lower)
        if phase_match:
            constraints.append(f"for phase {phase_match.group(1)}")

        return constraints

    def _requires_object(self, ac_lower: str, story_type: StoryType) -> bool:
        """Determine if action requires an existing object.

        Args:
            ac_lower: Lowercase AC text
            story_type: Story type

        Returns:
            True if object is required before action
        """
        # Check for explicit signals
        for signal in self.REQUIRES_OBJECT_SIGNALS:
            if signal in ac_lower:
                return True

        # Story type heuristics
        if story_type in [StoryType.MEASUREMENT, StoryType.TOOL]:
            return True

        return False
