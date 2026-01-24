"""
Comprehensive Test Generator with Full Edge Case Coverage
Generates test cases matching ChatGPT quality level by extracting all edge cases from AC and QA Prep.
"""
from typing import List, Dict, Optional, Tuple
import re
from src.test_rules import TestRules
import config


class ComprehensiveTestGenerator:
    """Generates comprehensive test cases with full edge case coverage."""

    def __init__(self):
        self.rules = TestRules()
        self.test_id_counter = 5

    def generate_test_cases(self, story_data: Dict, criteria: List[str], qa_prep_content: Optional[str] = None) -> List[Dict]:
        """
        Generate comprehensive test cases with edge cases from AC + QA Prep.

        Returns:
            List of test case dicts
        """
        test_cases = []
        story_id = story_data['story_id']
        feature_name = self.rules.extract_feature_name(story_data['title'])

        # Parse QA Prep for edge cases and details
        qa_details = self._parse_qa_prep(qa_prep_content) if qa_prep_content else {}

        # Generate test cases from AC
        for idx, ac_bullet in enumerate(criteria):
            # Skip cancelled AC
            if self.rules.is_cancelled(ac_bullet):
                print(f"  ⚠ Skipping cancelled AC{idx + 1}: {ac_bullet[:50]}...")
                continue

            # Generate test ID
            if idx == 0:
                test_id = f"{story_id}-AC1"
            else:
                test_id = f"{story_id}-{self.test_id_counter:03d}"
                self.test_id_counter += 5

            # Generate primary test case for this AC
            test_case = self._generate_primary_test(
                test_id, ac_bullet, idx + 1, feature_name, story_data, qa_details
            )
            if test_case:
                test_cases.append(test_case)

        # Generate edge case tests from QA Prep
        edge_cases = self._extract_edge_cases(qa_details, feature_name, story_data)
        for edge_case in edge_cases:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += 5

            test_case = self._generate_edge_case_test(test_id, edge_case, feature_name, story_data)
            if test_case:
                test_cases.append(test_case)

        # Generate platform-specific tests if mentioned in QA Prep
        if qa_details.get('platforms'):
            platform_tests = self._generate_platform_tests(story_id, feature_name, story_data, qa_details)
            for pt in platform_tests:
                test_cases.append(pt)

        # Generate accessibility tests
        accessibility_tests = self._generate_accessibility_tests(story_id, feature_name, story_data, qa_details)
        for at in accessibility_tests:
            test_cases.append(at)

        print(f"  Generated {len(test_cases)} test cases from {len(criteria)} AC bullets (including edge cases)")
        return test_cases

    def _parse_qa_prep(self, qa_prep: str) -> Dict:
        """Parse QA Prep to extract structured information."""
        details = {
            'entry_points': [],
            'platforms': [],
            'edge_cases': [],
            'units': False,
            'undo_redo_actions': [],
            'visibility': False,
            'negative_scenarios': []
        }

        qa_lower = qa_prep.lower()

        # Extract entry points
        if 'dimensions menu' in qa_lower or 'dimensions →' in qa_lower:
            details['entry_points'].append('Dimensions Menu')
        if 'properties' in qa_lower and 'design' in qa_lower:
            details['entry_points'].append('Properties – Design Panel')

        # Extract platforms
        if 'windows 11' in qa_lower or 'mouse/keyboard' in qa_lower:
            details['platforms'].append('Windows 11')
        if 'ipad' in qa_lower or 'ipados' in qa_lower:
            details['platforms'].append('iPad')
        if 'android' in qa_lower and 'tablet' in qa_lower:
            details['platforms'].append('Android Tablet')

        # Detect unit system tests
        if 'imperial' in qa_lower and 'metric' in qa_lower:
            details['units'] = True

        # Detect visibility toggle
        if 'visibility' in qa_lower or 'show or hide' in qa_lower:
            details['visibility'] = True

        # Extract undo/redo actions
        if 'undo' in qa_lower or 'redo' in qa_lower:
            if 'add/remove' in qa_lower or 'adding' in qa_lower:
                details['undo_redo_actions'].append('add/remove')
            if 'visibility' in qa_lower or 'hide' in qa_lower:
                details['undo_redo_actions'].append('visibility')

        # Detect negative scenarios
        if 'no object' in qa_lower or 'no selection' in qa_lower:
            details['negative_scenarios'].append('no_selection')
        if 'non-ellipse' in qa_lower or 'wrong object' in qa_lower or 'boundary' in qa_lower:
            details['negative_scenarios'].append('wrong_object_type')
        if 'duplicate' in qa_lower or 'reappl' in qa_lower:
            details['edge_cases'].append('duplicate_prevention')

        # For Dimensions/Measurement features ONLY, include diameter-specific edge cases
        # These are specific to diameter/measurement stories
        if 'diameter' in qa_lower or ('dimension' in qa_lower and 'measurement' in qa_lower):
            # Test "no selection" scenario for measurement features
            if 'no_selection' not in details['negative_scenarios']:
                details['negative_scenarios'].append('no_selection')
            # Test "wrong object type" scenario for shape-specific measurements
            if 'ellipse' in qa_lower or 'circle' in qa_lower:
                if 'wrong_object_type' not in details['negative_scenarios']:
                    details['negative_scenarios'].append('wrong_object_type')
            # Test duplicate prevention for measurements
            if 'duplicate_prevention' not in details['edge_cases']:
                details['edge_cases'].append('duplicate_prevention')

        return details

    def _generate_primary_test(self, test_id: str, ac_bullet: str, ac_index: int,
                                feature_name: str, story_data: Dict, qa_details: Dict) -> Optional[Dict]:
        """Generate primary test case for AC bullet - GENERIC for any story type."""

        # AC1 is always availability test
        if '-AC1' in test_id:
            return self._generate_ac1_test(test_id, ac_bullet, feature_name, story_data, qa_details)

        # Detect test type from AC content
        ac_lower = ac_bullet.lower()
        feature_lower = feature_name.lower()

        # Check if this is a diameter/measurement specific story (use specialized generators)
        is_diameter_story = 'diameter' in feature_lower or ('dimension' in feature_lower and 'measurement' in feature_lower)

        if is_diameter_story:
            # Use specialized diameter generators for diameter stories only
            if 'user chooses' in ac_lower or 'enables' in ac_lower or 'toggle' in ac_lower:
                return self._generate_create_measurement_test(test_id, ac_bullet, feature_name, story_data, qa_details)
            if 'visibility' in ac_lower or 'show or hide' in ac_lower:
                return self._generate_visibility_test(test_id, ac_bullet, feature_name, story_data, qa_details)
            if 'cannot be' in ac_lower or 'reposition' in ac_lower or 'placement' in ac_lower:
                return self._generate_constraint_test(test_id, ac_bullet, feature_name, story_data, qa_details)

        # Undo/Redo test (generic for any feature)
        if 'undo' in ac_lower or 'redo' in ac_lower:
            return self._generate_comprehensive_undo_redo_test(test_id, ac_bullet, feature_name, story_data, qa_details)

        # Accessibility test - will be generated separately at the end
        if 'accessibility' in ac_lower or 'wcag' in ac_lower or '508' in ac_lower:
            return None

        # For all other cases, use the generic test generator
        return self._generate_generic_test(test_id, ac_bullet, feature_name, story_data, qa_details)

    def _generate_ac1_test(self, test_id: str, ac_bullet: str, feature_name: str,
                           story_data: Dict, qa_details: Dict) -> Dict:
        """Generate AC1 availability test - GENERIC for any story type."""
        # Extract entry point from QA details or determine from feature name
        entry_points = qa_details.get('entry_points', [])
        entry_point = self._determine_entry_point(feature_name, entry_points)

        # Create generic availability title based on feature
        title = f"{test_id}: {feature_name} / {entry_point} / Feature availability"

        steps = [
            {"action": "Pre-req: The ENV QuickDraw App is installed", "expected": ""},
            {"action": "Launch the ENV QuickDraw application.", "expected": "Model space(Gray) and Canvas(white) space should be displayed"},
            {"action": f"Navigate to {entry_point}.", "expected": ""},
            {"action": f"Verify the {feature_name} option is visible and accessible.", "expected": f"{feature_name} option is present and accessible."},
            {"action": "Close the ENV QuickDraw App", "expected": ""}
        ]

        objective = f"Verify that <b>{feature_name}</b> is available and accessible from <b>{entry_point}</b>"

        return {'id': test_id, 'title': title, 'steps': steps, 'objective': objective}

    def _determine_entry_point(self, feature_name: str, entry_points: list) -> str:
        """Determine the most appropriate entry point based on feature name."""
        if entry_points:
            return entry_points[0]

        feature_lower = feature_name.lower()

        # Map feature keywords to entry points
        if 'import' in feature_lower:
            return 'File Menu'
        elif 'export' in feature_lower:
            return 'File Menu'
        elif 'save' in feature_lower:
            return 'File Menu'
        elif 'open' in feature_lower:
            return 'File Menu'
        elif 'new' in feature_lower:
            return 'File Menu'
        elif 'undo' in feature_lower or 'redo' in feature_lower:
            return 'Edit Menu'
        elif 'copy' in feature_lower or 'paste' in feature_lower or 'cut' in feature_lower:
            return 'Edit Menu'
        elif 'view' in feature_lower or 'zoom' in feature_lower or 'pan' in feature_lower:
            return 'View Menu'
        elif 'tool' in feature_lower or 'draw' in feature_lower or 'shape' in feature_lower:
            return 'Tools Menu'
        elif 'dimension' in feature_lower or 'measure' in feature_lower or 'diameter' in feature_lower:
            return 'Dimensions Menu'
        elif 'propert' in feature_lower:
            return 'Properties Panel'
        elif 'setting' in feature_lower or 'preference' in feature_lower:
            return 'Settings'
        else:
            return 'Application Menu'

    def _generate_create_measurement_test(self, test_id: str, ac_bullet: str, feature_name: str,
                                           story_data: Dict, qa_details: Dict) -> Dict:
        """Generate test for creating diameter measurement."""
        entry_points = qa_details.get('entry_points', ['Dimensions Menu'])

        # Generate one test per entry point
        entry_point = entry_points[0] if len(entry_points) > 0 else 'Dimensions Menu'

        # Determine action based on entry point
        if 'Properties' in entry_point:
            action_desc = "Enable diameter measurement using toggle for selected ellipse"
            enable_steps = [
                {"action": f"Open the {entry_point}.", "expected": ""},
                {"action": "Enable the Diameter measurement toggle.", "expected": ""}
            ]
        else:
            action_desc = "Create diameter measurement for selected ellipse"
            enable_steps = [
                {"action": "Open the Dimensions menu.", "expected": ""},
                {"action": "Select Diameter.", "expected": ""}
            ]

        title = f"{test_id}: {feature_name} / {entry_point} / {action_desc}"

        steps = [
            {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
            {"action": "Launch the ENV QuickDraw application.", "expected": ""},
            {"action": "Create a new drawing.", "expected": ""},
            {"action": "Draw an ellipse on the Canvas.", "expected": ""},
            {"action": "Select the drawn ellipse on the Canvas.", "expected": ""},
        ]
        steps.extend(enable_steps)
        steps.extend([
            {"action": "Verify a diameter line is drawn across the ellipse and a diameter label is displayed on the Canvas.",
             "expected": "Diameter line and label are displayed for the selected ellipse."},
        ])

        # Add unit system verification if mentioned in QA Prep
        if qa_details.get('units'):
            steps.append({
                "action": "Verify the diameter label displays a numeric value using the current unit system.",
                "expected": "Diameter label shows a numeric value and matches the active unit system."
            })

        steps.append({"action": "Close/Exit the QuickDraw application", "expected": ""})

        objective = f"Verify that <b>Diameter measurement</b> can be created for a selected ellipse via <b>{entry_point}</b>, displaying diameter line and label with correct unit system"

        return {'id': test_id, 'title': title, 'steps': steps, 'objective': objective}

    def _generate_constraint_test(self, test_id: str, ac_bullet: str, feature_name: str,
                                   story_data: Dict, qa_details: Dict) -> Dict:
        """Generate test for fixed placement constraint."""
        title = f"{test_id}: {feature_name} / Canvas / Diameter measurement uses fixed standard placement and cannot be manually repositioned"

        steps = [
            {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
            {"action": "Launch the ENV QuickDraw application.", "expected": ""},
            {"action": "Create a new drawing.", "expected": ""},
            {"action": "Draw an ellipse on the Canvas.", "expected": ""},
            {"action": "Select the drawn ellipse on the Canvas.", "expected": ""},
            {"action": "Open the Dimensions menu.", "expected": ""},
            {"action": "Select Diameter.", "expected": ""},
            {"action": "Attempt to drag the diameter label to a new location on the Canvas.", "expected": ""},
            {"action": "Verify the diameter label position does not change and remains in the system-defined placement.",
             "expected": "Diameter label cannot be manually repositioned and remains fixed by standard placement rules."},
            {"action": "Close/Exit the QuickDraw application", "expected": ""}
        ]

        objective = "Verify that <b>diameter label</b> uses <b>fixed standard placement</b> and <b>cannot be manually repositioned</b> on the Canvas"

        return {'id': test_id, 'title': title, 'steps': steps, 'objective': objective}

    def _generate_visibility_test(self, test_id: str, ac_bullet: str, feature_name: str,
                                   story_data: Dict, qa_details: Dict) -> Dict:
        """Generate visibility toggle test."""
        title = f"{test_id}: {feature_name} / Properties – Design Panel / Show and hide diameter measurement using visibility control"

        steps = [
            {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
            {"action": "Launch the ENV QuickDraw application.", "expected": ""},
            {"action": "Create a new drawing.", "expected": ""},
            {"action": "Draw an ellipse on the Canvas.", "expected": ""},
            {"action": "Select the drawn ellipse on the Canvas.", "expected": ""},
            {"action": "Open the Properties – Design panel.", "expected": ""},
            {"action": "Enable the Diameter measurement toggle.", "expected": ""},
            {"action": "Disable the Show Diameter visibility control.", "expected": ""},
            {"action": "Verify the diameter line and label are hidden and do not occupy space on the Canvas UI.",
             "expected": "Diameter line and label are not visible after hiding."},
            {"action": "Enable the Show Diameter visibility control.", "expected": ""},
            {"action": "Verify the diameter line and label are visible again in the system-defined placement.",
             "expected": "Diameter line and label are visible after showing."},
            {"action": "Close/Exit the QuickDraw application", "expected": ""}
        ]

        objective = "Verify that <b>visibility control</b> allows user to <b>show and hide</b> diameter measurement for selected object"

        return {'id': test_id, 'title': title, 'steps': steps, 'objective': objective}

    def _generate_comprehensive_undo_redo_test(self, test_id: str, ac_bullet: str, feature_name: str,
                                                 story_data: Dict, qa_details: Dict) -> Dict:
        """Generate comprehensive undo/redo test - GENERIC for any feature."""
        entry_point = self._determine_entry_point(feature_name, qa_details.get('entry_points', []))
        title = f"{test_id}: {feature_name} / {entry_point} / Undo and redo actions"

        steps = [
            {"action": "Pre-req: The ENV QuickDraw App is installed", "expected": ""},
            {"action": "Launch the ENV QuickDraw application.", "expected": "Model space(Gray) and Canvas(white) space should be displayed"},
            {"action": "Create a new drawing.", "expected": ""},
        ]

        # Add object setup if needed
        if self.rules.requires_object_interaction(ac_bullet) or self.rules.requires_object_interaction(feature_name):
            steps.extend([
                {"action": "Draw a shape on the Canvas.", "expected": ""},
                {"action": "Select the drawn object.", "expected": ""},
            ])

        # Perform action
        steps.extend([
            {"action": f"Perform the {feature_name} action.", "expected": ""},
            {"action": f"Verify the {feature_name} action is applied.",
             "expected": f"{feature_name} action is completed successfully."},
            {"action": "Trigger Undo.", "expected": ""},
            {"action": f"Verify the {feature_name} action is reversed.",
             "expected": f"{feature_name} action is undone."},
            {"action": "Trigger Redo.", "expected": ""},
            {"action": f"Verify the {feature_name} action is restored.",
             "expected": f"{feature_name} action is restored after Redo."},
        ])

        steps.append({"action": "Close the ENV QuickDraw App", "expected": ""})

        objective = f"Verify that <b>Undo</b> and <b>Redo</b> operations correctly reverse and restore <b>{feature_name}</b> actions"

        return {'id': test_id, 'title': title, 'steps': steps, 'objective': objective}

    def _generate_generic_test(self, test_id: str, ac_bullet: str, feature_name: str,
                                story_data: Dict, qa_details: Dict) -> Dict:
        """Generate a generic test based on AC content - works for any story type."""
        # Extract a clean scenario description from the AC
        scenario = self._extract_scenario_from_ac(ac_bullet, feature_name)
        entry_point = self._determine_entry_point(feature_name, qa_details.get('entry_points', []))

        title = f"{test_id}: {feature_name} / {entry_point} / {scenario}"

        # Build steps based on AC content
        steps = [
            {"action": "Pre-req: The ENV QuickDraw App is installed", "expected": ""},
            {"action": "Launch the ENV QuickDraw application.", "expected": "Model space(Gray) and Canvas(white) space should be displayed"},
        ]

        # Add object setup if AC requires object interaction
        if self.rules.requires_object_interaction(ac_bullet):
            steps.extend([
                {"action": "Create a new drawing.", "expected": ""},
                {"action": "Draw a shape on the Canvas.", "expected": ""},
                {"action": "Select the drawn object.", "expected": ""},
            ])

        # Add navigation to entry point
        steps.append({"action": f"Navigate to {entry_point}.", "expected": ""})

        # Add main action step based on AC
        main_action = self._extract_main_action(ac_bullet)
        steps.append({"action": main_action, "expected": ""})

        # Add verification step
        verification = self._extract_verification(ac_bullet, feature_name)
        steps.append({"action": f"Verify {verification}.", "expected": f"{verification.capitalize()}."})

        steps.append({"action": "Close the ENV QuickDraw App", "expected": ""})

        objective = f"Verify that <b>{feature_name}</b> {verification}"

        return {'id': test_id, 'title': title, 'steps': steps, 'objective': objective}

    def _extract_scenario_from_ac(self, ac_bullet: str, feature_name: str) -> str:
        """Extract a clean scenario description from AC text."""
        # Remove common prefixes
        text = ac_bullet.strip()
        prefixes_to_remove = ['the user can', 'user can', 'users can', 'the system shall', 'system shall',
                              'the application shall', 'application shall', 'shall be able to', 'able to']
        text_lower = text.lower()
        for prefix in prefixes_to_remove:
            if text_lower.startswith(prefix):
                text = text[len(prefix):].strip()
                break

        # Capitalize first letter and limit length
        if text:
            text = text[0].upper() + text[1:]

        # Truncate if too long
        if len(text) > 60:
            text = text[:57] + "..."

        return text if text else f"{feature_name} functionality"

    def _extract_main_action(self, ac_bullet: str) -> str:
        """Extract the main action from AC text."""
        text = ac_bullet.strip()

        # If it starts with action verbs, use it directly
        action_verbs = ['import', 'export', 'save', 'open', 'create', 'delete', 'edit', 'modify',
                        'select', 'click', 'drag', 'drop', 'enable', 'disable', 'toggle', 'set']

        text_lower = text.lower()
        for verb in action_verbs:
            if verb in text_lower:
                # Find the verb position and extract action
                idx = text_lower.find(verb)
                action = text[idx:].split('.')[0].strip()
                if action:
                    return action[0].upper() + action[1:] + "."

        return f"Perform the action described: {text[:80]}."

    def _extract_verification(self, ac_bullet: str, feature_name: str) -> str:
        """Extract verification criteria from AC text."""
        text = ac_bullet.lower()

        # Look for expected outcomes
        if 'should' in text:
            idx = text.find('should')
            return text[idx:].split('.')[0].strip()
        elif 'will' in text:
            idx = text.find('will')
            return text[idx:].split('.')[0].strip()
        elif 'is' in text and ('displayed' in text or 'shown' in text or 'visible' in text):
            return f"the {feature_name} is displayed correctly"

        return f"the {feature_name} works as expected"

    def _extract_edge_cases(self, qa_details: Dict, feature_name: str, story_data: Dict) -> List[Dict]:
        """Extract edge case scenarios from QA Prep."""
        edge_cases = []

        # No selection scenario
        if 'no_selection' in qa_details.get('negative_scenarios', []):
            edge_cases.append({
                'type': 'no_selection',
                'title': 'Diameter option behavior when no object is selected',
                'entry_point': 'Dimensions Menu'
            })

        # Wrong object type scenario
        if 'wrong_object_type' in qa_details.get('negative_scenarios', []):
            edge_cases.append({
                'type': 'wrong_object',
                'title': 'Diameter option behavior when a non-ellipse object is selected',
                'entry_point': 'Dimensions Menu'
            })

        # Duplicate prevention
        if 'duplicate_prevention' in qa_details.get('edge_cases', []):
            edge_cases.append({
                'type': 'duplicate',
                'title': 'Reapplying Diameter does not create duplicate measurements',
                'entry_point': 'Dimensions Menu'
            })

        # Unit system test
        if qa_details.get('units'):
            edge_cases.append({
                'type': 'units',
                'title': 'Diameter label reflects active Imperial or Metric unit system',
                'entry_point': 'Units'
            })

        return edge_cases

    def _generate_edge_case_test(self, test_id: str, edge_case: Dict, feature_name: str, story_data: Dict) -> Dict:
        """Generate test for edge case scenario."""
        edge_type = edge_case['type']
        title = f"{test_id}: {feature_name} / {edge_case['entry_point']} / {edge_case['title']}"

        if edge_type == 'no_selection':
            steps = [
                {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
                {"action": "Launch the ENV QuickDraw application.", "expected": ""},
                {"action": "Create a new drawing.", "expected": ""},
                {"action": "Open the Dimensions menu.", "expected": ""},
                {"action": "Select Diameter.", "expected": ""},
                {"action": "Verify no diameter measurement is created on the Canvas and the app provides clear feedback.",
                 "expected": "No diameter line and label is created when no object is selected."},
                {"action": "Close/Exit the QuickDraw application", "expected": ""}
            ]
            objective = "Verify that <b>Diameter option</b> provides appropriate feedback when <b>no object is selected</b>"

        elif edge_type == 'wrong_object':
            steps = [
                {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
                {"action": "Launch the ENV QuickDraw application.", "expected": ""},
                {"action": "Create a new drawing.", "expected": ""},
                {"action": "Draw a rectangle on the Canvas.", "expected": ""},
                {"action": "Select the drawn rectangle on the Canvas.", "expected": ""},
                {"action": "Open the Dimensions menu.", "expected": ""},
                {"action": "Select Diameter.", "expected": ""},
                {"action": "Verify no diameter measurement is created for the non-ellipse selection and the app provides clear feedback .",
                 "expected": "No diameter line and label is created for a non-ellipse object."},
                {"action": "Close/Exit the QuickDraw application", "expected": ""}
            ]
            objective = "Verify that <b>Diameter option</b> provides appropriate feedback when <b>non-ellipse object</b> is selected"

        elif edge_type == 'duplicate':
            steps = [
                {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
                {"action": "Launch the ENV QuickDraw application.", "expected": ""},
                {"action": "Create a new drawing.", "expected": ""},
                {"action": "Draw an ellipse on the Canvas.", "expected": ""},
                {"action": "Select the drawn ellipse on the Canvas.", "expected": ""},
                {"action": "Open the Dimensions menu.", "expected": ""},
                {"action": "Select Diameter.", "expected": ""},
                {"action": "Verify one diameter line and one diameter label are displayed.",
                 "expected": "A single diameter line and label are displayed."},
                {"action": "Open the Dimensions menu.", "expected": ""},
                {"action": "Select Diameter.", "expected": ""},
                {"action": "Verify the ellipse still shows a single diameter line and label with no duplicates.",
                 "expected": "No duplicate diameter lines and labels are created."},
                {"action": "Close/Exit the QuickDraw application", "expected": ""}
            ]
            objective = "Verify that <b>reapplying Diameter</b> does not create <b>duplicate measurements</b>"

        elif edge_type == 'units':
            steps = [
                {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
                {"action": "Launch the ENV QuickDraw application.", "expected": ""},
                {"action": "Create a new drawing.", "expected": ""},
                {"action": "Set Unit of Measure to Imperial in application settings.", "expected": ""},
                {"action": "Draw an ellipse on the Canvas.", "expected": ""},
                {"action": "Select the drawn ellipse on the Canvas.", "expected": ""},
                {"action": "Open the Dimensions menu.", "expected": ""},
                {"action": "Select Diameter.", "expected": ""},
                {"action": "Verify the diameter label displays the measurement using Imperial units.",
                 "expected": "Diameter label uses Imperial units."},
                {"action": "Set Unit of Measure to Metric in application settings.", "expected": ""},
                {"action": "Verify the diameter label updates to display the measurement using Metric units.",
                 "expected": "Diameter label uses Metric units."},
                {"action": "Close/Exit the QuickDraw application", "expected": ""}
            ]
            objective = "Verify that <b>diameter label</b> correctly reflects <b>Imperial or Metric unit system</b> changes"
        else:
            steps = []
            objective = ""

        return {'id': test_id, 'title': title, 'steps': steps, 'objective': objective}

    def _generate_platform_tests(self, story_id: str, feature_name: str, story_data: Dict, qa_details: Dict) -> List[Dict]:
        """Generate platform-specific tests if applicable - GENERIC for any feature."""
        platform_tests = []
        platforms = qa_details.get('platforms', [])
        entry_point = self._determine_entry_point(feature_name, qa_details.get('entry_points', []))
        feature_lower = feature_name.lower()

        # Check if this is a diameter-specific story
        is_diameter_story = 'diameter' in feature_lower or ('dimension' in feature_lower and 'measurement' in feature_lower)

        # Only generate separate tablet tests if mentioned and feature involves touch interaction
        if 'iPad' in platforms or 'Android Tablet' in platforms:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += 5

            # Generate generic tablet functional test
            title = f"{test_id}: {feature_name} / {entry_point} / Touch interaction (Tablet)"
            steps = [
                {"action": "Pre-req: The ENV QuickDraw App is installed", "expected": ""},
                {"action": "Launch the ENV QuickDraw application.", "expected": "Model space(Gray) and Canvas(white) space should be displayed"},
            ]

            # Add object setup if feature requires it
            if self.rules.requires_object_interaction(feature_name):
                steps.extend([
                    {"action": "Create a new drawing.", "expected": ""},
                    {"action": "Draw a shape on the Canvas using touch.", "expected": ""},
                    {"action": "Select the drawn object.", "expected": ""},
                ])

            steps.extend([
                {"action": f"Navigate to {entry_point} using touch.", "expected": ""},
                {"action": f"Perform the {feature_name} action using touch gestures.", "expected": ""},
                {"action": f"Verify the {feature_name} functionality works correctly with touch input.",
                 "expected": f"{feature_name} works correctly with touch interaction."},
                {"action": "Close the ENV QuickDraw App", "expected": ""}
            ])
            objective = f"Verify that <b>{feature_name}</b> works correctly on <b>tablets</b> using <b>touch or stylus</b>"
            platform_tests.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        return platform_tests

    def _generate_accessibility_tests(self, story_id: str, feature_name: str, story_data: Dict, qa_details: Dict) -> List[Dict]:
        """Generate device-specific accessibility tests - GENERIC for any feature."""
        accessibility_tests = []
        platforms = qa_details.get('platforms', [])
        entry_point = self._determine_entry_point(feature_name, qa_details.get('entry_points', []))

        # Windows 11 accessibility test
        if 'Windows 11' in platforms:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += 5

            title = f"{test_id}: {feature_name} / Accessibility / Keyboard navigation and labels (Windows 11)"
            steps = [
                {"action": "Pre-req: The ENV QuickDraw App is installed", "expected": ""},
                {"action": "Pre-req: Accessibility Insights for Windows tool is installed", "expected": ""},
                {"action": "Launch the ENV QuickDraw application.", "expected": "Model space(Gray) and Canvas(white) space should be displayed"},
                {"action": f"Navigate to {entry_point} using keyboard.", "expected": ""},
                {"action": f"Verify the {feature_name} controls are reachable by keyboard and focus is clearly visible.",
                 "expected": f"Keyboard focus moves to the {feature_name} controls with a visible focus indicator."},
                {"action": f"Verify {feature_name} controls expose meaningful labels and roles in Accessibility Insights.",
                 "expected": "Controls expose correct accessible name and role."},
                {"action": "Close the ENV QuickDraw App", "expected": ""}
            ]
            objective = f"Verify that <b>{feature_name}</b> controls meet <b>WCAG 2.1 AA</b> standards on <b>Windows 11</b>, with keyboard accessibility and correct labels/roles"
            accessibility_tests.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        # iPad accessibility test
        if 'iPad' in platforms:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += 5

            title = f"{test_id}: {feature_name} / Accessibility / VoiceOver navigation and labels (iPad)"
            steps = [
                {"action": "Pre-req: The ENV QuickDraw App is installed", "expected": ""},
                {"action": "Pre-req: VoiceOver is enabled on the iPad", "expected": ""},
                {"action": "Launch the ENV QuickDraw application.", "expected": "Model space(Gray) and Canvas(white) space should be displayed"},
                {"action": "Enable VoiceOver.", "expected": ""},
                {"action": f"Navigate to {entry_point} using VoiceOver swipe gestures.", "expected": ""},
                {"action": f"Verify the {feature_name} controls are announced with meaningful labels and correct roles.",
                 "expected": f"VoiceOver announces the {feature_name} controls with meaningful labels and roles."},
                {"action": "Verify reading order is logical.",
                 "expected": "VoiceOver announces controls in a logical order."},
                {"action": "Close the ENV QuickDraw App", "expected": ""}
            ]
            objective = f"Verify that <b>{feature_name}</b> controls are accessible via <b>VoiceOver on iPad</b>, with logical reading order and meaningful labels"
            accessibility_tests.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        # Android Tablet accessibility test
        if 'Android Tablet' in platforms:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += 5

            title = f"{test_id}: {feature_name} / Accessibility / Accessibility Scanner validation (Android Tablet)"
            steps = [
                {"action": "Pre-req: The ENV QuickDraw App is installed", "expected": ""},
                {"action": "Pre-req: Accessibility Scanner for Android is installed", "expected": ""},
                {"action": "Launch the ENV QuickDraw application.", "expected": "Model space(Gray) and Canvas(white) space should be displayed"},
                {"action": f"Navigate to {entry_point}.", "expected": ""},
                {"action": f"Run Accessibility Scanner on the {feature_name} controls.", "expected": ""},
                {"action": f"Verify Accessibility Scanner reports readable labels and appropriate roles for {feature_name} controls.",
                 "expected": "Controls have readable labels and appropriate roles with no critical scanner issues."},
                {"action": "Close the ENV QuickDraw App", "expected": ""}
            ]
            objective = f"Verify that <b>{feature_name}</b> controls meet accessibility standards on <b>Android Tablet</b> using <b>Accessibility Scanner</b>"
            accessibility_tests.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        return accessibility_tests
