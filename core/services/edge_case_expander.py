"""
EdgeCaseExpander: Systematic edge case generation based on story type.

This module generates edge case tests based on story type and signals,
ensuring comprehensive coverage without LLM guesswork.
"""
from typing import List, Dict, Optional
from core.domain.grounded_spec import GroundedSpec
from core.services.story_type_classifier import StoryType, StoryTypeClassifier
from core.services.action_chain_builder import ActionChainBuilder


class EdgeCaseExpander:
    """
    Expands coverage with story-type-specific edge cases.

    Uses story type + signals to add 1-3 extra tests per AC within scope.
    """

    def __init__(self, grounded_spec: GroundedSpec, story_type: StoryType):
        self.grounded_spec = grounded_spec
        self.story_type = story_type

    def generate_edge_case_tests(self, story_id: int, feature_name: str) -> List[Dict]:
        """
        Generate edge case tests based on story type and grounded spec.

        Returns:
            List of edge case test dicts
        """
        edge_case_tests = []
        test_id_counter = 100  # Start edge cases at 100

        # Get edge cases based on story type
        if self.story_type == StoryType.MODE_LAYOUT:
            edge_case_tests.extend(self._generate_mode_layout_edge_cases(story_id, feature_name, test_id_counter))

        elif self.story_type == StoryType.DIALOG:
            edge_case_tests.extend(self._generate_dialog_edge_cases(story_id, feature_name, test_id_counter))

        elif self.story_type == StoryType.TOOL:
            edge_case_tests.extend(self._generate_tool_edge_cases(story_id, feature_name, test_id_counter))

        elif self.story_type == StoryType.MEASUREMENT:
            edge_case_tests.extend(self._generate_measurement_edge_cases(story_id, feature_name, test_id_counter))

        elif self.story_type == StoryType.FILE_OPS:
            edge_case_tests.extend(self._generate_file_ops_edge_cases(story_id, feature_name, test_id_counter))

        return edge_case_tests

    def _generate_mode_layout_edge_cases(self, story_id: int, feature_name: str, test_id_counter: int) -> List[Dict]:
        """Generate edge cases for Mode/Layout stories."""
        edge_cases = []

        # Edge case: Repeated toggle enter/exit
        entry_point = self.grounded_spec.get_primary_entry_point() or "View Menu"

        test_id = f"{story_id}-{test_id_counter:03d}"
        title = f"{test_id}: {feature_name} / {entry_point} / Repeated toggle enter and exit mode"
        steps = [
            {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
            {"action": "Launch the ENV QuickDraw application.", "expected": ""},
            {"action": f"Enter {feature_name} mode via {entry_point}.", "expected": ""},
            {"action": f"Verify {feature_name} mode is active.", "expected": f"{feature_name} mode is active."},
            {"action": f"Exit {feature_name} mode.", "expected": ""},
            {"action": f"Verify {feature_name} mode is exited and previous state is restored.", "expected": "Previous state is restored."},
            {"action": f"Enter {feature_name} mode via {entry_point}.", "expected": ""},
            {"action": f"Verify {feature_name} mode is active again.", "expected": f"{feature_name} mode is active."},
            {"action": "Close/Exit the QuickDraw application", "expected": ""}
        ]
        objective = f"Verify that <b>{feature_name} mode</b> can be <b>toggled repeatedly</b> without errors or state corruption"
        edge_cases.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        # Edge case: Preserve active project
        test_id_counter += 5
        test_id = f"{story_id}-{test_id_counter:03d}"
        title = f"{test_id}: {feature_name} / {entry_point} / Active project preserved when entering mode"
        steps = [
            {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
            {"action": "Launch the ENV QuickDraw application.", "expected": ""},
            {"action": "Create a new drawing with multiple objects.", "expected": ""},
            {"action": f"Enter {feature_name} mode via {entry_point}.", "expected": ""},
            {"action": "Verify the active project and all objects remain accessible.", "expected": "Active project is preserved."},
            {"action": "Close/Exit the QuickDraw application", "expected": ""}
        ]
        objective = f"Verify that <b>active project</b> is <b>preserved</b> when entering <b>{feature_name} mode</b>"
        edge_cases.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        return edge_cases

    def _generate_dialog_edge_cases(self, story_id: int, feature_name: str, test_id_counter: int) -> List[Dict]:
        """Generate edge cases for Dialog stories."""
        edge_cases = []
        entry_point = self.grounded_spec.get_primary_entry_point() or "File Menu"

        # Edge case: Close without action
        test_id = f"{story_id}-{test_id_counter:03d}"
        title = f"{test_id}: {feature_name} / {entry_point} / Close dialog without creating"
        steps = [
            {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
            {"action": "Launch the ENV QuickDraw application.", "expected": ""},
            {"action": f"Open {feature_name} dialog via {entry_point}.", "expected": ""},
            {"action": "Close the dialog without performing any action.", "expected": ""},
            {"action": "Verify no changes are made to the active project.", "expected": "No changes are made to the project."},
            {"action": "Close/Exit the QuickDraw application", "expected": ""}
        ]
        objective = f"Verify that closing <b>{feature_name} dialog</b> without action makes <b>no changes</b> to the project"
        edge_cases.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        # Edge case: Tab order / focus trap
        test_id_counter += 5
        test_id = f"{story_id}-{test_id_counter:03d}"
        title = f"{test_id}: {feature_name} / {entry_point} / Tab order and focus trap in dialog"
        steps = [
            {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
            {"action": "Launch the ENV QuickDraw application.", "expected": ""},
            {"action": f"Open {feature_name} dialog via {entry_point}.", "expected": ""},
            {"action": "Navigate through all controls using Tab key.", "expected": ""},
            {"action": "Verify tab order is logical and focus remains trapped within the dialog.", "expected": "Tab order is logical and focus is trapped."},
            {"action": "Close/Exit the QuickDraw application", "expected": ""}
        ]
        objective = f"Verify that <b>{feature_name} dialog</b> has <b>logical tab order</b> and <b>focus trap</b>"
        edge_cases.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        return edge_cases

    def _generate_tool_edge_cases(self, story_id: int, feature_name: str, test_id_counter: int) -> List[Dict]:
        """Generate edge cases for Tool stories."""
        edge_cases = []
        entry_point = self.grounded_spec.get_primary_entry_point() or "Tools Menu"

        # Edge case: No selection behavior
        if 'no_selection' not in self.grounded_spec.negative_scenarios:
            test_id = f"{story_id}-{test_id_counter:03d}"
            title = f"{test_id}: {feature_name} / {entry_point} / Tool behavior with no selection"
            steps = [
                {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
                {"action": "Launch the ENV QuickDraw application.", "expected": ""},
                {"action": "Create a new drawing.", "expected": ""},
                {"action": f"Activate {feature_name} tool via {entry_point}.", "expected": ""},
                {"action": f"Attempt to use {feature_name} tool without selecting any object.", "expected": ""},
                {"action": "Verify the tool provides appropriate feedback and does not cause errors.", "expected": "Tool provides feedback for no selection."},
                {"action": "Close/Exit the QuickDraw application", "expected": ""}
            ]
            objective = f"Verify that <b>{feature_name} tool</b> provides <b>appropriate feedback</b> when <b>no object is selected</b>"
            edge_cases.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})
            test_id_counter += 5

        # Edge case: Multi-object selection
        test_id = f"{story_id}-{test_id_counter:03d}"
        title = f"{test_id}: {feature_name} / {entry_point} / Tool applied to multiple selected objects"
        steps = [
            {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
            {"action": "Launch the ENV QuickDraw application.", "expected": ""},
            {"action": "Create a new drawing.", "expected": ""},
            {"action": "Draw multiple shapes on the Canvas.", "expected": ""},
            {"action": "Select all drawn shapes.", "expected": ""},
            {"action": f"Activate {feature_name} tool via {entry_point}.", "expected": ""},
            {"action": f"Apply {feature_name} tool to the multi-object selection.", "expected": ""},
            {"action": "Verify the tool is applied to all selected objects.", "expected": "Tool is applied to all selected objects."},
            {"action": "Close/Exit the QuickDraw application", "expected": ""}
        ]
        objective = f"Verify that <b>{feature_name} tool</b> is <b>applied to all selected objects</b> in a multi-object selection"
        edge_cases.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        return edge_cases

    def _generate_measurement_edge_cases(self, story_id: int, feature_name: str, test_id_counter: int) -> List[Dict]:
        """Generate edge cases for Measurement stories."""
        edge_cases = []
        entry_point = self.grounded_spec.get_primary_entry_point() or "Dimensions Menu"

        # Always include these for measurement stories
        # Edge case: No selection
        if 'no_selection' not in self.grounded_spec.negative_scenarios:
            chain = ActionChainBuilder.chain_negative_no_selection(feature_name, entry_point)
            test_id = f"{story_id}-{test_id_counter:03d}"
            title = f"{test_id}: {feature_name} / {entry_point} / Behavior when no object is selected"
            steps = [
                {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
                {"action": "Launch the ENV QuickDraw application.", "expected": ""},
                {"action": "Create a new drawing.", "expected": ""}
            ]
            steps.extend(chain.steps)
            steps.append({"action": "Close/Exit the QuickDraw application", "expected": ""})
            objective = f"Verify that <b>{feature_name}</b> provides appropriate feedback when <b>no object is selected</b>"
            edge_cases.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})
            test_id_counter += 5

        # Edge case: Wrong object type (if object type constraints exist)
        if self.grounded_spec.object_types and 'wrong_object_type' not in self.grounded_spec.negative_scenarios:
            # Get the required object type from spec
            required_type = list(self.grounded_spec.object_types)[0] if self.grounded_spec.object_types else "ellipse"
            wrong_type = "rectangle" if required_type != "rectangle" else "triangle"

            chain = ActionChainBuilder.chain_negative_wrong_object_type(
                feature_name, entry_point, wrong_type, required_type
            )
            test_id = f"{story_id}-{test_id_counter:03d}"
            title = f"{test_id}: {feature_name} / {entry_point} / Behavior when non-{required_type} object is selected"
            steps = [
                {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
                {"action": "Launch the ENV QuickDraw application.", "expected": ""},
                {"action": "Create a new drawing.", "expected": ""}
            ]
            steps.extend(chain.steps)
            steps.append({"action": "Close/Exit the QuickDraw application", "expected": ""})
            objective = f"Verify that <b>{feature_name}</b> provides appropriate feedback when <b>non-{required_type} object</b> is selected"
            edge_cases.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})
            test_id_counter += 5

        # Edge case: Duplicate prevention
        chain = ActionChainBuilder.chain_duplicate_prevention(feature_name, entry_point)
        test_id = f"{story_id}-{test_id_counter:03d}"
        title = f"{test_id}: {feature_name} / {entry_point} / Reapplying measurement does not create duplicates"
        steps = [
            {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
            {"action": "Launch the ENV QuickDraw application.", "expected": ""},
            {"action": "Create a new drawing.", "expected": ""}
        ]
        steps.extend(chain.steps)
        steps.append({"action": "Close/Exit the QuickDraw application", "expected": ""})
        objective = f"Verify that <b>reapplying {feature_name}</b> does not create <b>duplicate measurements</b>"
        edge_cases.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})
        test_id_counter += 5

        # Edge case: Unit system (if units are mentioned)
        if 'metric' in {s.lower() for s in self.grounded_spec.ac_bullets.values()} or \
           'imperial' in {s.lower() for s in self.grounded_spec.ac_bullets.values()}:
            object_type = list(self.grounded_spec.object_types)[0] if self.grounded_spec.object_types else "ellipse"
            chain = ActionChainBuilder.chain_unit_system_test(feature_name, entry_point, object_type)
            test_id = f"{story_id}-{test_id_counter:03d}"
            title = f"{test_id}: {feature_name} / Units / Measurement label reflects active unit system"
            steps = [
                {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
                {"action": "Launch the ENV QuickDraw application.", "expected": ""},
                {"action": "Create a new drawing.", "expected": ""}
            ]
            steps.extend(chain.steps)
            steps.append({"action": "Close/Exit the QuickDraw application", "expected": ""})
            objective = f"Verify that <b>{feature_name} label</b> correctly reflects <b>Imperial or Metric unit system</b> changes"
            edge_cases.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        return edge_cases

    def _generate_file_ops_edge_cases(self, story_id: int, feature_name: str, test_id_counter: int) -> List[Dict]:
        """Generate edge cases for File Operations stories."""
        edge_cases = []
        entry_point = self.grounded_spec.get_primary_entry_point() or "File Menu"

        # Edge case: File not found
        test_id = f"{story_id}-{test_id_counter:03d}"
        title = f"{test_id}: {feature_name} / {entry_point} / File not found error handling"
        steps = [
            {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
            {"action": "Launch the ENV QuickDraw application.", "expected": ""},
            {"action": f"Attempt to open a file that does not exist via {entry_point}.", "expected": ""},
            {"action": "Verify the application displays an appropriate error message.", "expected": "Error message is displayed for file not found."},
            {"action": "Close/Exit the QuickDraw application", "expected": ""}
        ]
        objective = f"Verify that <b>{feature_name}</b> provides <b>appropriate error message</b> when <b>file is not found</b>"
        edge_cases.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        # Edge case: Recent files ordering
        test_id_counter += 5
        test_id = f"{story_id}-{test_id_counter:03d}"
        title = f"{test_id}: {feature_name} / {entry_point} / Recent files list ordering"
        steps = [
            {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
            {"action": "Launch the ENV QuickDraw application.", "expected": ""},
            {"action": "Open multiple files in sequence via {entry_point}.", "expected": ""},
            {"action": "Verify recent files list shows files in reverse chronological order.", "expected": "Recent files are ordered correctly."},
            {"action": "Close/Exit the QuickDraw application", "expected": ""}
        ]
        objective = f"Verify that <b>recent files list</b> displays files in <b>reverse chronological order</b>"
        edge_cases.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        return edge_cases

    def get_edge_case_count_estimate(self) -> int:
        """
        Estimate number of edge cases that will be generated.

        Returns:
            Estimated count of edge case tests
        """
        if self.story_type == StoryType.MODE_LAYOUT:
            return 2
        elif self.story_type == StoryType.DIALOG:
            return 2
        elif self.story_type == StoryType.TOOL:
            return 2
        elif self.story_type == StoryType.MEASUREMENT:
            return 3  # Can be up to 4 if units mentioned
        elif self.story_type == StoryType.FILE_OPS:
            return 2
        else:
            return 0
