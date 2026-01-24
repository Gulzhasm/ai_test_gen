"""Generic Step Builder - Build test steps from observables, not hardcoded chains.

This module builds test steps dynamically based on extracted observables,
making the generator work for ANY story type without hardcoding.
"""

from typing import List, Dict, Optional
from core.services.observable_extractor import Observable
from core.domain.grounded_spec import GroundedSpec
from core.services.story_type_classifier import StoryType


class GenericStepBuilder:
    """Build test steps from observables, not from hardcoded chains."""

    def build_steps(self, observable: Observable, grounded_spec: GroundedSpec) -> List[Dict[str, str]]:
        """Build complete test steps from observable.

        Generic step pattern:
        1. Setup (PRE-REQ, Launch)
        2. Object setup (if required)
        3. Navigate to entry point
        4. Perform action
        5. Verify outcomes
        6. Teardown (Close)

        Args:
            observable: Extracted observable with action/target/outcomes
            grounded_spec: Evidence-backed specification

        Returns:
            List of step dictionaries with 'action' and 'expected' keys
        """
        steps = []

        # 1. Standard setup
        steps.append({"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""})
        steps.append({"action": "Launch the ENV QuickDraw application.", "expected": ""})

        # 2. Object setup if needed
        if observable.requires_object:
            steps.extend(self._build_object_setup(grounded_spec))

        # 3. Navigate to entry point
        entry_point = grounded_spec.get_primary_entry_point()
        if entry_point:
            steps.extend(self._build_navigation(entry_point, observable.target, observable.action))

        # 4. Perform action
        steps.extend(self._build_action_steps(observable))

        # 5. Verify outcomes
        steps.extend(self._build_verification_steps(observable.outcomes))

        # 6. Teardown
        steps.append({"action": "Close/Exit the QuickDraw application", "expected": ""})

        return steps

    def _build_object_setup(self, grounded_spec: GroundedSpec) -> List[Dict[str, str]]:
        """Build steps to create/select object if needed.

        Args:
            grounded_spec: Specification with context

        Returns:
            List of setup steps
        """
        steps = []

        # Create a generic shape
        steps.append({"action": "Create a new drawing with an object (e.g., ellipse, rectangle).", "expected": ""})
        steps.append({"action": "Select the object.", "expected": ""})

        return steps

    def _build_navigation(self, entry_point: str, target: str, action: str) -> List[Dict[str, str]]:
        """Build navigation steps to reach the feature.

        Generic navigation patterns:
        - If "Menu" → Open menu, Select option
        - If "Panel" → Open panel, Enable control
        - If "Toolbar" → Click button
        - If "Dialog" → Open dialog

        Args:
            entry_point: Entry point surface (e.g., "View Menu")
            target: Target feature (e.g., "fullscreen mode")
            action: Action type (for context)

        Returns:
            List of navigation steps
        """
        steps = []

        if "Menu" in entry_point:
            # Extract menu name (e.g., "View Menu" → "View")
            menu_name = entry_point.replace(" Menu", "")
            steps.append({"action": f"Open the {menu_name} menu.", "expected": ""})

            # Determine what to select based on action and target
            if action == 'accessible':
                # For availability tests, just verify presence
                return steps
            else:
                # For action tests, select the option
                # Use target for option name (e.g., "Full Screen Mode")
                option_name = self._format_target_as_menu_option(target)
                steps.append({"action": f"Select {option_name}.", "expected": ""})

        elif "Panel" in entry_point:
            # Panel navigation
            steps.append({"action": f"Open the {entry_point}.", "expected": ""})
            option_name = self._format_target_as_menu_option(target)
            steps.append({"action": f"Enable the {option_name}.", "expected": ""})

        elif "Toolbar" in entry_point:
            # Toolbar button click
            option_name = self._format_target_as_menu_option(target)
            steps.append({"action": f"Click the {option_name} button in the toolbar.", "expected": ""})

        elif "Dialog" in entry_point:
            # Dialog opening
            steps.append({"action": f"Open the {entry_point}.", "expected": ""})

        else:
            # Generic fallback
            option_name = self._format_target_as_menu_option(target)
            steps.append({"action": f"Navigate to {option_name} via {entry_point}.", "expected": ""})

        return steps

    def _format_target_as_menu_option(self, target: str) -> str:
        """Format target as a menu option name.

        Args:
            target: Target description (e.g., "fullscreen mode", "diameter measurement")

        Returns:
            Formatted menu option (e.g., "Full Screen Mode", "Diameter")
        """
        # Title case the target
        formatted = target.title()

        # Handle special cases
        formatted = formatted.replace("Fullscreen Mode", "Full Screen Mode")
        formatted = formatted.replace("Fullscreen", "Full Screen Mode")

        return formatted

    def _build_action_steps(self, observable: Observable) -> List[Dict[str, str]]:
        """Build action steps based on action verb.

        Args:
            observable: Observable with action/target info

        Returns:
            List of action steps
        """
        steps = []
        action = observable.action
        target = observable.target

        # Map action types to step templates
        if action == 'enter':
            steps.append({"action": f"Enter {target}.", "expected": ""})

        elif action == 'exit':
            steps.append({"action": f"Exit {target}.", "expected": ""})

        elif action == 'create':
            steps.append({"action": f"Create {target}.", "expected": ""})

        elif action == 'enable':
            steps.append({"action": f"Enable {target}.", "expected": ""})

        elif action == 'disable':
            steps.append({"action": f"Disable {target}.", "expected": ""})

        elif action == 'toggle':
            steps.append({"action": f"Toggle {target}.", "expected": ""})

        elif action == 'activate':
            # Tool activation - more specific than generic "activate tool"
            steps.append({"action": f"Activate the tool.", "expected": ""})

        elif action == 'select':
            steps.append({"action": f"Select {target}.", "expected": ""})

        elif action == 'move':
            steps.append({"action": f"Move {target}.", "expected": ""})

        elif action == 'rotate':
            # Rotation action - specify by dragging for tools
            if 'handle' in target.lower():
                steps.append({"action": f"Drag {target} to rotate the object.", "expected": ""})
            else:
                steps.append({"action": f"Rotate {target} using the rotation tool.", "expected": ""})

        elif action == 'drag':
            steps.append({"action": f"Drag {target}.", "expected": ""})

        elif action == 'resize':
            steps.append({"action": f"Resize {target}.", "expected": ""})

        elif action == 'measure':
            steps.append({"action": f"Measure {target}.", "expected": ""})

        elif action == 'display':
            # Display action - no explicit action needed, just verification
            # The display happens automatically, so skip action step
            pass

        elif action == 'verify':
            # Verification-only action (outcomes handled separately)
            pass

        elif action == 'accessible':
            # Availability check (handled in navigation)
            pass

        else:
            # Generic fallback
            steps.append({"action": f"Perform {action} on {target}.", "expected": ""})

        return steps

    def _build_verification_steps(self, outcomes: List[str]) -> List[Dict[str, str]]:
        """Build verification steps from outcomes.

        Args:
            outcomes: List of expected outcomes

        Returns:
            List of verification steps
        """
        steps = []

        for outcome in outcomes:
            # Format outcome for verification
            # "OS UI hidden" → "Verify OS UI is hidden."
            # "diameter line visible" → "Verify diameter line is visible."

            # Check if outcome already has "is/are"
            if ' is ' in outcome or ' are ' in outcome:
                # Already formatted
                action_text = f"Verify {outcome}."
                expected_text = f"{outcome.capitalize()}."
            else:
                # Add "is" or "are" based on outcome
                # Simple heuristic: if outcome ends with "s", use "are", else "is"
                if self._should_use_are(outcome):
                    action_text = f"Verify {outcome} are present."
                    expected_text = f"{outcome.capitalize()} are present."
                else:
                    action_text = f"Verify {outcome}."
                    expected_text = f"{outcome.capitalize()}."

            steps.append({
                "action": action_text,
                "expected": expected_text
            })

        return steps

    def _should_use_are(self, outcome: str) -> bool:
        """Determine if outcome should use 'are' vs 'is'.

        Args:
            outcome: Outcome text

        Returns:
            True if should use 'are'
        """
        # Simple heuristic: plural nouns typically end with 's'
        # Check for common plural patterns
        plural_indicators = [
            'panels', 'menus', 'toolbars', 'borders', 'issues',
            'objects', 'shapes', 'items', 'controls', 'buttons'
        ]

        outcome_lower = outcome.lower()
        for indicator in plural_indicators:
            if indicator in outcome_lower:
                return True

        return False

    def build_availability_steps(self, grounded_spec: GroundedSpec, feature_name: str) -> List[Dict[str, str]]:
        """Build steps for AC1 availability test.

        Args:
            grounded_spec: Evidence-backed specification
            feature_name: Name of feature to check

        Returns:
            List of availability test steps
        """
        steps = []

        # Standard setup
        steps.append({"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""})
        steps.append({"action": "Launch the ENV QuickDraw application.", "expected": ""})

        # Navigate to entry point
        entry_point = grounded_spec.get_primary_entry_point()
        if entry_point and "Menu" in entry_point:
            menu_name = entry_point.replace(" Menu", "")
            steps.append({"action": f"Navigate to {entry_point}.", "expected": ""})
            steps.append({
                "action": f"Verify the {feature_name} option is visible and accessible.",
                "expected": f"{feature_name} option is present and accessible."
            })
        else:
            steps.append({
                "action": f"Verify the {feature_name} is available in the application.",
                "expected": f"{feature_name} is available."
            })

        # Teardown
        steps.append({"action": "Close/Exit the QuickDraw application", "expected": ""})

        return steps
