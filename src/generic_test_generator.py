"""
Generic Test Generator - Project-agnostic test case generation.
Uses ProjectConfig to generate test cases for any application.
"""
from typing import List, Dict, Optional
import re

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projects.project_config import ProjectConfig
from projects.test_suite_creator import QAPrepGenerator


class GenericTestGenerator:
    """
    Generates test cases using project configuration.
    Replaces hardcoded ENV QuickDraw references with configurable templates.
    """

    def __init__(self, config: ProjectConfig):
        """
        Initialize generator with project configuration.

        Args:
            config: ProjectConfig for the target application.
        """
        self.config = config
        self.app = config.application
        self.rules = config.rules
        self.test_id_counter = config.rules.test_id_increment

    def generate_test_cases(
        self,
        story_data: Dict,
        criteria: List[str],
        qa_prep_content: Optional[str] = None
    ) -> List[Dict]:
        """
        Generate comprehensive test cases for a story.

        Args:
            story_data: Story information (story_id, title, description).
            criteria: List of acceptance criteria bullets.
            qa_prep_content: Optional QA Prep task content.

        Returns:
            List of test case dictionaries.
        """
        test_cases = []
        story_id = story_data['story_id']
        feature_name = self._extract_feature_name(story_data['title'])

        # Parse QA Prep or generate equivalent
        qa_details = self._parse_qa_prep(qa_prep_content) if qa_prep_content else {}

        # If no QA Prep and no details, generate them
        if not qa_details:
            qa_generator = QAPrepGenerator(self.config)
            qa_details = qa_generator.generate_qa_prep_content(story_data, criteria)

        # Generate test cases from AC
        for idx, ac_bullet in enumerate(criteria):
            # Skip cancelled AC
            if self._is_cancelled(ac_bullet):
                print(f"  Skipping cancelled AC{idx + 1}: {ac_bullet[:50]}...")
                continue

            # Generate test ID
            if idx == 0:
                test_id = f"{story_id}-{self.rules.first_test_id}"
            else:
                test_id = f"{story_id}-{self.test_id_counter:03d}"
                self.test_id_counter += self.rules.test_id_increment

            # Generate test case
            test_case = self._generate_test_for_ac(
                test_id, ac_bullet, idx + 1, feature_name, story_data, qa_details
            )
            if test_case:
                test_cases.append(test_case)

        # Generate edge case tests
        edge_cases = self._extract_edge_cases(qa_details, feature_name)
        for edge_case in edge_cases:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += self.rules.test_id_increment

            test_case = self._generate_edge_case_test(test_id, edge_case, feature_name, story_data)
            if test_case:
                test_cases.append(test_case)

        # Generate platform-specific tests
        if qa_details.get('platforms'):
            platform_tests = self._generate_platform_tests(
                story_id, feature_name, story_data, qa_details
            )
            test_cases.extend(platform_tests)

        # Generate accessibility tests
        accessibility_tests = self._generate_accessibility_tests(
            story_id, feature_name, story_data, qa_details
        )
        test_cases.extend(accessibility_tests)

        print(f"  Generated {len(test_cases)} test cases from {len(criteria)} AC bullets")
        return test_cases

    # ============ Step Template Methods ============

    def _get_prereq_step(self) -> Dict[str, str]:
        """Get the prerequisite step using project config."""
        return {"action": self.app.get_prereq_step(), "expected": ""}

    def _get_launch_step(self) -> Dict[str, str]:
        """Get the application launch step using project config."""
        return {"action": self.app.get_launch_step(), "expected": self.app.launch_expected}

    def _get_close_step(self) -> Dict[str, str]:
        """Get the application close step using project config."""
        return {"action": self.app.get_close_step(), "expected": ""}

    def _get_standard_setup_steps(self) -> List[Dict[str, str]]:
        """Get standard setup steps (prereq + launch)."""
        return [self._get_prereq_step(), self._get_launch_step()]

    def _get_object_setup_steps(self) -> List[Dict[str, str]]:
        """Get object interaction setup steps."""
        return [
            {"action": "Create a new document/drawing.", "expected": ""},
            {"action": "Create an object (e.g., shape, record, item) in the workspace.", "expected": ""},
            {"action": "Select the created object.", "expected": ""}
        ]

    # ============ Test Generation Methods ============

    def _generate_test_for_ac(
        self,
        test_id: str,
        ac_bullet: str,
        ac_index: int,
        feature_name: str,
        story_data: Dict,
        qa_details: Dict
    ) -> Optional[Dict]:
        """Generate test case for an acceptance criterion."""
        ac_lower = ac_bullet.lower()

        # AC1 is always availability test
        if test_id.endswith(self.rules.first_test_id):
            return self._generate_availability_test(
                test_id, ac_bullet, feature_name, story_data, qa_details
            )

        # Undo/Redo test
        if 'undo' in ac_lower or 'redo' in ac_lower:
            return self._generate_undo_redo_test(
                test_id, ac_bullet, feature_name, story_data, qa_details
            )

        # Accessibility test - will be generated separately
        if 'accessibility' in ac_lower or 'wcag' in ac_lower or '508' in ac_lower:
            return None

        # Generic test for other AC
        return self._generate_generic_test(
            test_id, ac_bullet, feature_name, story_data, qa_details
        )

    def _generate_availability_test(
        self,
        test_id: str,
        ac_bullet: str,
        feature_name: str,
        story_data: Dict,
        qa_details: Dict
    ) -> Dict:
        """Generate availability/access test for AC1."""
        entry_points = qa_details.get('entry_points', [])
        entry_point = self.app.determine_entry_point(feature_name, entry_points)

        title = f"{test_id}: {feature_name} / {entry_point} / Feature availability"

        steps = self._get_standard_setup_steps()
        steps.extend([
            {"action": f"Navigate to {entry_point}.", "expected": ""},
            {"action": f"Verify the {feature_name} option is visible and accessible.",
             "expected": f"{feature_name} option is present and accessible."},
        ])
        steps.append(self._get_close_step())

        objective = f"Verify that <b>{feature_name}</b> is available and accessible from <b>{entry_point}</b>"

        return {'id': test_id, 'title': title, 'steps': steps, 'objective': objective}

    def _generate_undo_redo_test(
        self,
        test_id: str,
        ac_bullet: str,
        feature_name: str,
        story_data: Dict,
        qa_details: Dict
    ) -> Dict:
        """Generate undo/redo test."""
        entry_point = self.app.determine_entry_point(feature_name, qa_details.get('entry_points', []))
        title = f"{test_id}: {feature_name} / {entry_point} / Undo and redo actions"

        steps = self._get_standard_setup_steps()
        steps.append({"action": "Create a new document/drawing.", "expected": ""})

        # Add object setup if needed
        if self.app.requires_object_interaction(ac_bullet) or self.app.requires_object_interaction(feature_name):
            steps.extend([
                {"action": "Create an object in the workspace.", "expected": ""},
                {"action": "Select the created object.", "expected": ""},
            ])

        steps.extend([
            {"action": f"Perform the {feature_name} action.", "expected": ""},
            {"action": f"Verify the {feature_name} action is applied.",
             "expected": f"{feature_name} action is completed successfully."},
            {"action": "Trigger Undo (Ctrl+Z or Cmd+Z).", "expected": ""},
            {"action": f"Verify the {feature_name} action is reversed.",
             "expected": f"{feature_name} action is undone."},
            {"action": "Trigger Redo (Ctrl+Y or Cmd+Shift+Z).", "expected": ""},
            {"action": f"Verify the {feature_name} action is restored.",
             "expected": f"{feature_name} action is restored after Redo."},
        ])
        steps.append(self._get_close_step())

        objective = f"Verify that <b>Undo</b> and <b>Redo</b> correctly reverse and restore <b>{feature_name}</b> actions"

        return {'id': test_id, 'title': title, 'steps': steps, 'objective': objective}

    def _generate_generic_test(
        self,
        test_id: str,
        ac_bullet: str,
        feature_name: str,
        story_data: Dict,
        qa_details: Dict
    ) -> Dict:
        """Generate a generic test based on AC content."""
        scenario = self._extract_scenario_from_ac(ac_bullet, feature_name)
        entry_point = self.app.determine_entry_point(feature_name, qa_details.get('entry_points', []))

        title = f"{test_id}: {feature_name} / {entry_point} / {scenario}"

        steps = self._get_standard_setup_steps()

        # Add object setup if AC requires object interaction
        if self.app.requires_object_interaction(ac_bullet):
            steps.extend(self._get_object_setup_steps())

        # Navigation step
        steps.append({"action": f"Navigate to {entry_point}.", "expected": ""})

        # Main action step
        main_action = self._extract_main_action(ac_bullet)
        steps.append({"action": main_action, "expected": ""})

        # Verification step
        verification = self._extract_verification(ac_bullet, feature_name)
        steps.append({"action": f"Verify {verification}.", "expected": f"{verification.capitalize()}."})

        steps.append(self._get_close_step())

        objective = f"Verify that <b>{feature_name}</b> {verification}"

        return {'id': test_id, 'title': title, 'steps': steps, 'objective': objective}

    def _generate_edge_case_test(
        self,
        test_id: str,
        edge_case: Dict,
        feature_name: str,
        story_data: Dict
    ) -> Optional[Dict]:
        """Generate test for edge case scenario."""
        edge_type = edge_case['type']
        entry_point = edge_case.get('entry_point', 'Application Menu')
        title = f"{test_id}: {feature_name} / {entry_point} / {edge_case['title']}"

        steps = self._get_standard_setup_steps()

        if edge_type == 'no_selection':
            steps.extend([
                {"action": "Create a new document/drawing.", "expected": ""},
                {"action": f"Navigate to {entry_point}.", "expected": ""},
                {"action": f"Attempt to use the {feature_name} feature.", "expected": ""},
                {"action": "Verify appropriate feedback is provided when no object is selected.",
                 "expected": "Feature is disabled or provides feedback that no object is selected."},
            ])
            objective = f"Verify that <b>{feature_name}</b> provides appropriate feedback when <b>no object is selected</b>"

        elif edge_type == 'invalid_type':
            steps.extend([
                {"action": "Create a new document/drawing.", "expected": ""},
                {"action": "Create an object of incompatible type.", "expected": ""},
                {"action": "Select the object.", "expected": ""},
                {"action": f"Navigate to {entry_point}.", "expected": ""},
                {"action": f"Attempt to use the {feature_name} feature.", "expected": ""},
                {"action": "Verify appropriate feedback is provided for incompatible object type.",
                 "expected": "Feature is disabled or provides feedback about incompatible object type."},
            ])
            objective = f"Verify that <b>{feature_name}</b> handles <b>incompatible object types</b> appropriately"

        elif edge_type == 'duplicate_prevention':
            steps.extend([
                {"action": "Create a new document/drawing.", "expected": ""},
                {"action": "Create and select an object.", "expected": ""},
                {"action": f"Navigate to {entry_point}.", "expected": ""},
                {"action": f"Apply the {feature_name} feature.", "expected": ""},
                {"action": "Verify the feature is applied once.", "expected": "Feature is applied successfully."},
                {"action": f"Navigate to {entry_point} again.", "expected": ""},
                {"action": f"Attempt to apply the {feature_name} feature again.", "expected": ""},
                {"action": "Verify no duplicate is created.",
                 "expected": "Feature prevents duplicate application."},
            ])
            objective = f"Verify that <b>reapplying {feature_name}</b> does not create <b>duplicates</b>"

        elif edge_type == 'empty_state':
            steps.extend([
                {"action": "Create a new empty document/drawing.", "expected": ""},
                {"action": f"Navigate to {entry_point}.", "expected": ""},
                {"action": f"Verify the {feature_name} feature behavior with empty state.",
                 "expected": "Feature handles empty state appropriately."},
            ])
            objective = f"Verify that <b>{feature_name}</b> handles <b>empty state</b> appropriately"

        else:
            return None

        steps.append(self._get_close_step())
        return {'id': test_id, 'title': title, 'steps': steps, 'objective': objective}

    def _generate_platform_tests(
        self,
        story_id: str,
        feature_name: str,
        story_data: Dict,
        qa_details: Dict
    ) -> List[Dict]:
        """Generate platform-specific tests."""
        platform_tests = []
        platforms = qa_details.get('platforms', [])
        entry_point = self.app.determine_entry_point(feature_name, qa_details.get('entry_points', []))

        # Check for touch platforms
        touch_platforms = [p for p in platforms if p in ['iPad', 'Android Tablet', 'iPhone', 'Android Phone']]

        if touch_platforms:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += self.rules.test_id_increment

            title = f"{test_id}: {feature_name} / {entry_point} / Touch interaction (Tablet/Mobile)"

            steps = self._get_standard_setup_steps()

            if self.app.requires_object_interaction(feature_name):
                steps.extend([
                    {"action": "Create a new document/drawing.", "expected": ""},
                    {"action": "Create an object using touch gestures.", "expected": ""},
                    {"action": "Select the object.", "expected": ""},
                ])

            steps.extend([
                {"action": f"Navigate to {entry_point} using touch.", "expected": ""},
                {"action": f"Perform the {feature_name} action using touch gestures.", "expected": ""},
                {"action": f"Verify the {feature_name} functionality works correctly with touch input.",
                 "expected": f"{feature_name} works correctly with touch interaction."},
            ])
            steps.append(self._get_close_step())

            objective = f"Verify that <b>{feature_name}</b> works correctly on <b>touch devices</b> using <b>touch or stylus</b>"
            platform_tests.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        return platform_tests

    def _generate_accessibility_tests(
        self,
        story_id: str,
        feature_name: str,
        story_data: Dict,
        qa_details: Dict
    ) -> List[Dict]:
        """Generate accessibility tests for each platform."""
        accessibility_tests = []
        platforms = qa_details.get('platforms', self.app.supported_platforms)
        entry_point = self.app.determine_entry_point(feature_name, qa_details.get('entry_points', []))

        # Windows accessibility test
        if 'Windows 11' in platforms or 'Windows 10' in platforms or 'Windows' in platforms:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += self.rules.test_id_increment

            title = f"{test_id}: {feature_name} / Accessibility / Keyboard navigation and labels (Windows)"

            steps = [
                self._get_prereq_step(),
                {"action": "Pre-req: Accessibility Insights for Windows is installed", "expected": ""},
                self._get_launch_step(),
                {"action": f"Navigate to {entry_point} using keyboard.", "expected": ""},
                {"action": f"Verify the {feature_name} controls are keyboard accessible.",
                 "expected": f"Keyboard focus moves to {feature_name} controls with visible focus indicator."},
                {"action": f"Verify {feature_name} controls expose meaningful labels in Accessibility Insights.",
                 "expected": "Controls expose correct accessible name and role."},
            ]
            steps.append(self._get_close_step())

            objective = f"Verify that <b>{feature_name}</b> controls meet <b>WCAG 2.1 AA</b> standards on <b>Windows</b>"
            accessibility_tests.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        # iPad/iOS accessibility test
        if 'iPad' in platforms or 'iPhone' in platforms:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += self.rules.test_id_increment

            title = f"{test_id}: {feature_name} / Accessibility / VoiceOver navigation (iOS)"

            steps = [
                self._get_prereq_step(),
                {"action": "Pre-req: VoiceOver is enabled", "expected": ""},
                self._get_launch_step(),
                {"action": f"Navigate to {entry_point} using VoiceOver swipe gestures.", "expected": ""},
                {"action": f"Verify the {feature_name} controls are announced with meaningful labels.",
                 "expected": f"VoiceOver announces {feature_name} controls with meaningful labels and roles."},
                {"action": "Verify reading order is logical.",
                 "expected": "VoiceOver announces controls in logical order."},
            ]
            steps.append(self._get_close_step())

            objective = f"Verify that <b>{feature_name}</b> controls are accessible via <b>VoiceOver</b>"
            accessibility_tests.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        # Android accessibility test
        if 'Android Tablet' in platforms or 'Android Phone' in platforms or 'Android' in platforms:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += self.rules.test_id_increment

            title = f"{test_id}: {feature_name} / Accessibility / Accessibility Scanner (Android)"

            steps = [
                self._get_prereq_step(),
                {"action": "Pre-req: Accessibility Scanner is installed", "expected": ""},
                self._get_launch_step(),
                {"action": f"Navigate to {entry_point}.", "expected": ""},
                {"action": f"Run Accessibility Scanner on the {feature_name} controls.", "expected": ""},
                {"action": f"Verify Accessibility Scanner reports no critical issues for {feature_name} controls.",
                 "expected": "Controls have readable labels and appropriate roles."},
            ]
            steps.append(self._get_close_step())

            objective = f"Verify that <b>{feature_name}</b> controls meet accessibility standards on <b>Android</b>"
            accessibility_tests.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        # Web browser accessibility (for web apps)
        if self.app.app_type == 'web':
            web_platforms = [p for p in platforms if p in ['Chrome', 'Firefox', 'Safari', 'Edge']]
            if web_platforms:
                test_id = f"{story_id}-{self.test_id_counter:03d}"
                self.test_id_counter += self.rules.test_id_increment

                title = f"{test_id}: {feature_name} / Accessibility / Screen reader and keyboard (Web)"

                steps = [
                    self._get_prereq_step(),
                    {"action": "Pre-req: Screen reader (NVDA/JAWS/VoiceOver) is enabled", "expected": ""},
                    self._get_launch_step(),
                    {"action": f"Navigate to {entry_point} using keyboard (Tab/Arrow keys).", "expected": ""},
                    {"action": f"Verify the {feature_name} controls have correct ARIA roles and labels.",
                     "expected": "Screen reader announces controls with meaningful labels."},
                    {"action": "Verify focus indicators are visible.",
                     "expected": "Focus is clearly visible on all interactive elements."},
                ]
                steps.append(self._get_close_step())

                objective = f"Verify that <b>{feature_name}</b> is accessible via <b>keyboard and screen reader</b>"
                accessibility_tests.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        return accessibility_tests

    # ============ Helper Methods ============

    def _parse_qa_prep(self, qa_prep: str) -> Dict:
        """Parse QA Prep content to extract testing details."""
        if not qa_prep:
            return {}

        qa_lower = qa_prep.lower()
        details = {
            'entry_points': [],
            'platforms': [],
            'edge_cases': [],
            'units': False,
            'undo_redo_actions': [],
            'visibility': False,
            'negative_scenarios': []
        }

        # Extract entry points using project config
        for keyword, entry_point in self.app.entry_point_mappings.items():
            if keyword in qa_lower:
                if entry_point not in details['entry_points']:
                    details['entry_points'].append(entry_point)

        # Extract platforms
        for platform in self.app.supported_platforms:
            if platform.lower() in qa_lower:
                details['platforms'].append(platform)

        # Detect unit system tests
        if 'imperial' in qa_lower and 'metric' in qa_lower:
            details['units'] = True

        # Detect visibility toggle
        if 'visibility' in qa_lower or 'show or hide' in qa_lower:
            details['visibility'] = True

        # Extract undo/redo actions
        if 'undo' in qa_lower or 'redo' in qa_lower:
            if 'add' in qa_lower or 'remove' in qa_lower:
                details['undo_redo_actions'].append('add/remove')
            if 'visibility' in qa_lower:
                details['undo_redo_actions'].append('visibility')

        # Detect negative scenarios
        if 'no object' in qa_lower or 'no selection' in qa_lower:
            details['negative_scenarios'].append('no_selection')
        if 'wrong' in qa_lower or 'invalid' in qa_lower:
            details['negative_scenarios'].append('invalid_type')
        if 'duplicate' in qa_lower or 'reappl' in qa_lower:
            details['edge_cases'].append('duplicate_prevention')

        return details

    def _extract_edge_cases(self, qa_details: Dict, feature_name: str) -> List[Dict]:
        """Extract edge case scenarios from QA details."""
        edge_cases = []
        entry_point = self.app.determine_entry_point(feature_name, qa_details.get('entry_points', []))

        if 'no_selection' in qa_details.get('negative_scenarios', []):
            edge_cases.append({
                'type': 'no_selection',
                'title': f'{feature_name} behavior when no object is selected',
                'entry_point': entry_point
            })

        if 'invalid_type' in qa_details.get('negative_scenarios', []):
            edge_cases.append({
                'type': 'invalid_type',
                'title': f'{feature_name} behavior with incompatible object type',
                'entry_point': entry_point
            })

        if 'duplicate_prevention' in qa_details.get('edge_cases', []):
            edge_cases.append({
                'type': 'duplicate_prevention',
                'title': f'Reapplying {feature_name} does not create duplicates',
                'entry_point': entry_point
            })

        if 'empty_state' in qa_details.get('edge_cases', []):
            edge_cases.append({
                'type': 'empty_state',
                'title': f'{feature_name} behavior with empty state',
                'entry_point': entry_point
            })

        return edge_cases

    def _extract_feature_name(self, story_title: str) -> str:
        """Extract the core feature name from story title."""
        title = story_title.strip()

        # Remove user story prefixes
        prefixes = ['As a', 'As an', 'I want', 'I need', 'User can', 'Users can']
        for prefix in prefixes:
            if title.lower().startswith(prefix.lower()):
                parts = title.split(',')
                if len(parts) > 1:
                    title = parts[1].strip() if 'so that' not in parts[1].lower() else parts[0].replace(prefix, '').strip()
                else:
                    title = title.replace(prefix, '').strip()
                break

        return title

    def _extract_scenario_from_ac(self, ac_bullet: str, feature_name: str) -> str:
        """Extract a clean scenario description from AC text."""
        text = ac_bullet.strip()
        prefixes = ['the user can', 'user can', 'users can', 'the system shall',
                    'shall be able to', 'able to']

        text_lower = text.lower()
        for prefix in prefixes:
            if text_lower.startswith(prefix):
                text = text[len(prefix):].strip()
                break

        if text:
            text = text[0].upper() + text[1:]

        if len(text) > 60:
            text = text[:57] + "..."

        return text if text else f"{feature_name} functionality"

    def _extract_main_action(self, ac_bullet: str) -> str:
        """Extract the main action from AC text."""
        text = ac_bullet.strip()
        action_verbs = ['import', 'export', 'save', 'open', 'create', 'delete', 'edit',
                        'select', 'click', 'drag', 'enable', 'disable', 'toggle', 'set']

        text_lower = text.lower()
        for verb in action_verbs:
            if verb in text_lower:
                idx = text_lower.find(verb)
                action = text[idx:].split('.')[0].strip()
                if action:
                    return action[0].upper() + action[1:] + "."

        return f"Perform the action described: {text[:80]}."

    def _extract_verification(self, ac_bullet: str, feature_name: str) -> str:
        """Extract verification criteria from AC text."""
        text = ac_bullet.lower()

        if 'should' in text:
            idx = text.find('should')
            return text[idx:].split('.')[0].strip()
        elif 'will' in text:
            idx = text.find('will')
            return text[idx:].split('.')[0].strip()
        elif 'displayed' in text or 'shown' in text or 'visible' in text:
            return f"the {feature_name} is displayed correctly"

        return f"the {feature_name} works as expected"

    def _is_cancelled(self, text: str) -> bool:
        """Check if text indicates cancelled/out-of-scope."""
        text_lower = text.lower()
        return any(ind in text_lower for ind in self.rules.cancelled_indicators)
