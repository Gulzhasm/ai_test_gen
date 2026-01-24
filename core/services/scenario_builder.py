"""
ScenarioBuilder: Builds balanced, specific scenario names from AC bullets.

This replaces generic titles like "Verify selected object" with specific scenarios
like "Rotate Tool Applies 90 Degree Clockwise Rotation".
"""
from typing import Dict, Optional, List
import re


class ScenarioBuilder:
    """
    Builds balanced scenario names that answer:
    1. FROM WHERE (Canvas / Tools Menu / Properties Panel)
    2. WHAT (Rotate / Mirror / Toggle)
    3. SCOPE/OUTCOME (In-Place / Proportions Unchanged / Only Selected)
    """

    def __init__(self):
        # Action verb mapping
        self.action_patterns = {
            # Transformation actions
            r'rotat(?:e|es|ing)': 'Rotate',
            r'mirror(?:s|ing)?\s+horizontally': 'Mirror Horizontally',
            r'mirror(?:s|ing)?\s+vertically': 'Mirror Vertically',
            r'flip(?:s|ping)?\s+horizontally': 'Mirror Horizontally',
            r'flip(?:s|ping)?\s+vertically': 'Mirror Vertically',

            # State actions
            r'enable(?:d|s)?': 'Enable',
            r'disable(?:d|s)?': 'Disable',
            r'activate(?:d|s)?': 'Activate',
            r'deactivate(?:d|s)?': 'Deactivate',
            r'toggle(?:d|s)?': 'Toggle',
            r'show(?:n|s)?': 'Show',
            r'hide(?:n|s)?': 'Hide',

            # CRUD actions
            r'create(?:d|s)?': 'Create',
            r'add(?:ed|s)?': 'Add',
            r'remove(?:d|s)?': 'Remove',
            r'delete(?:d|s)?': 'Delete',
            r'modify|modifies': 'Modify',
            r'update(?:d|s)?': 'Update',

            # Undo/Redo
            r'undo': 'Undo',
            r'redo': 'Redo',

            # Persistence
            r'persist(?:s|ed|ent)?': 'Persist',
            r'remain(?:s|ing)?': 'Remain',
            r'stay(?:s)?': 'Stay',

            # Application
            r'appl(?:y|ies|ied)': 'Apply',
            r'affect(?:s|ed)?': 'Affect',
        }

        # Outcome/validation patterns
        self.outcome_patterns = {
            r'immediat(?:e|ely)': 'Immediately',
            r'in-place|in place': 'In Place',
            r'proportions?\s+(?:unchanged|preserved|maintained)': 'Proportions Unchanged',
            r'only\s+selected': 'Only Selected',
            r'multi(?:-)?select(?:ed|ion)?': 'Multi Selection',
            r'preserv(?:e|es|ing)\s+relative\s+(?:position|layout)': 'Preserving Relative Layout',
            r'disabled?\s+(?:when|if)\s+no\s+(?:selection|object)': 'Disabled When No Selection',
            r'available\s+in\s+(?:the\s+)?(.+?)(?:\.|$)': 'Available In \\1',
            r'synchronized?': 'Synchronized',
            r'consistent(?:ly)?': 'Consistent',
        }

        # Negative scenario patterns
        self.negative_patterns = {
            r'no\s+(?:selection|object(?:s)?)\s+selected': 'No Selection',
            r'does?\s+not\s+(?:modify|change|affect)': 'Does Not Affect',
            r'(?:hidden|not\s+visible)\s+(?:when|for)': 'Hidden For',
            r'not\s+available': 'Not Available',
            r'disabled': 'Disabled State',
        }

    def build_scenario(self, ac_bullet: str, ac_index: int, story_type: str = None) -> str:
        """
        Build a specific, balanced scenario name from AC bullet.

        Args:
            ac_bullet: Acceptance criteria text
            ac_index: 1-based AC index
            story_type: Optional story type hint

        Returns:
            Specific scenario name (e.g., "Rotate Tool Applies 90 Degree Rotation")
        """
        ac_lower = ac_bullet.lower().strip()

        # AC1 is always "Feature Availability" or "Commands Available"
        if ac_index == 1:
            return self._build_ac1_scenario(ac_bullet)

        # Check for negative scenarios first
        for pattern, scenario in self.negative_patterns.items():
            if re.search(pattern, ac_lower):
                return self._build_negative_scenario(ac_bullet, scenario)

        # Extract action
        action = self._extract_action(ac_bullet)

        # Extract outcome/validation
        outcome = self._extract_outcome(ac_bullet)

        # Extract target (what's being acted upon)
        target = self._extract_target(ac_bullet)

        # Build scenario from components
        return self._compose_scenario(action, target, outcome, ac_bullet)

    def _build_ac1_scenario(self, ac_bullet: str) -> str:
        """Build AC1 scenario (always availability-focused)."""
        ac_lower = ac_bullet.lower()

        # Check if it mentions multiple commands/options
        if 'following commands' in ac_lower or 'following' in ac_lower:
            return "Commands Available In Menu"

        if 'available' in ac_lower:
            return "Feature Availability"

        if 'visible' in ac_lower or 'appear' in ac_lower:
            return "Feature Visibility"

        return "Feature Availability"

    def _build_negative_scenario(self, ac_bullet: str, base_scenario: str) -> str:
        """Build scenario for negative test cases."""
        ac_lower = ac_bullet.lower()

        # Extract what it doesn't affect
        if 'does not modify' in ac_lower or 'do not modify' in ac_lower:
            # Extract what's not modified
            not_modify_pattern = r'do(?:es)?\s+not\s+modify\s+(?:object\s+)?(.+?)(?:\.|,|$)'
            match = re.search(not_modify_pattern, ac_lower)
            if match:
                attributes = match.group(1).strip()
                # Clean up attribute list
                attributes = re.sub(r'\s+or\s+', ', ', attributes)
                return f"Does Not Modify {attributes.title()}"

        # Hidden for non-X objects
        if 'hidden' in ac_lower or 'not visible' in ac_lower:
            # Extract for what
            for_pattern = r'(?:hidden|not\s+visible)\s+(?:for|when)\s+(.+?)(?:\.|$)'
            match = re.search(for_pattern, ac_lower)
            if match:
                condition = match.group(1).strip()
                return f"Hidden For {condition.title()}"
            return "Hidden State"

        # Disabled when no selection
        if 'disabled' in ac_lower and 'no' in ac_lower:
            return "Disabled When No Selection"

        return base_scenario

    def _extract_action(self, ac_bullet: str) -> Optional[str]:
        """Extract primary action from AC bullet."""
        ac_lower = ac_bullet.lower()

        for pattern, action in self.action_patterns.items():
            if re.search(pattern, ac_lower):
                return action

        return None

    def _extract_outcome(self, ac_bullet: str) -> Optional[str]:
        """Extract expected outcome/validation from AC bullet."""
        ac_lower = ac_bullet.lower()

        for pattern, outcome in self.outcome_patterns.items():
            match = re.search(pattern, ac_lower)
            if match:
                # Handle backreferences (e.g., \1 for captured groups)
                if '\\1' in outcome and match.lastindex:
                    return outcome.replace('\\1', match.group(1).title())
                return outcome

        return None

    def _extract_target(self, ac_bullet: str) -> Optional[str]:
        """Extract target object/control from AC bullet."""
        ac_lower = ac_bullet.lower()

        # Common targets
        targets = {
            'selected object': 'Selected Object',
            'multi-selected object': 'Multi-Selected Objects',
            'canvas': 'Canvas',
            'dialog': 'Dialog',
            'panel': 'Panel',
            'menu': 'Menu',
            'toolbar': 'Toolbar',
            'control': 'Control',
            'button': 'Button',
            'toggle': 'Toggle',
            'field': 'Field',
        }

        for target_keyword, target_name in targets.items():
            if target_keyword in ac_lower:
                return target_name

        return None

    def _compose_scenario(self, action: Optional[str], target: Optional[str],
                         outcome: Optional[str], ac_bullet: str) -> str:
        """Compose scenario from extracted components."""

        # If we have all components
        if action and outcome:
            if target:
                return f"{action} {target} {outcome}"
            else:
                return f"{action} {outcome}"

        # If we have action and target
        if action and target:
            return f"{action} {target}"

        # If we have just action
        if action:
            return f"{action} Behavior"

        # Fallback: try to extract a meaningful phrase
        return self._fallback_scenario(ac_bullet)

    def _fallback_scenario(self, ac_bullet: str) -> str:
        """Fallback scenario extraction for complex bullets."""
        ac_lower = ac_bullet.lower().strip()

        # Undo/Redo pattern
        if 'undo' in ac_lower and 'redo' in ac_lower:
            return "Undo Redo Support"

        # Synchronization pattern
        if 'synchron' in ac_lower or 'match' in ac_lower:
            return "State Synchronization"

        # Persistence pattern
        if 'persist' in ac_lower or 'remain' in ac_lower:
            return "State Persistence"

        # Multi-selection pattern
        if 'multi' in ac_lower and 'select' in ac_lower:
            return "Multi Selection Behavior"

        # Immediate update pattern
        if 'immediate' in ac_lower or 'instantly' in ac_lower:
            return "Immediate Update"

        # Default: use first few meaningful words
        words = ac_bullet.split()[:5]
        meaningful_words = [w for w in words if len(w) > 3 and w[0].isupper()]
        if meaningful_words:
            return ' '.join(meaningful_words[:3])

        return "Functional Behavior"


def build_balanced_title(story_id: int, feature_name: str, area: str,
                        scenario: str, device: Optional[str] = None) -> str:
    """
    Build a balanced test case title following strict format.

    Format: <StoryID>-XXX: <FeatureName> / <ConcreteArea> / <SpecificScenario> (Device)

    Args:
        story_id: Story ID
        feature_name: Feature name from story title
        area: Concrete UI surface (Tools Menu, Properties Panel, Canvas, etc.)
        scenario: Specific scenario name
        device: Optional device name (Windows 11, iPad, Android Tablet)

    Returns:
        Balanced title string
    """
    # Build base title
    title = f"{feature_name} / {area} / {scenario}"

    # Add device if provided
    if device:
        title += f" ({device})"

    return title
