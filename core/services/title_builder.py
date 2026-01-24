"""Title Builder - Build test titles from observables, not hardcoded.

This module builds test titles dynamically based on extracted observables,
ensuring titles accurately reflect the test scenario for ANY story type.
"""

from core.services.observable_extractor import Observable


class TitleBuilder:
    """Build test titles from observables, not hardcoded."""

    # Action templates for scenario descriptions
    ACTION_TEMPLATES = {
        'enter': 'Enter {target}',
        'exit': 'Exit {target}',
        'create': 'Create {target}',
        'enable': 'Enable {target}',
        'disable': 'Disable {target}',
        'toggle': 'Toggle {target}',
        'activate': 'Activate tool for {target}',
        'select': 'Select {target}',
        'move': 'Move {target}',
        'rotate': 'Rotate {target}',
        'drag': 'Drag {target}',
        'resize': 'Resize {target}',
        'measure': 'Measure {target}',
        'verify': 'Verify {target}',
        'display': 'Display {target}',
        'hide': 'Hide {target}',
        'accessible': 'Feature availability',
        'modify': 'Modify {target}'
    }

    def build(self, test_id: str, feature_name: str, entry_point: str,
              observable: Observable) -> str:
        """Build test title from observable.

        Generic title format:
        <ID>: <Feature> / <Entry Point> / <Action> <Target>

        Examples:
        - "272265-005: Full Screen Mode / View Menu / Enter fullscreen mode"
        - "272780-005: Diameter / Dimensions Menu / Enable diameter measurement"
        - "270471-005: Rotate Tool / Tools Menu / Rotate selected object"
        - "270123-005: New Dialog / File Menu / Create new document"

        Args:
            test_id: Test case ID (e.g., "272265-005")
            feature_name: Feature name from story
            entry_point: Entry point surface (e.g., "View Menu")
            observable: Extracted observable with action/target

        Returns:
            Complete test title
        """
        scenario = self._build_scenario(observable)
        return f"{test_id}: {feature_name} / {entry_point} / {scenario}"

    def _build_scenario(self, observable: Observable) -> str:
        """Build scenario description from observable.

        Args:
            observable: Extracted observable

        Returns:
            Scenario description (e.g., "Enter fullscreen mode", "Create diameter measurement")
        """
        action = observable.action
        target = observable.target

        # Get template for action
        template = self.ACTION_TEMPLATES.get(action, '{action} {target}')

        # Format template
        if '{target}' in template:
            scenario = template.format(target=target)
        elif '{action}' in template:
            scenario = template.format(action=action.capitalize(), target=target)
        else:
            # Template doesn't need formatting (e.g., "Feature availability")
            scenario = template

        return scenario

    def build_availability_title(self, test_id: str, feature_name: str, entry_point: str) -> str:
        """Build title for AC1 availability test.

        Args:
            test_id: Test case ID
            feature_name: Feature name
            entry_point: Entry point surface

        Returns:
            Availability test title
        """
        return f"{test_id}: {feature_name} / {entry_point} / Feature availability"

    def build_edge_case_title(self, test_id: str, feature_name: str, entry_point: str,
                              edge_case_description: str) -> str:
        """Build title for edge case test.

        Args:
            test_id: Test case ID
            feature_name: Feature name
            entry_point: Entry point surface
            edge_case_description: Description of edge case

        Returns:
            Edge case test title
        """
        return f"{test_id}: {feature_name} / {entry_point} / {edge_case_description}"

    def build_accessibility_title(self, test_id: str, feature_name: str,
                                  device: str, accessibility_type: str) -> str:
        """Build title for accessibility test.

        Args:
            test_id: Test case ID
            feature_name: Feature name
            device: Device platform (Windows 11, iPad, Android Tablet)
            accessibility_type: Type of accessibility test

        Returns:
            Accessibility test title
        """
        return f"{test_id}: {feature_name} / Accessibility / {accessibility_type} ({device})"
