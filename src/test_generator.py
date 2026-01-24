"""
Generic Rule-Based Test Case Generator
Generates comprehensive test cases following all quality rules with full edge case coverage.
"""
from typing import List, Dict, Optional, Set
import re
from src.test_rules import TestRules
import config


class TestGenerator:
    """Generic test case generator using rule-based templates with comprehensive coverage."""
    
    def __init__(self):
        self.rules = TestRules()
        self.test_id_counter = 5  # Start at AC1, then 005, 010, 015...

    def generate_test_cases(self, story_data: Dict, criteria: List[str], qa_prep_content: Optional[str] = None) -> List[Dict]:
        """
        Generate comprehensive test cases from story data, acceptance criteria, and QA prep.
        
        Args:
            story_data: Dict with 'story_id', 'title', 'description_text', 'acceptance_criteria_text', 'qa_prep_text'
            criteria: List of acceptance criteria bullets (parsed and ordered)
            qa_prep_content: Optional QA prep content for coverage expansion
            
        Returns:
            List of test case dicts with 'id', 'title', 'steps', 'objective'
        """
        test_cases = []
        story_id = story_data.get('story_id') or story_data.get('id')
        if not story_id:
            raise ValueError("story_data must contain 'story_id' or 'id'")
        feature_name = self.rules.extract_feature_name(story_data.get('title', ''))
        
        # Parse QA Prep for edge cases and coverage dimensions
        qa_details = self._parse_qa_prep(qa_prep_content) if qa_prep_content else {}
        
        # Step 1: Generate primary tests from AC bullets
        for idx, ac_bullet in enumerate(criteria):
            # Skip cancelled AC
            if self.rules.is_cancelled(ac_bullet):
                print(f"  ⚠ Skipping cancelled AC{idx + 1}: {ac_bullet[:50]}...")
                continue

            # Generate test case ID
            if idx == 0:
                test_id = f"{story_id}-AC1"
            else:
                test_id = f"{story_id}-{self.test_id_counter:03d}"
                self.test_id_counter += 5

            # Generate primary test case for this AC
            test_case = self._generate_test_from_ac(
                test_id=test_id,
                ac_bullet=ac_bullet,
                ac_index=idx + 1,
                feature_name=feature_name,
                story_data=story_data,
                qa_prep=qa_prep_content,
                qa_details=qa_details
            )

            if test_case:
                test_cases.append(test_case)
        
        # Step 2: Generate deterministic edge case tests (conditional expansion)
        # Only expand if AC or QA Prep explicitly mentions the scenario
        edge_case_tests = self._generate_deterministic_edge_cases(
            story_id, feature_name, story_data, qa_details, criteria
        )
        test_cases.extend(edge_case_tests)
        
        # Step 3: Generate accessibility tests (only if AC or QA Prep requires it)
        if qa_details.get('accessibility_requirements') or any('accessibility' in ac.lower() or 'keyboard' in ac.lower() 
                                                               for ac in criteria):
            accessibility_tests = self._generate_accessibility_tests(story_id, feature_name, story_data, qa_details)
            test_cases.extend(accessibility_tests)

        # Step 9: Post-process all test cases to fix validation issues
        test_cases = self._post_process_test_cases(test_cases)
        
        # Step 10: Quality Gates - Fail Fast on violations
        quality_gate_result = self._run_quality_gates(test_cases, criteria, qa_details)
        if not quality_gate_result['is_valid']:
            print("\n✗ QUALITY GATE FAILED:")
            for error in quality_gate_result['errors']:
                print(f"  ✗ {error}")
            print("\n✗ ERROR: Cannot proceed with invalid test cases.")
            raise ValueError("Quality gate validation failed")
        
        # Step 11: Print coverage summary
        self._print_coverage_summary(test_cases, criteria, qa_details, quality_gate_result['coverage'])

        print(f"  Generated {len(test_cases)} test cases from {len(criteria)} AC bullets (including edge cases)")
        return test_cases

    def _parse_qa_prep(self, qa_prep: str) -> Dict:
        """Parse QA Prep to extract structured information for edge case generation."""
        details = {
            'entry_points': [],
            'platforms': [],
            'object_types': set(),
            'boundaries': [],
            'negative_scenarios': [],
            'undo_redo_actions': [],
            'integration_scenarios': [],
            'isolation_scenarios': [],
            'accessibility_requirements': []
        }
        
        if not qa_prep:
            return details
        
        qa_lower = qa_prep.lower()
        
        # Extract entry points
        entry_point_patterns = [
            (r'tools\s+menu', 'Tools Menu'),
            (r'edit\s+menu', 'Edit Menu'),
            (r'file\s+menu', 'File Menu'),
            (r'help\s+menu', 'Help Menu'),
            (r'properties\s+(?:panel|design)', 'Properties Panel'),
            (r'dimensions\s+(?:menu|panel)', 'Dimensions Menu'),
            (r'canvas', 'Canvas'),
            (r'toolbar', 'Toolbar')
        ]
        for pattern, entry_point in entry_point_patterns:
            if re.search(pattern, qa_lower):
                if entry_point not in details['entry_points']:
                    details['entry_points'].append(entry_point)
        
        # Extract platforms
        if 'windows' in qa_lower or 'win11' in qa_lower:
            details['platforms'].append('Windows 11')
        if 'ipad' in qa_lower:
            details['platforms'].append('iPad')
        if 'android' in qa_lower or 'tablet' in qa_lower:
            details['platforms'].append('Android Tablet')
        
        # Extract object types mentioned
        object_types = ['rectangle', 'circle', 'line', 'arrow', 'text', 'annotation', 'triangle', 'polygon', 'ellipse']
        for obj_type in object_types:
            if obj_type in qa_lower:
                details['object_types'].add(obj_type.capitalize())
        
        # Extract boundary conditions
        if re.search(r'\b(360|0)\s*deg', qa_lower):
            details['boundaries'].append('rotation_range')
        if 'wrap' in qa_lower or 'wrap-around' in qa_lower:
            details['boundaries'].append('wrap_around')
        if 'boundary' in qa_lower:
            details['boundaries'].append('boundary')
        
        # Extract angle feedback scenarios
        if 'angle' in qa_lower and ('feedback' in qa_lower or 'display' in qa_lower or 'cursor' in qa_lower):
            details['boundaries'].append('angle_feedback')
        
        # Extract shift key locking scenarios
        if 'shift' in qa_lower and ('increment' in qa_lower or '15' in qa_lower or 'step' in qa_lower):
            details['boundaries'].append('shift_locking')
        
        # Extract negative scenarios
        if 'no selection' in qa_lower or 'without selection' in qa_lower:
            details['negative_scenarios'].append('no_selection')
        if 'empty canvas' in qa_lower or 'no objects' in qa_lower:
            details['negative_scenarios'].append('empty_canvas')
        
        # Extract undo/redo mentions
        if 'undo' in qa_lower or 'redo' in qa_lower:
            details['undo_redo_actions'].append('general')
        
        # Extract integration scenarios
        if 'multiple' in qa_lower and ('rotation' in qa_lower or 'operation' in qa_lower):
            details['integration_scenarios'].append('multiple_operations')
        if 'switch' in qa_lower and 'tool' in qa_lower:
            details['integration_scenarios'].append('tool_switching')
        if 'after moving' in qa_lower or 'after move' in qa_lower:
            details['integration_scenarios'].append('after_move')
        
        # Extract isolation scenarios
        if 'only selected' in qa_lower or 'selected object' in qa_lower:
            details['isolation_scenarios'].append('only_selected')
        if 'layout' in qa_lower or 'alignment' in qa_lower:
            details['isolation_scenarios'].append('layout_isolation')
        
        # Extract accessibility requirements
        if 'keyboard' in qa_lower or 'accessibility' in qa_lower:
            details['accessibility_requirements'].append('keyboard_navigation')
        if 'voiceover' in qa_lower or 'screen reader' in qa_lower:
            details['accessibility_requirements'].append('screen_reader')
        if 'contrast' in qa_lower:
            details['accessibility_requirements'].append('contrast')
        if 'focus' in qa_lower or 'focus indicator' in qa_lower:
            details['accessibility_requirements'].append('focus_indicators')
        if 'label' in qa_lower and ('role' in qa_lower or 'accessible' in qa_lower):
            details['accessibility_requirements'].append('labels_roles')
        
        return details

    def _generate_test_from_ac(self, test_id: str, ac_bullet: str, ac_index: int,
                                 feature_name: str, story_data: Dict, qa_prep: Optional[str],
                                 qa_details: Dict) -> Optional[Dict]:
        """Generate a single test case from an AC bullet."""
        steps = []
        title = ""
        objective = ""

        # Check if this requires object interaction
        requires_object = self.rules.requires_object_interaction(ac_bullet)

        # AC1 is always availability/entry point test
        if test_id.endswith("-AC1") or ac_index == 1:
            title, steps, objective = self._generate_availability_test(feature_name, ac_bullet, story_data, qa_details)
        # Check for undo/redo pattern
        elif 'undo' in ac_bullet.lower() or 'redo' in ac_bullet.lower():
            title, steps, objective = self._generate_undo_redo_test(feature_name, ac_bullet, requires_object)
        # Check for add/remove pattern
        elif any(word in ac_bullet.lower() for word in ['add', 'remove', 'enable', 'disable', 'toggle']):
            title, steps, objective = self._generate_add_remove_test(feature_name, ac_bullet, requires_object)
        # Check for accessibility
        elif 'accessibility' in ac_bullet.lower() or 'keyboard' in ac_bullet.lower() or 'wcag' in ac_bullet.lower():
            title, steps, objective = self._generate_accessibility_test(feature_name, ac_bullet, story_data)
        # Generic behavior test
        else:
            title, steps, objective = self._generate_behavior_test(feature_name, ac_bullet, requires_object, qa_details)

        # Add mandatory PRE-REQ and Close steps
        steps = self._add_mandatory_steps(steps)

        # Add test_id prefix to title (if not already there)
        if not title.startswith(test_id):
            title = f"{test_id}: {title}"

        # Clean forbidden words
        title = self.rules.clean_forbidden_words(title)
        objective = self.rules.clean_forbidden_words(objective)

        return {
            'id': test_id,
            'title': title,
            'steps': steps,
            'objective': objective,
            'requires_object': requires_object,
            'source_ac_id': f"AC{ac_index}"  # Tag primary test with AC number
        }

    def _generate_availability_test(self, feature_name: str, ac_bullet: str, story_data: Dict, qa_details: Dict) -> tuple:
        """Generate AC1 availability/entry point test."""
        # Extract entry point from AC, QA Prep, or default
        entry_point = self._extract_entry_point(ac_bullet, story_data)
        if qa_details.get('entry_points'):
            entry_point = qa_details['entry_points'][0]

        title = f"{feature_name} / {entry_point} / Available and Accessible"

        steps = [
            {"action": "Launch ENV QuickDraw application.", "expected": ""},
            {"action": f"Open {entry_point}.", "expected": f"{entry_point} opens and is displayed."},
            {"action": f"Verify that {feature_name} is available and can be activated.", "expected": f"{feature_name} is visible and can be activated from {entry_point}."}
        ]

        objective = f"Verify that <b>{feature_name}</b> is available and accessible from <b>{entry_point}</b>"

        return title, steps, objective

    def _generate_undo_redo_test(self, feature_name: str, ac_bullet: str, requires_object: bool) -> tuple:
        """Generate comprehensive Undo/Redo test."""
        action = self._extract_action_from_ac(ac_bullet)
        title = f"Undo Redo / Canvas / {action}"

        steps = []
        if requires_object:
            steps.extend(self.rules.get_object_setup_steps())

        post_state = f"{action} is applied"
        pre_state = f"{action} is reverted"
        steps.extend(self.rules.get_undo_redo_steps(
            action_description=f"Perform {action}.",
            post_state=post_state,
            pre_state=pre_state
        ))

        objective = f"Verify that <b>Undo</b> and <b>Redo</b> operations correctly reverse and restore <b>{action}</b> on the Canvas"

        return title, steps, objective

    def _generate_add_remove_test(self, feature_name: str, ac_bullet: str, requires_object: bool) -> tuple:
        """Generate Add/Remove pattern test."""
        action = self._extract_action_from_ac(ac_bullet)
        entry_point = self._extract_entry_point(ac_bullet, {})
        title = f"{feature_name} / {entry_point} / Add Remove"

        steps = []
        if requires_object:
            steps.extend(self.rules.get_object_setup_steps())

        added_element = self._extract_added_element(ac_bullet)
        steps.extend(self.rules.get_add_remove_steps(
            add_action=f"Enable {feature_name} from {entry_point}.",
            added_state=f"{added_element} appears",
            remove_action=f"Disable {feature_name} from {entry_point}."
        ))

        objective = f"Verify that <b>{feature_name}</b> can be added and removed via <b>{entry_point}</b>, with no stale artifacts remaining"

        return title, steps, objective

    def _generate_behavior_test(self, feature_name: str, ac_bullet: str, requires_object: bool, qa_details: Dict) -> tuple:
        """Generate generic behavior test."""
        action = self._extract_action_from_ac(ac_bullet)
        entry_point = self._extract_entry_point(ac_bullet, {})
        expected_outcome = self._extract_expected_outcome(ac_bullet)

        # Extract scenario from AC
        scenario = self._extract_scenario(ac_bullet)
        title = f"{feature_name} / {entry_point} / {scenario}"

        steps = []
        if requires_object:
            steps.extend(self.rules.get_object_setup_steps())

        steps.append({"action": f"Perform {action} via {entry_point}.", "expected": ""})
        steps.append({"action": f"Verify that {expected_outcome.lower()}.", "expected": expected_outcome})

        objective = f"Verify that <b>{action}</b> via <b>{entry_point}</b> produces the expected outcome: {expected_outcome}"

        return title, steps, objective

    def _generate_accessibility_test(self, feature_name: str, ac_bullet: str, story_data: Dict) -> tuple:
        """Generate device-specific accessibility test."""
        device = "Windows 11"
        title = f"{feature_name} / Accessibility / Keyboard Navigation ({device})"

        steps = [
            {"action": f"Launch Accessibility Insights for Windows and connect to the application.", "expected": ""},
            {"action": "Navigate through all interactive elements using Tab key.", "expected": ""},
            {"action": "Verify that all elements are keyboard accessible with visible focus indicators.", "expected": "All elements are keyboard accessible with visible focus"}
        ]

        objective = f"Verify that <b>{feature_name}</b> meets <b>WCAG 2.1 AA</b> standards on <b>{device}</b>, with keyboard navigation and visible focus indicators"

        return title, steps, objective

    def _generate_edge_case_tests(self, story_id: int, feature_name: str, story_data: Dict, 
                                   qa_details: Dict, criteria: List[str]) -> List[Dict]:
        """Generate edge case tests from QA Prep."""
        tests = []
        
        # Negative scenario: No selection
        if 'no_selection' in qa_details.get('negative_scenarios', []):
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += 5
            
            entry_point = qa_details.get('entry_points', ['Tools Menu'])[0] if qa_details.get('entry_points') else 'Tools Menu'
            
            title = f"{feature_name} / {entry_point} / Rotation marker not visible when no object selected"
            steps = [
                {"action": "Launch ENV QuickDraw application.", "expected": ""},
                {"action": f"Activate {feature_name} without selecting any object.", "expected": ""},
                {"action": "Verify that rotation marker is not visible when no object is selected.", "expected": "No rotation marker is displayed on the Canvas."}
            ]
            steps = self._add_mandatory_steps(steps)
            
            objective = f"Verify that <b>{feature_name}</b> is not visible when no object is selected."
            
            tests.append({
                'id': test_id,
                'title': f"{test_id}: {title}",
                'steps': steps,
                'objective': objective,
                'requires_object': False
            })
        
        return tests
    
    def _generate_deterministic_edge_cases(self, story_id: int, feature_name: str, story_data: Dict,
                                          qa_details: Dict, criteria: List[str]) -> List[Dict]:
        """
        Generate deterministic edge cases based on AC and QA Prep content.
        Only expands coverage when explicitly mentioned in AC or QA Prep.
        
        Rules:
        1. State-Based Expansion: Only if AC mentions state dependencies
        2. Boundary Expansion: Only if AC mentions numeric values/ranges
        3. Visibility/Toggle Expansion: Only if AC mentions show/hide/toggle
        4. Undo/Redo Expansion: Only if AC or QA Prep mentions undo/redo
        5. Constraint Validation: Only if AC or QA Prep enforces restrictions
        """
        tests = []
        all_ac_text = ' '.join(criteria).lower()
        
        # 1. State-Based Expansion: Negative states (only if dependency implied)
        negative_scenarios = qa_details.get('negative_scenarios', [])
        if 'no_selection' in negative_scenarios or 'no selection' in all_ac_text:
            tests.extend(self._generate_state_negative_tests(story_id, feature_name, story_data, qa_details))
        
        # 2. Boundary Expansion: Only if AC mentions numeric values/ranges/angles
        boundaries = qa_details.get('boundaries', [])
        if boundaries or any(keyword in all_ac_text for keyword in ['360', '0 degree', 'angle', 'range', 'increment']):
            tests.extend(self._generate_boundary_tests(story_id, feature_name, story_data, qa_details, criteria))
        
        # 3. Visibility/Toggle Expansion: Only if AC mentions show/hide/toggle
        if any(keyword in all_ac_text for keyword in ['visible', 'hidden', 'show', 'hide', 'toggle', 'display']):
            tests.extend(self._generate_visibility_tests(story_id, feature_name, story_data, qa_details, criteria))
        
        # 4. Object-Specific Tests: Only if QA Prep mentions specific object types
        object_types = qa_details.get('object_types', set())
        if object_types:
            tests.extend(self._generate_object_specific_tests(story_id, feature_name, story_data, qa_details))
        
        # 5. Integration Tests: Only if QA Prep mentions integration scenarios
        integration_scenarios = qa_details.get('integration_scenarios', [])
        if integration_scenarios:
            tests.extend(self._generate_integration_tests(story_id, feature_name, story_data, qa_details))
        
        # 6. Isolation Tests: Only if QA Prep mentions isolation scenarios
        isolation_scenarios = qa_details.get('isolation_scenarios', [])
        if isolation_scenarios:
            tests.extend(self._generate_isolation_tests(story_id, feature_name, story_data, qa_details))
        
        # 7. Undo/Redo Expansion: Only if AC or QA Prep explicitly mentions it
        undo_redo_actions = qa_details.get('undo_redo_actions', [])
        if undo_redo_actions or any(keyword in all_ac_text for keyword in ['undo', 'redo']):
            tests.extend(self._generate_undo_redo_tests(story_id, feature_name, story_data, qa_details, criteria))
        
        # 8. Constraint Validation: Only if AC or QA Prep enforces restrictions
        if any(keyword in all_ac_text for keyword in ['cannot', 'prevent', 'restrict', 'constraint', 'not allowed']):
            tests.extend(self._generate_constraint_tests(story_id, feature_name, story_data, qa_details, criteria))
        
        return tests
    
    def _generate_state_negative_tests(self, story_id: int, feature_name: str, story_data: Dict,
                                       qa_details: Dict) -> List[Dict]:
        """Generate state-based negative tests (no selection, wrong object type, etc.)."""
        tests = []
        negative_scenarios = qa_details.get('negative_scenarios', [])
        entry_point = qa_details.get('entry_points', ['Tools Menu'])[0] if qa_details.get('entry_points') else 'Tools Menu'
        
        # No selection scenario
        if 'no_selection' in negative_scenarios:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += 5
            
            title = f"{feature_name} / {entry_point} / Rotation marker not visible when no object selected"
            steps = [
                {"action": "Launch ENV QuickDraw application.", "expected": ""},
                {"action": f"Activate {feature_name} without selecting any object.", "expected": ""},
                {"action": "Verify that rotation marker is not visible when no object is selected.", "expected": "No rotation marker is displayed on the Canvas."}
            ]
            steps = self._add_mandatory_steps(steps)
            
            objective = f"Verify that <b>{feature_name}</b> is not visible when no object is selected."
            
            tests.append({
                'id': test_id,
                'title': f"{test_id}: {title}",
                'steps': steps,
                'objective': objective,
                'requires_object': False,
                'edge_category': 'negative'
            })
        
        return tests
    
    def _generate_visibility_tests(self, story_id: int, feature_name: str, story_data: Dict,
                                   qa_details: Dict, criteria: List[str]) -> List[Dict]:
        """Generate visibility/toggle tests (show/hide, toggle ON/OFF)."""
        tests = []
        # Visibility is typically covered in primary AC tests
        # Additional visibility edge cases can be added here if QA Prep explicitly requests them
        return tests
    
    def _generate_constraint_tests(self, story_id: int, feature_name: str, story_data: Dict,
                                  qa_details: Dict, criteria: List[str]) -> List[Dict]:
        """Generate constraint validation tests (attempt forbidden action, verify prevention)."""
        tests = []
        # Constraints are typically validated in primary AC tests
        # Additional constraint tests can be added here if QA Prep explicitly requests them
        return tests

    def _generate_object_specific_tests(self, story_id: int, feature_name: str, story_data: Dict, 
                                        qa_details: Dict) -> List[Dict]:
        """Generate object-specific tests for each object type mentioned."""
        tests = []
        object_types = qa_details.get('object_types', set())
        
        if not object_types:
            return tests
        
        entry_point = qa_details.get('entry_points', ['Tools Menu'])[0] if qa_details.get('entry_points') else 'Tools Menu'
        action_type = self._extract_action_type(feature_name)
        
        for obj_type in object_types:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += 5
            
            title = f"{feature_name} / Canvas / Rotate {obj_type} object maintaining geometry and proportions"
            steps = [
                {"action": "Launch ENV QuickDraw application.", "expected": ""},
                {"action": f"Draw a {obj_type} on the Canvas.", "expected": f"{obj_type} is drawn on the Canvas."},
                {"action": f"Select the {obj_type}.", "expected": f"{obj_type} is selected on the Canvas."},
                {"action": f"Activate {feature_name}.", "expected": f"{feature_name} is activated and rotation marker appears."},
                {"action": f"Click and drag the rotation marker to rotate the {obj_type} by approximately 45 degrees.", "expected": f"{obj_type} rotates by approximately 45 degrees."},
                {"action": f"Verify that {obj_type} object geometry and proportions remain intact during rotation.", "expected": f"{obj_type} maintains its geometry and proportions after rotation."},
                {"action": f"Verify that pivot behavior is correct for {obj_type} object.", "expected": f"{obj_type} rotates around the correct pivot point."}
            ]
            steps = self._add_mandatory_steps(steps)
            
            objective = f"Verify that <b>{obj_type} object</b> maintains its geometry and proportions when using <b>{feature_name}</b>."
            
            tests.append({
                'id': test_id,
                'title': f"{test_id}: {title}",
                'steps': steps,
                'objective': objective,
                'requires_object': True
            })
        
        return tests

    def _generate_boundary_tests(self, story_id: int, feature_name: str, story_data: Dict,
                                  qa_details: Dict, criteria: List[str]) -> List[Dict]:
        """Generate boundary/constraint tests."""
        tests = []
        boundaries = qa_details.get('boundaries', [])
        
        entry_point = qa_details.get('entry_points', ['Canvas'])[0] if qa_details.get('entry_points') else 'Canvas'
        
        if 'rotation_range' in boundaries:
            # Full rotation range test
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += 5
            
            title = f"{feature_name} / {entry_point} / Full rotation range 0-360 degrees"
            steps = [
                {"action": "Launch ENV QuickDraw application.", "expected": ""},
                {"action": "Draw a shape (e.g. rectangle) on the Canvas.", "expected": ""},
                {"action": "Select the shape.", "expected": ""},
                {"action": f"Activate {feature_name}.", "expected": f"{feature_name} is activated and rotation marker appears."},
                {"action": "Click and drag the rotation marker to rotate the object through the full 0-360 degree range.", "expected": "Object rotates smoothly through the complete 0-360 degree range."},
                {"action": "Verify that rotation operates smoothly across the full rotation range.", "expected": "Rotation is smooth and continuous throughout the 0-360 degree range."}
            ]
            steps = self._add_mandatory_steps(steps)
            
            objective = f"Verify that <b>{feature_name}</b> operates smoothly across the full 0-360 degree range."
            tests.append({
                'id': test_id,
                'title': f"{test_id}: {title}",
                'steps': steps,
                'objective': objective,
                'requires_object': True
            })
            
            # Boundary at 0 degrees
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += 5
            
            title = f"{feature_name} / {entry_point} / Boundary position at 0 degrees"
            steps = [
                {"action": "Launch ENV QuickDraw application.", "expected": ""},
                {"action": "Draw a shape (e.g. rectangle) on the Canvas.", "expected": ""},
                {"action": "Select the shape.", "expected": ""},
                {"action": f"Activate {feature_name}.", "expected": f"{feature_name} is activated and rotation marker appears."},
                {"action": "Rotate the object to 0 degrees.", "expected": "Object is rotated to 0 degrees."},
                {"action": "Verify that rotation handles correctly at 0 degree boundary position.", "expected": "Object maintains correct orientation at 0 degrees without visual artifacts."}
            ]
            steps = self._add_mandatory_steps(steps)
            
            objective = f"Verify that <b>{feature_name}</b> handles correctly at 0 degree boundary position."
            tests.append({
                'id': test_id,
                'title': f"{test_id}: {title}",
                'steps': steps,
                'objective': objective,
                'requires_object': True
            })
            
            # Boundary near 360 degrees
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += 5
            
            title = f"{feature_name} / {entry_point} / Boundary position near 360 degrees"
            steps = [
                {"action": "Launch ENV QuickDraw application.", "expected": ""},
                {"action": "Draw a shape (e.g. rectangle) on the Canvas.", "expected": ""},
                {"action": "Select the shape.", "expected": ""},
                {"action": f"Activate {feature_name}.", "expected": f"{feature_name} is activated and rotation marker appears."},
                {"action": "Rotate the object to near 360 degrees (e.g., 359 degrees).", "expected": "Object is rotated to near 360 degrees."},
                {"action": "Verify that rotation handles correctly at near 360 degree boundary position.", "expected": "Object maintains correct orientation near 360 degrees without visual artifacts."}
            ]
            steps = self._add_mandatory_steps(steps)
            
            objective = f"Verify that <b>{feature_name}</b> handles correctly at near 360 degree boundary position."
            tests.append({
                'id': test_id,
                'title': f"{test_id}: {title}",
                'steps': steps,
                'objective': objective,
                'requires_object': True
            })
        
        if 'wrap_around' in boundaries:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += 5
            
            title = f"{feature_name} / {entry_point} / Wrap-around behavior from 360 to 0 degrees"
            steps = [
                {"action": "Launch ENV QuickDraw application.", "expected": ""},
                {"action": "Draw a shape (e.g. rectangle) on the Canvas.", "expected": ""},
                {"action": "Select the shape.", "expected": ""},
                {"action": f"Activate {feature_name}.", "expected": f"{feature_name} is activated and rotation marker appears."},
                {"action": "Rotate the object to 360 degrees.", "expected": "Object is rotated to 360 degrees."},
                {"action": "Continue rotating past 360 degrees.", "expected": ""},
                {"action": "Verify that wrap-around behavior occurs.", "expected": "Rotation wraps around smoothly from 360 degrees to 0 degrees without visual glitches."},
                {"action": "Verify that wrap-around behavior is smooth and predictable.", "expected": "Wrap-around from 360 to 0 degrees is smooth and maintains object integrity."}
            ]
            steps = self._add_mandatory_steps(steps)
            
            objective = f"Verify that <b>{feature_name}</b> wraps around correctly from 360 to 0 degrees."
            tests.append({
                'id': test_id,
                'title': f"{test_id}: {title}",
                'steps': steps,
                'objective': objective,
                'requires_object': True
            })
        
        # Angle feedback tests
        if 'angle_feedback' in boundaries:
            # Live rotation angle feedback test
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += 5
            
            title = f"{feature_name} / {entry_point} / Live rotation angle feedback displayed near cursor"
            steps = [
                {"action": "Launch ENV QuickDraw application.", "expected": ""},
                {"action": "Draw a shape (e.g. rectangle) on the Canvas.", "expected": ""},
                {"action": "Select the shape.", "expected": ""},
                {"action": f"Activate {feature_name}.", "expected": f"{feature_name} is activated and rotation marker appears."},
                {"action": "Click and drag the rotation marker to rotate the object.", "expected": ""},
                {"action": "Verify that rotation angle feedback is displayed near the cursor during interaction.", "expected": "Rotation angle feedback is displayed near the cursor during interaction."},
                {"action": "Verify that rotation angle values update consistently during the rotation gesture.", "expected": "Angle values update in real-time as the object rotates."},
                {"action": "Verify that angle feedback remains readable throughout the rotation gesture.", "expected": "Angle feedback text remains clear and readable during rotation."}
            ]
            steps = self._add_mandatory_steps(steps)
            
            objective = f"Verify that <b>rotation angle feedback</b> is displayed near the cursor and updates in real-time during rotation."
            tests.append({
                'id': test_id,
                'title': f"{test_id}: {title}",
                'steps': steps,
                'objective': objective,
                'requires_object': True
            })
            
            # Rotation angle feedback accuracy test
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += 5
            
            title = f"{feature_name} / {entry_point} / Rotation angle feedback accuracy"
            steps = [
                {"action": "Launch ENV QuickDraw application.", "expected": ""},
                {"action": "Draw a shape (e.g. rectangle) on the Canvas.", "expected": ""},
                {"action": "Select the shape.", "expected": ""},
                {"action": f"Activate {feature_name}.", "expected": f"{feature_name} is activated and rotation marker appears."},
                {"action": "Rotate the object to specific angles (e.g., 45°, 90°, 180°, 270°).", "expected": "Object rotates to the specified angles."},
                {"action": "Verify that displayed angle values match the actual rotation angles.", "expected": "Displayed angle values accurately reflect the actual object rotation."}
            ]
            steps = self._add_mandatory_steps(steps)
            
            objective = f"Verify that <b>displayed angle values</b> accurately match the actual rotation angles."
            tests.append({
                'id': test_id,
                'title': f"{test_id}: {title}",
                'steps': steps,
                'objective': objective,
                'requires_object': True
            })
        
        # Shift key locking tests
        if 'shift_locking' in boundaries:
            # Shift key locks rotation to 15 degree increments
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += 5
            
            title = f"{feature_name} / {entry_point} / Shift key locks rotation to 15 degree increments"
            steps = [
                {"action": "Launch ENV QuickDraw application.", "expected": ""},
                {"action": "Draw a shape (e.g. rectangle) on the Canvas.", "expected": ""},
                {"action": "Select the shape.", "expected": ""},
                {"action": f"Activate {feature_name}.", "expected": f"{feature_name} is activated and rotation marker appears."},
                {"action": "Hold Shift key and drag the rotation marker.", "expected": "Rotation locks to 15° incremental steps."},
                {"action": "Verify that rotation snaps to 15-degree increments when Shift key is held.", "expected": "Object rotates only in 15-degree increments (15°, 30°, 45°, 60°, etc.)."}
            ]
            steps = self._add_mandatory_steps(steps)
            
            objective = f"Verify that <b>Shift key</b> locks rotation to 15-degree increments."
            tests.append({
                'id': test_id,
                'title': f"{test_id}: {title}",
                'steps': steps,
                'objective': objective,
                'requires_object': True
            })
            
            # Shift key step locking consistent across multiple rotation directions
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += 5
            
            title = f"{feature_name} / {entry_point} / Shift key step locking consistent across multiple rotation directions"
            steps = [
                {"action": "Launch ENV QuickDraw application.", "expected": ""},
                {"action": "Draw a shape (e.g. rectangle) on the Canvas.", "expected": ""},
                {"action": "Select the shape.", "expected": ""},
                {"action": f"Activate {feature_name}.", "expected": f"{feature_name} is activated and rotation marker appears."},
                {"action": "Hold Shift key and rotate clockwise through multiple 15° increments.", "expected": "Rotation snaps to 15° increments in clockwise direction."},
                {"action": "Hold Shift key and rotate counter-clockwise through multiple 15° increments.", "expected": "Rotation snaps to 15° increments in counter-clockwise direction."},
                {"action": "Verify that 15° step locking is consistent across both rotation directions.", "expected": "15° step locking works consistently in both clockwise and counter-clockwise directions."}
            ]
            steps = self._add_mandatory_steps(steps)
            
            objective = f"Verify that <b>15° step locking</b> works consistently in both clockwise and counter-clockwise directions."
            tests.append({
                'id': test_id,
                'title': f"{test_id}: {title}",
                'steps': steps,
                'objective': objective,
                'requires_object': True
            })
            
            # Shift key step locking with repeated interactions
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += 5
            
            title = f"{feature_name} / {entry_point} / Shift key step locking with repeated interactions"
            steps = [
                {"action": "Launch ENV QuickDraw application.", "expected": ""},
                {"action": "Draw a shape (e.g. rectangle) on the Canvas.", "expected": ""},
                {"action": "Select the shape.", "expected": ""},
                {"action": f"Activate {feature_name}.", "expected": f"{feature_name} is activated and rotation marker appears."},
                {"action": "Perform multiple rotation interactions while holding Shift key.", "expected": "Each rotation interaction snaps to 15° increments."},
                {"action": "Verify that 15° step locking remains consistent across repeated interactions.", "expected": "15° step locking is consistent and reliable across all repeated interactions."}
            ]
            steps = self._add_mandatory_steps(steps)
            
            objective = f"Verify that <b>15° step locking</b> remains consistent across repeated interactions."
            tests.append({
                'id': test_id,
                'title': f"{test_id}: {title}",
                'steps': steps,
                'objective': objective,
                'requires_object': True
            })
        
        return tests

    def _generate_integration_tests(self, story_id: int, feature_name: str, story_data: Dict,
                                     qa_details: Dict) -> List[Dict]:
        """Generate integration tests (multiple operations, tool switching)."""
        tests = []
        scenarios = qa_details.get('integration_scenarios', [])
        
        entry_point = qa_details.get('entry_points', ['Tools Menu'])[0] if qa_details.get('entry_points') else 'Tools Menu'
        
        if 'multiple_operations' in scenarios:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += 5
            
            title = f"{feature_name} / {entry_point} / Multiple operations in succession"
            steps = [
                {"action": "Launch ENV QuickDraw application.", "expected": ""},
                {"action": "Draw a shape (e.g. rectangle) on the Canvas.", "expected": ""},
                {"action": "Select the shape.", "expected": ""},
                {"action": f"Activate {feature_name}.", "expected": ""},
                {"action": "Perform first rotation (e.g., 45 degrees).", "expected": ""},
                {"action": "Perform second rotation (e.g., additional 90 degrees).", "expected": ""},
                {"action": "Perform third rotation (e.g., additional 180 degrees).", "expected": ""},
                {"action": "Verify that multiple rotations in succession work correctly without cumulative errors.", "expected": "Object maintains correct orientation after multiple rotations."}
            ]
            steps = self._add_mandatory_steps(steps)
            
            objective = f"Verify that multiple <b>{feature_name}</b> operations in succession work correctly without cumulative errors."
            tests.append({
                'id': test_id,
                'title': f"{test_id}: {title}",
                'steps': steps,
                'objective': objective,
                'requires_object': True
            })
        
        if 'tool_switching' in scenarios:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += 5
            
            title = f"{feature_name} / {entry_point} / Tool remains active until another drawing tool is selected"
            steps = [
            {"action": "Launch ENV QuickDraw application.", "expected": ""},
                {"action": "Draw a shape (e.g. rectangle) on the Canvas.", "expected": ""},
                {"action": "Select the shape.", "expected": ""},
                {"action": f"Activate {feature_name}.", "expected": ""},
                {"action": "Rotate the object.", "expected": "Object rotates."},
                {"action": f"Verify that {feature_name} remains active.", "expected": f"{feature_name} remains active and rotation marker is still visible."},
                {"action": "Select another drawing tool (e.g., Draw Rectangle tool).", "expected": ""},
                {"action": f"Verify that {feature_name} is deactivated when another tool is selected.", "expected": f"{feature_name} is deactivated when another tool is selected."}
            ]
            steps = self._add_mandatory_steps(steps)
            
            objective = f"Verify that <b>{feature_name}</b> remains active until another drawing tool is selected."
            tests.append({
                'id': test_id,
                'title': f"{test_id}: {title}",
                'steps': steps,
                'objective': objective,
                'requires_object': True
            })
        
        if 'after_move' in scenarios:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += 5
            
            title = f"{feature_name} / Canvas / {feature_name} after moving an object"
            steps = [
                {"action": "Launch ENV QuickDraw application.", "expected": ""},
                {"action": "Draw a shape (e.g. rectangle) on the Canvas.", "expected": ""},
                {"action": "Select the shape.", "expected": ""},
                {"action": "Move the object to a new position.", "expected": "Object is moved to a new position."},
                {"action": f"Activate {feature_name}.", "expected": ""},
                {"action": f"Activate {feature_name}.", "expected": f"{feature_name} is activated and rotation marker appears."},
                {"action": "Rotate the object.", "expected": "Object rotates correctly."},
                {"action": f"Verify that rotation works correctly after moving the object.", "expected": f"Rotation operates correctly after object has been moved."}
            ]
            steps = self._add_mandatory_steps(steps)
            
            objective = f"Verify that <b>{feature_name}</b> works correctly after moving an object."
            tests.append({
                'id': test_id,
                'title': f"{test_id}: {title}",
                'steps': steps,
                'objective': objective,
                'requires_object': True
            })
        
        return tests

    def _generate_isolation_tests(self, story_id: int, feature_name: str, story_data: Dict,
                                   qa_details: Dict) -> List[Dict]:
        """Generate isolation tests (only selected object, doesn't affect layout)."""
        tests = []
        scenarios = qa_details.get('isolation_scenarios', [])
        
        entry_point = qa_details.get('entry_points', ['Canvas'])[0] if qa_details.get('entry_points') else 'Canvas'
        
        if 'only_selected' in scenarios:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += 5
            
            title = f"{feature_name} / {entry_point} / {feature_name} affects only selected object"
            steps = [
                {"action": "Launch ENV QuickDraw application.", "expected": ""},
                {"action": "Draw multiple shapes on the Canvas.", "expected": ""},
                {"action": "Select one shape.", "expected": "One shape is selected on the Canvas."},
                {"action": f"Activate {feature_name}.", "expected": f"{feature_name} is activated on selected object."},
                {"action": f"Activate {feature_name}.", "expected": f"{feature_name} is activated and rotation marker appears on selected object."},
                {"action": "Rotate the selected object.", "expected": "Selected object rotates."},
                {"action": "Verify that only the selected object rotates and other objects remain unchanged.", "expected": "Only the selected object rotates; other objects maintain their positions and orientations."}
            ]
            steps = self._add_mandatory_steps(steps)
            
            objective = f"Verify that <b>{feature_name}</b> affects only the selected object and other objects remain unchanged."
            tests.append({
                'id': test_id,
                'title': f"{test_id}: {title}",
                'steps': steps,
                'objective': objective,
                'requires_object': True
            })
        
        if 'layout_isolation' in scenarios:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += 5
            
            title = f"{feature_name} / {entry_point} / {feature_name} does not alter overall Canvas layout"
            steps = [
                {"action": "Launch ENV QuickDraw application.", "expected": ""},
                {"action": "Create a complex Canvas layout with multiple objects.", "expected": "Complex Canvas layout is created."},
                {"action": "Select one object.", "expected": "One object is selected."},
                {"action": f"Activate {feature_name}.", "expected": ""},
                {"action": f"Activate {feature_name}.", "expected": f"{feature_name} is activated and rotation marker appears."},
                {"action": "Rotate the selected object.", "expected": "Selected object rotates."},
                {"action": "Verify that overall Canvas layout remains unchanged.", "expected": "Overall Canvas layout is not altered by rotation of selected object."}
            ]
            steps = self._add_mandatory_steps(steps)
            
            objective = f"Verify that <b>{feature_name}</b> does not alter overall Canvas layout."
            tests.append({
                'id': test_id,
                'title': f"{test_id}: {title}",
                'steps': steps,
                'objective': objective,
                'requires_object': True
            })
        
        return tests

    def _generate_undo_redo_tests(self, story_id: int, feature_name: str, story_data: Dict,
                                   qa_details: Dict, criteria: List[str]) -> List[Dict]:
        """Generate comprehensive undo/redo tests."""
        tests = []
        
        if not qa_details.get('undo_redo_actions'):
            return tests
        
        entry_point = qa_details.get('entry_points', ['Canvas'])[0] if qa_details.get('entry_points') else 'Canvas'
        
        # Basic undo/redo test
        test_id = f"{story_id}-{self.test_id_counter:03d}"
        self.test_id_counter += 5
        
        title = f"{feature_name} / Canvas / Undo {feature_name} action restores object state"
        steps = [
            {"action": "Launch ENV QuickDraw application.", "expected": ""},
            {"action": "Draw a shape (e.g. rectangle) on the Canvas.", "expected": ""},
            {"action": "Select the shape.", "expected": ""},
            {"action": f"Activate {feature_name}.", "expected": f"{feature_name} is activated."},
            {"action": "Rotate the object by 45 degrees.", "expected": "Object is rotated by 45 degrees."},
            {"action": "Record the rotated orientation.", "expected": "Rotated orientation is recorded."},
            {"action": "Perform Undo action.", "expected": "Undo action is performed."},
            {"action": "Verify that object orientation is correctly restored to pre-rotation state.", "expected": "Object orientation is restored to its original state before rotation."},
            {"action": "Verify that visual state is correctly restored without UI artifacts.", "expected": "Object visual state is restored correctly without any UI artifacts."}
        ]
        steps = self._add_mandatory_steps(steps)
        
        objective = f"Verify that <b>Undo</b> action correctly restores object state after <b>{feature_name}</b> operation."
        tests.append({
            'id': test_id,
            'title': f"{test_id}: {title}",
            'steps': steps,
            'objective': objective,
            'requires_object': True
        })
        
        # Redo test
        test_id = f"{story_id}-{self.test_id_counter:03d}"
        self.test_id_counter += 5
        
        title = f"{feature_name} / Canvas / Redo {feature_name} action reapplies operation"
        steps = [
            {"action": "Launch ENV QuickDraw application.", "expected": ""},
            {"action": "Draw a shape (e.g. rectangle) on the Canvas.", "expected": ""},
            {"action": "Select the shape.", "expected": ""},
            {"action": f"Activate {feature_name}.", "expected": f"{feature_name} is activated."},
            {"action": "Rotate the object by 45 degrees.", "expected": "Object is rotated by 45 degrees."},
            {"action": "Perform Undo action.", "expected": "Rotation is undone."},
            {"action": "Perform Redo action.", "expected": "Redo action is performed."},
            {"action": "Verify that rotation is correctly reapplied.", "expected": "Object rotation is reapplied correctly."},
            {"action": "Verify that visual state is correctly reapplied without cumulative drift.", "expected": f"Object visual state is reapplied correctly without cumulative drift."}
        ]
        steps = self._add_mandatory_steps(steps)
        
        objective = f"Verify that <b>Redo</b> action correctly reapplies <b>{feature_name}</b> operation."
        tests.append({
            'id': test_id,
            'title': f"{test_id}: {title}",
            'steps': steps,
            'objective': objective,
            'requires_object': True
        })
        
        # Multiple undo/redo test
        test_id = f"{story_id}-{self.test_id_counter:03d}"
        self.test_id_counter += 5
        
        title = f"{feature_name} / Canvas / Multiple undo and redo operations without cumulative drift"
        steps = [
            {"action": "Launch ENV QuickDraw application.", "expected": ""},
            {"action": "Draw a shape (e.g. rectangle) on the Canvas.", "expected": ""},
            {"action": "Select the shape.", "expected": ""},
            {"action": f"Activate {feature_name}.", "expected": f"{feature_name} is activated."},
            {"action": "Perform multiple rotations (e.g., 45°, then 90°, then 180°).", "expected": ""},
            {"action": "Perform multiple Undo operations.", "expected": ""},
            {"action": "Perform multiple Redo operations.", "expected": ""},
            {"action": "Verify that object orientation is correctly restored and reapplied without cumulative drift.", "expected": "Object orientation is correctly restored and reapplied without cumulative drift."}
        ]
        steps = self._add_mandatory_steps(steps)
        
        objective = f"Verify that multiple <b>Undo</b> and <b>Redo</b> operations work correctly without cumulative drift."
        tests.append({
            'id': test_id,
            'title': f"{test_id}: {title}",
            'steps': steps,
            'objective': objective,
            'requires_object': True
        })
        
        return tests

    def _generate_accessibility_tests(self, story_id: int, feature_name: str, story_data: Dict,
                                       qa_details: Dict) -> List[Dict]:
        """Generate comprehensive accessibility tests for all platforms."""
        tests = []
        platforms = qa_details.get('platforms', ['Windows 11'])
        accessibility_reqs = qa_details.get('accessibility_requirements', [])
        
        entry_point = qa_details.get('entry_points', ['Tools Menu'])[0] if qa_details.get('entry_points') else 'Tools Menu'
        
        for platform in platforms:
            if platform == 'Windows 11':
                # Keyboard access test
                if 'keyboard_navigation' in accessibility_reqs:
                    test_id = f"{story_id}-{self.test_id_counter:03d}"
                    self.test_id_counter += 5
                    
                    title = f"{feature_name} / {entry_point} / Keyboard access to tool ({platform})"
                    steps = [
                        {"action": "PRE-REQ: Accessibility Insights for Windows tool is installed", "expected": ""},
                        {"action": "Launch ENV QuickDraw application on Windows 11.", "expected": ""},
                        {"action": f"Open {entry_point} using keyboard navigation.", "expected": f"{entry_point} opens and is displayed."},
                        {"action": f"Navigate to {feature_name} option using keyboard navigation.", "expected": f"{feature_name} option is reached using keyboard navigation."},
                        {"action": f"Activate {feature_name} using keyboard navigation.", "expected": ""},
                        {"action": f"Verify that keyboard access to the tool is fully functional.", "expected": f"{feature_name} can be accessed and activated using keyboard only."}
                    ]
                    steps = self._add_mandatory_steps(steps)
                    
                    objective = f"Verify that <b>{feature_name}</b> can be accessed and activated using keyboard only on <b>{platform}</b>."
                    tests.append({
                        'id': test_id,
                        'title': f"{test_id}: {title}",
                        'steps': steps,
                        'objective': objective,
                        'requires_object': False
                    })
                
                # Focus indicators test
                if 'focus_indicators' in accessibility_reqs:
                    test_id = f"{story_id}-{self.test_id_counter:03d}"
                    self.test_id_counter += 5
                    
                    title = f"{feature_name} / {entry_point} / Visible focus indicators ({platform})"
                    steps = [
                        {"action": "PRE-REQ: Accessibility Insights for Windows tool is installed", "expected": ""},
                        {"action": "Launch ENV QuickDraw application on Windows 11.", "expected": ""},
                        {"action": f"Open {entry_point} using keyboard navigation.", "expected": f"{entry_point} opens and is displayed."},
                        {"action": f"Navigate to {feature_name} option using keyboard navigation.", "expected": f"{feature_name} option is reached using keyboard navigation."},
                        {"action": f"Verify that visible focus indicators are present on {feature_name} option.", "expected": f"Visible focus indicators are displayed on {feature_name} option."},
                        {"action": f"Activate {feature_name}.", "expected": ""},
                        {"action": f"Verify that visible focus indicators are present on {feature_name} controls.", "expected": f"Visible focus indicators are displayed on {feature_name} controls."}
                    ]
                    steps = self._add_mandatory_steps(steps)
                    
                    objective = f"Verify that <b>{feature_name}</b> has visible focus indicators on <b>{platform}</b>."
                    tests.append({
                        'id': test_id,
                        'title': f"{test_id}: {title}",
                        'steps': steps,
                        'objective': objective,
                        'requires_object': False
                    })
                
                # Labels and roles test
                if 'labels_roles' in accessibility_reqs:
                    test_id = f"{story_id}-{self.test_id_counter:03d}"
                    self.test_id_counter += 5
                    
                    title = f"{feature_name} / {entry_point} / Meaningful labels and roles for tool control ({platform})"
                    steps = [
                        {"action": "PRE-REQ: Accessibility Insights for Windows tool is installed", "expected": ""},
                        {"action": "Launch ENV QuickDraw application on Windows 11.", "expected": ""},
                        {"action": f"Open {entry_point} using keyboard navigation.", "expected": f"{entry_point} opens and is displayed."},
                        {"action": f"Navigate to {feature_name} option using assistive technology.", "expected": f"{feature_name} option is reached using assistive technology."},
                        {"action": f"Verify that {feature_name} option has meaningful label.", "expected": f"{feature_name} option has meaningful and descriptive label."},
                        {"action": f"Verify that {feature_name} option has correct control role.", "expected": f"{feature_name} option control role is exposed as a button."},
                        {"action": f"Activate {feature_name}.", "expected": ""},
                        {"action": f"Verify that {feature_name} controls have meaningful labels and roles.", "expected": f"{feature_name} controls have meaningful labels and correct roles for assistive technologies."}
                    ]
                    steps = self._add_mandatory_steps(steps)
                    
                    objective = f"Verify that <b>{feature_name}</b> has meaningful labels and roles for assistive technologies on <b>{platform}</b>."
                    tests.append({
                        'id': test_id,
                        'title': f"{test_id}: {title}",
                        'steps': steps,
                        'objective': objective,
                        'requires_object': False
                    })
                
                # Contrast test
                if 'contrast' in accessibility_reqs:
                    test_id = f"{story_id}-{self.test_id_counter:03d}"
                    self.test_id_counter += 5
                    
                    title = f"{feature_name} / Canvas / Sufficient contrast for controls and feedback ({platform})"
                    steps = [
                        {"action": "PRE-REQ: Accessibility Insights for Windows tool is installed", "expected": ""},
                        {"action": "Launch ENV QuickDraw application on Windows 11.", "expected": ""},
                        {"action": "Draw a shape (e.g. rectangle) on the Canvas.", "expected": ""},
                        {"action": "Select the shape.", "expected": ""},
                        {"action": f"Activate {feature_name}.", "expected": ""},
                        {"action": "Click and drag the rotation marker to rotate the object.", "expected": ""},
                        {"action": "Verify that rotation angle feedback is displayed near the cursor during interaction.", "expected": "Rotation angle feedback is displayed near the cursor during interaction."},
                        {"action": f"Verify that {feature_name} controls have sufficient contrast against Canvas background.", "expected": f"{feature_name} controls have sufficient contrast and are clearly visible."},
                        {"action": f"Verify that feedback text has sufficient contrast for readability.", "expected": "Feedback text has sufficient contrast and is clearly readable."}
                    ]
                    steps = self._add_mandatory_steps(steps)
                    
                    objective = f"Verify that <b>{feature_name}</b> controls and feedback have sufficient contrast on <b>{platform}</b>."
                    tests.append({
                        'id': test_id,
                        'title': f"{test_id}: {title}",
                        'steps': steps,
                        'objective': objective,
                        'requires_object': True
                    })
            
            elif platform == 'iPad':
                # Touch access with VoiceOver test
                if 'screen_reader' in accessibility_reqs:
                    test_id = f"{story_id}-{self.test_id_counter:03d}"
                    self.test_id_counter += 5
                    
                    title = f"{feature_name} / {entry_point} / Touch access with VoiceOver ({platform})"
                    steps = [
                        {"action": "PRE-REQ: Apple built-in accessibility tools are available and enabled (e.g., VoiceOver) is installed", "expected": ""},
                        {"action": "Launch ENV QuickDraw application on iPad.", "expected": ""},
                        {"action": f"Open {entry_point} using touch and VoiceOver.", "expected": f"{entry_point} opens and is displayed."},
                        {"action": f"Navigate to {feature_name} option using touch and VoiceOver.", "expected": f"{feature_name} option is reached using VoiceOver swipe gestures."},
                        {"action": f"Activate {feature_name} using touch and VoiceOver.", "expected": ""},
                        {"action": f"Verify that touch access with VoiceOver to the tool is fully functional.", "expected": f"{feature_name} can be accessed and activated using touch with VoiceOver."}
                    ]
                    steps = self._add_mandatory_steps(steps)
                    
                    objective = f"Verify that <b>{feature_name}</b> can be accessed and activated using touch with VoiceOver on <b>{platform}</b>."
                    tests.append({
                        'id': test_id,
                        'title': f"{test_id}: {title}",
                        'steps': steps,
                        'objective': objective,
                        'requires_object': False
                    })
                
                # Focus indicators for iPad
                if 'focus_indicators' in accessibility_reqs:
                    test_id = f"{story_id}-{self.test_id_counter:03d}"
                    self.test_id_counter += 5
                    
                    title = f"{feature_name} / {entry_point} / Visible focus indicators ({platform})"
                    steps = [
                        {"action": "PRE-REQ: Apple built-in accessibility tools are available and enabled (e.g., VoiceOver) is installed", "expected": ""},
                        {"action": "Launch ENV QuickDraw application on iPad.", "expected": ""},
                        {"action": f"Open {entry_point} using touch and VoiceOver.", "expected": f"{entry_point} opens and is displayed."},
                        {"action": f"Navigate to {feature_name} option using touch and VoiceOver.", "expected": f"{feature_name} option is reached using VoiceOver swipe gestures."},
                        {"action": f"Verify that visible focus indicators are present on {feature_name} option.", "expected": f"Visible focus indicators are displayed on {feature_name} option."},
                        {"action": f"Activate {feature_name}.", "expected": ""},
                        {"action": f"Verify that visible focus indicators are present on {feature_name} controls.", "expected": f"Visible focus indicators are displayed on {feature_name} controls."}
                    ]
                    steps = self._add_mandatory_steps(steps)
                    
                    objective = f"Verify that <b>{feature_name}</b> has visible focus indicators on <b>{platform}</b>."
                    tests.append({
                        'id': test_id,
                        'title': f"{test_id}: {title}",
                        'steps': steps,
                        'objective': objective,
                        'requires_object': False
                    })
                
                # Labels and roles for iPad
                if 'labels_roles' in accessibility_reqs:
                    test_id = f"{story_id}-{self.test_id_counter:03d}"
                    self.test_id_counter += 5
                    
                    title = f"{feature_name} / {entry_point} / Meaningful labels and roles for tool control ({platform})"
                    steps = [
                        {"action": "PRE-REQ: Apple built-in accessibility tools are available and enabled (e.g., VoiceOver) is installed", "expected": ""},
                        {"action": "Launch ENV QuickDraw application on iPad.", "expected": ""},
                        {"action": f"Open {entry_point} using touch and VoiceOver.", "expected": f"{entry_point} opens and is displayed."},
                        {"action": f"Navigate to {feature_name} option using assistive technology.", "expected": f"{feature_name} option is reached using assistive technology."},
                        {"action": f"Verify that {feature_name} option has meaningful label.", "expected": f"{feature_name} option has meaningful and descriptive label."},
                        {"action": f"Verify that {feature_name} option has correct control role.", "expected": f"{feature_name} option control role is exposed as a button."},
                        {"action": f"Activate {feature_name}.", "expected": ""},
                        {"action": f"Verify that {feature_name} controls have meaningful labels and roles.", "expected": f"{feature_name} controls have meaningful labels and correct roles for assistive technologies."}
                    ]
                    steps = self._add_mandatory_steps(steps)
                    
                    objective = f"Verify that <b>{feature_name}</b> has meaningful labels and roles for assistive technologies on <b>{platform}</b>."
                    tests.append({
                        'id': test_id,
                        'title': f"{test_id}: {title}",
                        'steps': steps,
                        'objective': objective,
                        'requires_object': False
                    })
                
                # Contrast for iPad
                if 'contrast' in accessibility_reqs:
                    test_id = f"{story_id}-{self.test_id_counter:03d}"
                    self.test_id_counter += 5
                    
                    title = f"{feature_name} / Canvas / Sufficient contrast for controls and feedback ({platform})"
                    steps = [
                        {"action": "PRE-REQ: Apple built-in accessibility tools are available and enabled (e.g., VoiceOver) is installed", "expected": ""},
                        {"action": "Launch ENV QuickDraw application on iPad.", "expected": ""},
                        {"action": "Draw a shape (e.g. rectangle) on the Canvas.", "expected": ""},
                        {"action": "Select the shape.", "expected": ""},
                        {"action": f"Activate {feature_name}.", "expected": ""},
                        {"action": "Click and drag the rotation marker to rotate the object.", "expected": ""},
                        {"action": "Verify that rotation angle feedback is displayed near the cursor during interaction.", "expected": "Rotation angle feedback is displayed near the cursor during interaction."},
                        {"action": f"Verify that {feature_name} controls have sufficient contrast against Canvas background.", "expected": f"{feature_name} controls have sufficient contrast and are clearly visible."},
                        {"action": f"Verify that feedback text has sufficient contrast for readability.", "expected": "Feedback text has sufficient contrast and is clearly readable."}
                    ]
                    steps = self._add_mandatory_steps(steps)
                    
                    objective = f"Verify that <b>{feature_name}</b> controls and feedback have sufficient contrast on <b>{platform}</b>."
                    tests.append({
                        'id': test_id,
                        'title': f"{test_id}: {title}",
                        'steps': steps,
                        'objective': objective,
                        'requires_object': True
                    })
            
            elif platform == 'Android Tablet':
                # Touch access test
                test_id = f"{story_id}-{self.test_id_counter:03d}"
                self.test_id_counter += 5
                
                title = f"{feature_name} / {entry_point} / Touch access ({platform})"
                steps = [
                    {"action": "PRE-REQ: Accessibility Scanner (Google) Free tool is installed", "expected": ""},
                    {"action": "Launch ENV QuickDraw application on Android Tablet.", "expected": ""},
                    {"action": f"Open {entry_point} using touch.", "expected": f"{entry_point} opens and is displayed."},
                    {"action": f"Navigate to {feature_name} option using touch.", "expected": f"{feature_name} option is reached using touch."},
                    {"action": f"Activate {feature_name} using touch.", "expected": ""},
                    {"action": f"Verify that touch access to the tool is fully functional.", "expected": f"{feature_name} can be accessed and activated using touch."}
                ]
                steps = self._add_mandatory_steps(steps)
                
                objective = f"Verify that <b>{feature_name}</b> can be accessed and activated using touch on <b>{platform}</b>."
                tests.append({
                    'id': test_id,
                    'title': f"{test_id}: {title}",
                    'steps': steps,
                    'objective': objective,
                    'requires_object': False
                })
                
                # Focus indicators for Android
                if 'focus_indicators' in accessibility_reqs:
                    test_id = f"{story_id}-{self.test_id_counter:03d}"
                    self.test_id_counter += 5
                    
                    title = f"{feature_name} / {entry_point} / Visible focus indicators ({platform})"
                    steps = [
                        {"action": "PRE-REQ: Accessibility Scanner (Google) Free tool is installed", "expected": ""},
                        {"action": "Launch ENV QuickDraw application on Android Tablet.", "expected": ""},
                        {"action": f"Open {entry_point} using touch.", "expected": f"{entry_point} opens and is displayed."},
                        {"action": f"Navigate to {feature_name} option using touch.", "expected": f"{feature_name} option is reached using touch."},
                        {"action": f"Verify that visible focus indicators are present on {feature_name} option.", "expected": f"Visible focus indicators are displayed on {feature_name} option."},
                        {"action": f"Activate {feature_name}.", "expected": ""},
                        {"action": f"Verify that visible focus indicators are present on {feature_name} controls.", "expected": f"Visible focus indicators are displayed on {feature_name} controls."}
                    ]
                    steps = self._add_mandatory_steps(steps)
                    
                    objective = f"Verify that <b>{feature_name}</b> has visible focus indicators on <b>{platform}</b>."
                    tests.append({
                        'id': test_id,
                        'title': f"{test_id}: {title}",
                        'steps': steps,
                        'objective': objective,
                        'requires_object': False
                    })
                
                # Labels and roles for Android
                if 'labels_roles' in accessibility_reqs:
                    test_id = f"{story_id}-{self.test_id_counter:03d}"
                    self.test_id_counter += 5
                    
                    title = f"{feature_name} / {entry_point} / Meaningful labels and roles for tool control ({platform})"
                    steps = [
                        {"action": "PRE-REQ: Accessibility Scanner (Google) Free tool is installed", "expected": ""},
                        {"action": "Launch ENV QuickDraw application on Android Tablet.", "expected": ""},
                        {"action": f"Open {entry_point} using touch.", "expected": f"{entry_point} opens and is displayed."},
                        {"action": f"Navigate to {feature_name} option using assistive technology.", "expected": f"{feature_name} option is reached using assistive technology."},
                        {"action": f"Verify that {feature_name} option has meaningful label.", "expected": f"{feature_name} option has meaningful and descriptive label."},
                        {"action": f"Verify that {feature_name} option has correct control role.", "expected": f"{feature_name} option control role is exposed as a button."},
                        {"action": f"Activate {feature_name}.", "expected": ""},
                        {"action": f"Verify that {feature_name} controls have meaningful labels and roles.", "expected": f"{feature_name} controls have meaningful labels and correct roles for assistive technologies."}
                    ]
                    steps = self._add_mandatory_steps(steps)
                    
                    objective = f"Verify that <b>{feature_name}</b> has meaningful labels and roles for assistive technologies on <b>{platform}</b>."
                    tests.append({
                        'id': test_id,
                        'title': f"{test_id}: {title}",
                        'steps': steps,
                        'objective': objective,
                        'requires_object': False
                    })
                
                # Contrast for Android
                if 'contrast' in accessibility_reqs:
                    test_id = f"{story_id}-{self.test_id_counter:03d}"
                    self.test_id_counter += 5
                    
                    title = f"{feature_name} / Canvas / Sufficient contrast for controls and feedback ({platform})"
                    steps = [
                        {"action": "PRE-REQ: Accessibility Scanner (Google) Free tool is installed", "expected": ""},
                        {"action": "Launch ENV QuickDraw application on Android Tablet.", "expected": ""},
                        {"action": "Draw a shape (e.g. rectangle) on the Canvas.", "expected": ""},
                        {"action": "Select the shape.", "expected": ""},
                        {"action": f"Activate {feature_name}.", "expected": ""},
                        {"action": "Click and drag the rotation marker to rotate the object.", "expected": ""},
                        {"action": "Verify that rotation angle feedback is displayed near the cursor during interaction.", "expected": "Rotation angle feedback is displayed near the cursor during interaction."},
                        {"action": f"Verify that {feature_name} controls have sufficient contrast against Canvas background.", "expected": f"{feature_name} controls have sufficient contrast and are clearly visible."},
                        {"action": f"Verify that feedback text has sufficient contrast for readability.", "expected": "Feedback text has sufficient contrast and is clearly readable."}
                    ]
                    steps = self._add_mandatory_steps(steps)
                    
                    objective = f"Verify that <b>{feature_name}</b> controls and feedback have sufficient contrast on <b>{platform}</b>."
                    tests.append({
                        'id': test_id,
                        'title': f"{test_id}: {title}",
                        'steps': steps,
                        'objective': objective,
                        'requires_object': True
                    })
        
        return tests

    def _add_mandatory_steps(self, steps: List[Dict]) -> List[Dict]:
        """Add mandatory PRE-REQ and Close steps."""
        # Check if main application PRE-REQ already exists (not just any PRE-REQ)
        has_app_prereq = any('PRE-REQ' in step.get('action', '').upper() and 
                            'ENV QuickDraw application' in step.get('action', '') 
                            for step in steps)
        if not has_app_prereq:
            prereq = {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""}
            # Insert after any existing tool-specific PRE-REQs
            insert_idx = 0
            for i, step in enumerate(steps):
                if 'PRE-REQ' in step.get('action', '').upper():
                    insert_idx = i + 1
                else:
                    break
            steps.insert(insert_idx, prereq)
        
        # Check if Close already exists
        has_close = any('close' in step.get('action', '').lower() or 'exit' in step.get('action', '').lower() for step in steps)
        if not has_close:
            close = {"action": "Close/Exit the QuickDraw application.", "expected": ""}
            steps.append(close)

        return steps

    def _post_process_test_cases(self, test_cases: List[Dict]) -> List[Dict]:
        """Post-process test cases to fix validation issues."""
        processed = []
        
        for tc in test_cases:
            steps = tc.get('steps', [])
            requires_object = tc.get('requires_object', False)
            
            # 1. Ensure object setup steps for tests that require objects
            if requires_object:
                has_draw = any('draw a shape' in step.get('action', '').lower() and 'canvas' in step.get('action', '').lower() 
                              for step in steps)
                has_select = any('select the' in step.get('action', '').lower() and ('shape' in step.get('action', '').lower() or 'object' in step.get('action', '').lower())
                                for step in steps)
                
                if not has_draw or not has_select:
                    # Find launch step index
                    launch_idx = -1
                    for i, step in enumerate(steps):
                        if 'launch' in step.get('action', '').lower():
                            launch_idx = i
                            break
                    
                    if launch_idx >= 0:
                        insert_idx = launch_idx + 1
                        if not has_draw:
                            steps.insert(insert_idx, {
                                "action": "Draw a shape (e.g. rectangle) on the Canvas.",
                                "expected": ""
                            })
                            insert_idx += 1
                        if not has_select:
                            steps.insert(insert_idx, {
                                "action": "Select the shape.",
                                "expected": ""
                            })
            
            # 2. Fix expected results: setup steps should have blank, verification steps should have expected
            for step in steps:
                action = step.get('action', '').lower()
                expected = step.get('expected', '').strip()
                
                # Setup steps that should have blank expected
                setup_patterns = [
                    'pre-req',
                    'launch',
                    'open',
                    'draw a shape',
                    'select the',
                    'activate',
                    'perform',
                    'hold shift',
                    'click and drag',
                    'continue rotating',
                    'continue performing',
                    'switch to',
                    'select another',
                    'move the',
                    'rotate the',
                    'deselect',
                    'record',
                    'navigate to',
                    'navigate through',
                    'swipe through'
                ]
                
                is_setup = any(pattern in action for pattern in setup_patterns)
                
                # Exception: "Verify" steps are verification, not setup
                if 'verify' in action:
                    is_setup = False
                
                # Exception: "Activate" steps that verify activation can have expected results
                # But if it's just "Activate tool" without verification context, it's setup
                if 'activate' in action:
                    # Only allow expected if it's explicitly verifying activation state
                    if expected and ('verify' in action or 'verification' in action):
                        is_setup = False
                    else:
                        # Activation steps are setup - remove expected
                        is_setup = True
                
                # Exception: Steps with expected results that describe what happened are verification
                # But only if they're not activation steps (which are setup)
                if expected and 'activate' not in action and any(word in expected.lower() for word in ['appears', 'is displayed', 'is activated', 'is rotated', 'is moved']):
                    is_setup = False
                
                if is_setup:
                    step['expected'] = ""
                elif 'verify' in action and not expected:
                    # Generate specific expected result for verification step
                    if 'rotation marker' in action:
                        if 'not visible' in action or 'disappears' in action:
                            step['expected'] = "Rotation marker is no longer visible."
                        elif 'appears' in action or 'visible' in action:
                            step['expected'] = "Rotation marker appears near the selected object."
                        else:
                            step['expected'] = "Rotation marker is displayed near the selected object."
                    elif 'rotation' in action and ('smooth' in action or 'range' in action):
                        step['expected'] = "Rotation is smooth and continuous throughout the 0-360 degree range."
                    elif 'rotation' in action and 'boundary' in action:
                        if '0 degree' in action:
                            step['expected'] = "Object maintains correct orientation at 0 degrees without visual artifacts."
                        elif '360' in action:
                            step['expected'] = "Object maintains correct orientation near 360 degrees without visual artifacts."
                        else:
                            step['expected'] = "Rotation handles boundary position correctly."
                    elif 'wrap-around' in action or 'wrap around' in action:
                        step['expected'] = "Wrap-around from 360 to 0 degrees is smooth and maintains object integrity."
                    elif 'angle' in action and ('feedback' in action or 'display' in action):
                        step['expected'] = "Rotation angle feedback is displayed near the cursor during interaction."
                    elif 'angle' in action and 'update' in action:
                        step['expected'] = "Angle values update in real-time as the object rotates."
                    elif 'angle' in action and 'readable' in action:
                        step['expected'] = "Angle feedback text remains clear and readable during rotation."
                    elif 'angle' in action and ('match' in action or 'accurate' in action):
                        step['expected'] = "Displayed angle values accurately reflect the actual object rotation."
                    elif 'shift' in action and 'increment' in action:
                        step['expected'] = "Object rotates only in 15-degree increments (15°, 30°, 45°, 60°, etc.)."
                    elif 'shift' in action and 'consistent' in action:
                        step['expected'] = "15° step locking works consistently in both clockwise and counter-clockwise directions."
                    elif 'geometry' in action or 'proportions' in action:
                        step['expected'] = "Object maintains its geometry and proportions after rotation."
                    elif 'pivot' in action:
                        step['expected'] = "Object rotates around the correct pivot point."
                    elif 'only selected' in action or 'selected object' in action:
                        step['expected'] = "Only the selected object rotates; other objects maintain their positions and orientations."
                    elif 'layout' in action or 'alignment' in action:
                        step['expected'] = "Overall Canvas layout is not altered by rotation of selected object."
                    elif 'undo' in action and 'restore' in action:
                        step['expected'] = "Object orientation is restored to its original state before rotation."
                    elif 'redo' in action and 'reapply' in action:
                        step['expected'] = "Object rotation is reapplied correctly."
                    elif 'cumulative' in action or 'drift' in action:
                        step['expected'] = "Object orientation is correctly restored and reapplied without cumulative drift."
                    elif 'available' in action or 'accessible' in action:
                        step['expected'] = "Feature is available and accessible."
                    elif 'visible' in action or 'displayed' in action:
                        step['expected'] = "Element is visible and displayed correctly."
                    elif 'active' in action:
                        step['expected'] = "Feature is active."
                    elif 'deactivated' in action:
                        step['expected'] = "Feature is deactivated."
                    elif 'focus' in action:
                        step['expected'] = "Focus indicators are visible."
                    elif 'label' in action or 'role' in action:
                        step['expected'] = "Labels and roles are correct."
                    elif 'contrast' in action:
                        step['expected'] = "Contrast is sufficient."
                    elif 'correctly' in action or 'works' in action:
                        step['expected'] = "Operation works correctly."
                    else:
                        step['expected'] = "Expected behavior is observed."
            
            # 3. Ensure PRE-REQ is first
            prereq_steps = [s for s in steps if 'PRE-REQ' in s.get('action', '').upper()]
            non_prereq_steps = [s for s in steps if 'PRE-REQ' not in s.get('action', '').upper()]
            
            if prereq_steps:
                steps = prereq_steps + non_prereq_steps
            
            # 4. Ensure Close is last (exact text match required by validator)
            has_close = any('Close/Exit the QuickDraw application' in s.get('action', '') 
                           for s in steps)
            if not has_close:
                # Add Close step if missing
                steps.append({"action": "Close/Exit the QuickDraw application.", "expected": ""})
            else:
                # Reorder to ensure Close is last
                close_steps = [s for s in steps if 'Close/Exit the QuickDraw application' in s.get('action', '')]
                non_close_steps = [s for s in steps if 'Close/Exit the QuickDraw application' not in s.get('action', '')]
                steps = non_close_steps + close_steps
            
            # Update test case
            tc['steps'] = steps
            processed.append(tc)
        
        return processed
    
    def _run_quality_gates(self, test_cases: List[Dict], criteria: List[str], qa_details: Dict) -> Dict:
        """
        Quality Gates: Fail Fast on violations.
        
        Returns:
            Dict with 'is_valid', 'errors', 'coverage'
        """
        errors = []
        coverage = {
            'ac_bullets_covered': set(),
            'edge_categories': {
                'state': 0,
                'boundary': 0,
                'undo_redo': 0,
                'visibility': 0,
                'constraint': 0,
                'negative': 0
            },
            'accessibility_tests': 0,
            'object_interaction_tests': 0
        }
        
        # Gate 1: Verify each AC bullet maps to exactly one primary test case
        ac_test_map = {}
        for tc in test_cases:
            tc_id = tc.get('id', '')
            source_ac = tc.get('source_ac_id')
            
            # Primary tests are tagged with source_ac_id
            if source_ac:
                ac_test_map[source_ac] = ac_test_map.get(source_ac, 0) + 1
            # Fallback: Check test ID for AC1
            elif '-AC1' in tc_id:
                ac_test_map['AC1'] = ac_test_map.get('AC1', 0) + 1
        
        # Check that we have tests for all non-cancelled AC bullets
        for idx, ac_bullet in enumerate(criteria):
            if self.rules.is_cancelled(ac_bullet):
                continue
            ac_key = f"AC{idx + 1}"
            if ac_key not in ac_test_map or ac_test_map[ac_key] == 0:
                errors.append(f"AC{idx + 1} has no primary test case")
            elif ac_test_map[ac_key] > 1:
                errors.append(f"AC{idx + 1} has {ac_test_map[ac_key]} primary test cases (should be exactly 1)")
            else:
                coverage['ac_bullets_covered'].add(ac_key)
        
        # Gate 2: Verify cancelled behavior is not tested
        for tc in test_cases:
            title = tc.get('title', '').lower()
            steps_text = ' '.join([s.get('action', '') for s in tc.get('steps', [])]).lower()
            combined_text = title + ' ' + steps_text
            
            cancelled_keywords = ['cancelled', 'out of scope', 'to be cancelled', 'not implemented']
            for keyword in cancelled_keywords:
                if keyword in combined_text:
                    errors.append(f"Test {tc.get('id')} contains cancelled behavior keyword: '{keyword}'")
        
        # Gate 3: Verify each object-based test includes draw + select steps
        for tc in test_cases:
            if tc.get('requires_object', False):
                steps = tc.get('steps', [])
                has_draw = any('draw a shape' in s.get('action', '').lower() and 'canvas' in s.get('action', '').lower() 
                              for s in steps)
                has_select = any('select the' in s.get('action', '').lower() and 
                               ('shape' in s.get('action', '').lower() or 'object' in s.get('action', '').lower() or 'drawn' in s.get('action', '').lower())
                               for s in steps)
                
                if not has_draw:
                    errors.append(f"Test {tc.get('id')} requires object but missing 'Draw a shape' step")
                if not has_select:
                    errors.append(f"Test {tc.get('id')} requires object but missing 'Select the drawn object' step")
                else:
                    coverage['object_interaction_tests'] += 1
        
        # Gate 4: Verify no forbidden wording
        forbidden_words = config.FORBIDDEN_WORDS if hasattr(config, 'FORBIDDEN_WORDS') else []
        for tc in test_cases:
            title = tc.get('title', '')
            objective = tc.get('objective', '')
            for step in tc.get('steps', []):
                action = step.get('action', '')
                expected = step.get('expected', '')
                
                for forbidden in forbidden_words:
                    if forbidden.lower() in title.lower():
                        errors.append(f"Test {tc.get('id')} title contains forbidden word: '{forbidden}'")
                    if forbidden.lower() in objective.lower():
                        errors.append(f"Test {tc.get('id')} objective contains forbidden word: '{forbidden}'")
                    if forbidden.lower() in action.lower():
                        errors.append(f"Test {tc.get('id')} step action contains forbidden word: '{forbidden}'")
                    if forbidden.lower() in expected.lower():
                        errors.append(f"Test {tc.get('id')} step expected contains forbidden word: '{forbidden}'")
        
        # Gate 5: Verify expected results only exist on verification steps
        for tc in test_cases:
            for step_idx, step in enumerate(tc.get('steps', []), start=1):
                action = step.get('action', '').lower()
                expected = step.get('expected', '').strip()
                
                # Setup steps that should have blank expected (strict list)
                strict_setup_patterns = [
                    'pre-req', 'launch', 'draw a shape', 'select the',
                    'perform', 'hold shift', 'click and drag',
                    'continue rotating', 'continue performing', 'switch to',
                    'select another', 'deselect', 'record',
                    'navigate to', 'navigate through', 'swipe through'
                ]
                
                # Steps that can have expected results (they verify state changes)
                allowed_with_expected = [
                    'open',  # "Open Tools Menu" verifies menu opened
                    'activate',  # "Activate tool" verifies tool activated
                    'move the',  # "Move the object" verifies object moved
                    'rotate the',  # "Rotate the object" verifies object rotated
                ]
                
                is_strict_setup = any(pattern in action for pattern in strict_setup_patterns)
                is_allowed_with_expected = any(pattern in action for pattern in allowed_with_expected)
                is_verify = 'verify' in action
                
                # Skip validation for steps that are allowed to have expected results
                if is_allowed_with_expected:
                    continue
                
                if is_strict_setup and expected and not is_verify:
                    errors.append(f"Test {tc.get('id')} Step {step_idx}: Setup step has expected result: '{action[:50]}...'")
                elif is_verify and not expected:
                    errors.append(f"Test {tc.get('id')} Step {step_idx}: Verification step missing expected result: '{action[:50]}...'")
        
        # Track edge categories
        for tc in test_cases:
            title_lower = tc.get('title', '').lower()
            if 'boundary' in title_lower or '360' in title_lower or '0 degree' in title_lower:
                coverage['edge_categories']['boundary'] += 1
            if 'undo' in title_lower or 'redo' in title_lower:
                coverage['edge_categories']['undo_redo'] += 1
            if 'visible' in title_lower or 'hidden' in title_lower or 'toggle' in title_lower:
                coverage['edge_categories']['visibility'] += 1
            if 'no selection' in title_lower or 'not visible' in title_lower or 'negative' in title_lower:
                coverage['edge_categories']['negative'] += 1
            if 'constraint' in title_lower or 'cannot' in title_lower or 'prevent' in title_lower:
                coverage['edge_categories']['constraint'] += 1
            if 'accessibility' in title_lower:
                coverage['accessibility_tests'] += 1
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'coverage': coverage
        }
    
    def _print_coverage_summary(self, test_cases: List[Dict], criteria: List[str], 
                                qa_details: Dict, coverage: Dict):
        """Print coverage summary report."""
        print("\n" + "=" * 80)
        print("COVERAGE SUMMARY")
        print("=" * 80)
        print(f"Total Test Cases Generated: {len(test_cases)}")
        print(f"AC Bullets Covered: {len(coverage['ac_bullets_covered'])}/{len([c for c in criteria if not self.rules.is_cancelled(c)])}")
        
        print(f"\nEdge Categories Applied:")
        for category, count in coverage['edge_categories'].items():
            if count > 0:
                print(f"  • {category.capitalize()}: {count} test(s)")
        
        print(f"\nSpecial Test Types:")
        print(f"  • Object Interaction Tests: {coverage['object_interaction_tests']}")
        print(f"  • Accessibility Tests: {coverage['accessibility_tests']}")
        
        print(f"\nAC Bullet to Test Case Mapping:")
        for ac_key in sorted(coverage['ac_bullets_covered']):
            matching_tests = [tc for tc in test_cases if ac_key in tc.get('id', '') or (f"-AC1" in tc.get('id', '') and ac_key == 'AC1')]
            if matching_tests:
                print(f"  • {ac_key}: {matching_tests[0].get('id', 'N/A')}")
        
        print("=" * 80)

    def _extract_entry_point(self, ac_text: str, story_data: Dict) -> str:
        """Extract entry point/UI surface from AC or story."""
        entry_points = [
            'Tools Menu', 'File Menu', 'Edit Menu', 'Help Menu', 'View Menu',
            'Properties Panel', 'Dimensions Panel', 'Canvas', 'Toolbar',
            'Dialog Window', 'Context Menu', 'Top Action Toolbar'
        ]

        ac_lower = ac_text.lower()
        for ep in entry_points:
            if ep.lower() in ac_lower:
                return ep

        return "Tools Menu"  # Default

    def _extract_action_from_ac(self, ac_text: str) -> str:
        """Extract the core action from AC text."""
        action = ac_text.strip()
        prefixes = ['When', 'The user', 'User can', 'Users can', 'The system', 'System']
        for prefix in prefixes:
            if action.startswith(prefix):
                action = action[len(prefix):].strip()

        if '.' in action:
            action = action.split('.')[0]

        return action[:80] if len(action) > 80 else action

    def _extract_expected_outcome(self, ac_text: str) -> str:
        """Extract expected outcome from AC."""
        outcome_keywords = ['then', 'should', 'must', 'will', 'displays', 'shows', 'appears']

        for keyword in outcome_keywords:
            if keyword in ac_text.lower():
                parts = ac_text.lower().split(keyword, 1)
                if len(parts) > 1:
                    outcome = parts[1].strip()
                    return outcome[:100] if len(outcome) > 100 else outcome

        return "Expected behavior is observed"

    def _extract_added_element(self, ac_text: str) -> str:
        """Extract what element is added/shown."""
        element_keywords = {
            'measurement': 'Measurement line',
            'dimension': 'Dimension marker',
            'label': 'Label',
            'marker': 'Marker',
            'indicator': 'Indicator',
            'line': 'Line',
            'arrow': 'Arrow'
        }

        ac_lower = ac_text.lower()
        for keyword, element in element_keywords.items():
            if keyword in ac_lower:
                return element

        return "Element"
    
    def _extract_scenario(self, ac_text: str) -> str:
        """Extract scenario description from AC text."""
        # Try to extract a meaningful scenario
        ac_lower = ac_text.lower()
        
        # Look for key phrases that indicate scenarios
        if 'when' in ac_lower:
            parts = ac_lower.split('when', 1)
            if len(parts) > 1:
                scenario = parts[1].split('.')[0].strip()
                return scenario[:60] if len(scenario) > 60 else scenario
        
        # Fallback: use first meaningful phrase
        words = ac_text.split()
        if len(words) > 3:
            return ' '.join(words[:5])[:60]
        
        return "Behavior verification"
    
    def _extract_action_type(self, feature_name: str, ac_text: str = "") -> str:
        """Extract the action type from feature name or AC text (e.g., 'rotate', 'move', 'measure')."""
        text_lower = (feature_name + " " + ac_text).lower()
        
        # Check for specific action types
        if 'rotate' in text_lower:
            return 'rotate'
        elif 'move' in text_lower:
            return 'move'
        elif 'measure' in text_lower or 'dimension' in text_lower:
            return 'measure'
        elif 'flip' in text_lower or 'mirror' in text_lower:
            return 'flip'
        elif 'scale' in text_lower or 'resize' in text_lower:
            return 'scale'
        elif 'undo' in text_lower or 'redo' in text_lower:
            return 'undo_redo'
        else:
            return 'generic'
    
    def _generate_specific_action_step(self, action_type: str, feature_name: str, context: str = "") -> str:
        """Generate a specific, human-like action step based on action type."""
        if action_type == 'rotate':
            if 'marker' in context.lower() or 'rotation marker' in context.lower():
                return "Click and drag the rotation marker to rotate the object."
            elif '360' in context.lower() or 'full range' in context.lower():
                return "Click and drag the rotation marker to rotate the object through the full 0-360 degree range."
            elif '0 degree' in context.lower():
                return "Rotate the object to 0 degrees."
            elif '360' in context.lower() and 'near' in context.lower():
                return "Rotate the object to near 360 degrees (e.g., 359 degrees)."
            elif 'shift' in context.lower() or 'increment' in context.lower():
                return "Hold Shift key and drag the rotation marker."
            else:
                return "Click and drag the rotation marker to rotate the object."
        elif action_type == 'move':
            return "Move the object to a new position."
        elif action_type == 'measure':
            if 'diameter' in context.lower():
                return "Select Diameter."
            elif 'radius' in context.lower():
                return "Select Radius."
            elif 'toggle' in context.lower() or 'visibility' in context.lower():
                return "Enable the Diameter measurement toggle."
            else:
                return f"Activate {feature_name}."
        elif action_type == 'flip':
            if 'horizontal' in context.lower():
                return "Select horizontal flip option."
            elif 'vertical' in context.lower():
                return "Select vertical flip option."
            else:
                return f"Activate {feature_name}."
        else:
            return f"Activate {feature_name}."
    
    def _generate_specific_expected_result(self, action_type: str, feature_name: str, action_step: str, context: str = "") -> str:
        """Generate a specific, descriptive expected result based on action type and step."""
        action_lower = action_step.lower()
        
        if action_type == 'rotate':
            if 'full 0-360' in action_lower or 'full range' in action_lower:
                return "Object rotates smoothly through the complete 0-360 degree range."
            elif '0 degree' in action_lower:
                return "Object is rotated to 0 degrees."
            elif 'near 360' in action_lower or '359' in action_lower:
                return "Object is rotated to near 360 degrees."
            elif 'shift' in action_lower or 'increment' in action_lower:
                return "Rotation locks to 15° incremental steps."
            elif 'marker' in action_lower:
                return "Rotation marker appears near the selected object."
            elif 'angle' in action_lower or 'feedback' in action_lower:
                return "Rotation angle feedback is displayed near the cursor during interaction."
            else:
                return "Object rotates correctly."
        elif action_type == 'move':
            return "Object is moved to a new position."
        elif action_type == 'measure':
            if 'diameter' in action_lower or 'radius' in action_lower:
                return "Diameter line and label are displayed for the selected ellipse."
            elif 'toggle' in action_lower or 'visibility' in action_lower:
                return "Diameter line and label are visible after showing."
            else:
                return f"{feature_name} is activated."
        elif action_type == 'flip':
            return "Object is flipped correctly."
        else:
            return "Expected behavior is observed."
