"""
Quality-Enforced Test Generator

Generates production-ready test suites that strictly follow quality gates for ANY story type.
This is a generic framework that works for all user stories without hardcoded logic.
"""

from typing import List, Dict, Tuple, Optional
import re

import config
from src.objective_generator import ObjectiveGenerator


class QualityRules:
    """Quality rules enforcer."""
    
    # Forbidden words that cause hard fail
    FORBIDDEN_WORDS = ['or / OR', ' or ', ' OR ', 'if available', 'if supported', 'where safe', 'ambiguous']
    
    # Forbidden area terms (use specific areas instead)
    FORBIDDEN_AREAS = ['Functionality', 'General', 'Behavior', 'Validation', 'System']
    
    # Allowed areas (concrete UI surfaces)
    ALLOWED_AREAS = [
        'File Menu', 'Edit Menu', 'Tools Menu', 'View Menu', 'Help Menu',
        'Properties Panel', 'Dimensions Panel', 'Canvas',
        'Dialog', 'Modal Window', 'Toolbar'
    ]
    
    @staticmethod
    def validate_test_case(test_case: Dict) -> List[str]:
        """Validate a single test case against quality rules."""
        errors = []
        test_id = test_case.get('id', 'UNKNOWN')
        
        # Rule 1: Must have PRE-REQ as first step
        steps = test_case.get('steps', [])
        if not steps:
            errors.append(f"{test_id}: No steps defined")
        elif not steps[0]['action'].startswith('PRE-REQ:'):
            errors.append(f"{test_id}: First step must be PRE-REQ")
        
        # Rule 2: Must have Close/Exit as last step
        if steps and 'Close/Exit' not in steps[-1]['action']:
            errors.append(f"{test_id}: Last step must be Close/Exit")
        
        # Rule 3: Last step must have no expected result
        if steps and steps[-1]['expected']:
            errors.append(f"{test_id}: Last step (Close/Exit) must have no expected result")
        
        # Rule 4: No forbidden words in steps
        for step_idx, step in enumerate(steps, 1):
            action = step['action']
            expected = step['expected']
            for forbidden in QualityRules.FORBIDDEN_WORDS:
                if forbidden.lower() in action.lower():
                    errors.append(f"{test_id} Step {step_idx}: Forbidden phrase '{forbidden}' in action")
                if forbidden.lower() in expected.lower():
                    errors.append(f"{test_id} Step {step_idx}: Forbidden phrase '{forbidden}' in expected")
        
        # Rule 5: Title must have format: ID: Feature / Area / Scenario
        title = test_case.get('title', '')
        if ': ' not in title:
            errors.append(f"{test_id}: Title missing ID separator ':'")
        else:
            title_body = title.split(': ', 1)[1]
            parts = title_body.split(' / ')
            if len(parts) < 3:
                errors.append(f"{test_id}: Title must have 3 parts (Feature / Area / Scenario)")
            else:
                area = parts[1].strip()
                # Check for forbidden areas
                for forbidden in QualityRules.FORBIDDEN_AREAS:
                    if forbidden.lower() in area.lower():
                        errors.append(f"{test_id}: Forbidden area term '{forbidden}' - use specific UI surface")
        
        return errors


class QualityEnforcedGenerator:
    """Generates comprehensive, quality-enforced test suites for ANY story."""
    
    def __init__(self):
        self.obj_gen = ObjectiveGenerator()
        self.test_id_counter = 5
    
    def generate(
        self,
        story_id: int,
        feature_name: str,
        description: str,
        acceptance_criteria: List[str],
        qa_planning: List[str]
    ) -> Tuple[List[Dict], Dict]:
        """
        Generate comprehensive test suite with quality enforcement.
        
        Returns:
            (test_cases, metadata) where metadata includes coverage and validation
        """
        print(f"\n→ Generating quality-enforced test suite for story {story_id}...")
        
        # Extract context from description
        context = self._extract_context(description, acceptance_criteria, qa_planning)
        
        test_cases = []
        ac_coverage = {}
        qa_coverage = {}
        
        # Step 1: Generate AC1 (mandatory availability test)
        ac1_test = self._generate_ac1_test(story_id, feature_name, context)
        test_cases.append(ac1_test)
        ac_coverage[1] = [ac1_test['id']]
        
        # Step 2: Generate tests for remaining ACs (1 per AC bullet)
        for ac_idx, ac_bullet in enumerate(acceptance_criteria[1:], start=2):
            if self._is_cancelled(ac_bullet):
                print(f"  ⚠ Skipping cancelled AC{ac_idx}")
                continue
            
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += 5
            
            test = self._generate_ac_test(test_id, ac_bullet, ac_idx, feature_name, context)
            test_cases.append(test)
            ac_coverage[ac_idx] = [test_id]
        
        # Step 3: Generate QA plan support tests
        qa_tests = self._generate_qa_tests(story_id, feature_name, qa_planning, context)
        test_cases.extend(qa_tests)
        for i, qa_test in enumerate(qa_tests, 1):
            qa_coverage[i] = [qa_test['id']]
        
        # Step 4: Generate accessibility tests (split by device)
        acc_tests = self._generate_accessibility_tests(story_id, feature_name, context)
        test_cases.extend(acc_tests)
        
        # Step 5: Validate quality gates (hard fail)
        validation = self._validate_quality_gates(test_cases, acceptance_criteria, qa_planning)
        
        metadata = {
            'ac_coverage': ac_coverage,
            'qa_coverage': qa_coverage,
            'validation': validation,
            'total_tests': len(test_cases),
            'context': context
        }
        
        return test_cases, metadata
    
    def _extract_context(self, description: str, acs: List[str], qa: List[str]) -> Dict:
        """Extract context from story evidence."""
        context = {
            'entry_point': 'Menu',
            'area': 'Canvas',
            'requires_objects': False,
            'requires_selection': False,
            'requires_undo_redo': False,
            'requires_persistence': False,
            'platforms': []
        }
        
        # Combine all text for analysis
        all_text = (description + ' ' + ' '.join(acs) + ' ' + ' '.join(qa)).lower()
        
        # Extract entry point
        if 'tools menu' in all_text or 'tools →' in all_text:
            context['entry_point'] = 'Tools Menu'
        elif 'edit menu' in all_text or 'edit →' in all_text:
            context['entry_point'] = 'Edit Menu'
        elif 'file menu' in all_text or 'file →' in all_text:
            context['entry_point'] = 'File Menu'
        elif 'properties panel' in all_text:
            context['entry_point'] = 'Properties Panel'
        elif 'dimensions menu' in all_text or 'dimensions →' in all_text:
            context['entry_point'] = 'Dimensions Menu'
        
        # Determine area (defaults to entry point unless overridden)
        context['area'] = context['entry_point']
        if 'canvas' in all_text:
            context['area'] = 'Canvas'
        
        # Detect requirements
        if any(word in all_text for word in ['object', 'shape', 'selection', 'selected', 'overlapping']):
            context['requires_objects'] = True
            context['requires_selection'] = True
        
        if 'undo' in all_text or 'redo' in all_text:
            context['requires_undo_redo'] = True
        
        if 'save' in all_text or 'persist' in all_text or 'reopen' in all_text:
            context['requires_persistence'] = True
        
        # Extract platforms
        if 'windows 11' in all_text:
            context['platforms'].append('Windows 11')
        if 'ipad' in all_text:
            context['platforms'].append('iPad')
        if 'android tablet' in all_text:
            context['platforms'].append('Android Tablet')
        
        return context
    
    def _is_cancelled(self, ac_bullet: str) -> bool:
        """Check if AC is cancelled."""
        return 'cancelled' in ac_bullet.lower() or 'deferred' in ac_bullet.lower()
    
    def _generate_ac1_test(self, story_id: int, feature_name: str, context: Dict) -> Dict:
        """Generate AC1 availability test (mandatory)."""
        test_id = f"{story_id}-AC1"
        entry_point = context['entry_point']
        
        title = f"{test_id}: {feature_name} / {entry_point} / Feature Available And Accessible"
        
        steps = [
            {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
            {"action": "Launch the ENV QuickDraw application.", "expected": ""},
            {"action": f"Navigate to {entry_point}.", "expected": ""},
            {"action": f"Verify {feature_name} option is visible and accessible.",
             "expected": f"{feature_name} option is present and accessible."},
            {"action": "Close/Exit the QuickDraw application", "expected": ""}
        ]
        
        objective = f"Verify that {feature_name} is available and accessible from {entry_point}"
        
        return {
            'id': test_id,
            'title': title,
            'steps': steps,
            'objective': objective,
            'ac_index': 1
        }
    
    def _generate_ac_test(
        self,
        test_id: str,
        ac_bullet: str,
        ac_index: int,
        feature_name: str,
        context: Dict
    ) -> Dict:
        """Generate test for AC bullet (generic logic)."""
        # Extract scenario from AC
        scenario = self._extract_scenario(ac_bullet)
        
        # Determine area from AC or use context
        area = self._determine_area(ac_bullet, context)
        
        # Build title
        title = f"{test_id}: {feature_name} / {area} / {scenario}"
        
        # Build steps
        steps = self._build_steps(ac_bullet, feature_name, context)
        
        # Build objective
        objective = self._build_objective(ac_bullet, feature_name)
        
        return {
            'id': test_id,
            'title': title,
            'steps': steps,
            'objective': objective,
            'ac_index': ac_index
        }
    
    def _extract_scenario(self, ac_bullet: str) -> str:
        """Extract balanced scenario from AC bullet."""
        # Clean AC bullet
        ac_clean = re.sub(r'^\d+[\.)]\s*', '', ac_bullet).strip()
        
        # Capitalize first letter of each word
        words = ac_clean.split()[:10]  # Max 10 words
        scenario = ' '.join(word.capitalize() for word in words)
        
        return scenario[:80]  # Max 80 chars
    
    def _determine_area(self, ac_bullet: str, context: Dict) -> str:
        """Determine area from AC or context."""
        ac_lower = ac_bullet.lower()
        
        if 'canvas' in ac_lower:
            return 'Canvas'
        elif 'properties' in ac_lower:
            return 'Properties Panel'
        elif 'tools menu' in ac_lower:
            return 'Tools Menu'
        elif 'edit menu' in ac_lower:
            return 'Edit Menu'
        elif 'file menu' in ac_lower:
            return 'File Menu'
        else:
            return context['area']
    
    def _build_steps(self, ac_bullet: str, feature_name: str, context: Dict) -> List[Dict]:
        """Build test steps with object setup if needed."""
        steps = []
        
        # Step 1: PRE-REQ (mandatory)
        steps.append({"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""})
        
        # Step 2: Launch
        steps.append({"action": "Launch the ENV QuickDraw application.", "expected": ""})
        
        # Add object setup if needed
        ac_lower = ac_bullet.lower()
        if context['requires_objects'] or any(word in ac_lower for word in ['object', 'shape', 'selected']):
            # Determine number of objects needed
            if 'overlapping' in ac_lower or 'stacking' in ac_lower:
                num_objects = 3
                steps.append({"action": f"Draw {num_objects} overlapping shapes on the Canvas.", "expected": ""})
                
                # Determine which to select
                if 'bottom' in ac_lower:
                    steps.append({"action": "Select the bottom-most shape.", "expected": ""})
                elif 'top' in ac_lower:
                    steps.append({"action": "Select the top-most shape.", "expected": ""})
                else:
                    steps.append({"action": "Select one shape.", "expected": ""})
            elif 'no' not in ac_lower:  # Not a "no selection" scenario
                steps.append({"action": "Draw a shape on the Canvas.", "expected": ""})
                steps.append({"action": "Select the drawn shape.", "expected": ""})
        
        # Add action steps
        action_steps = self._extract_actions(ac_bullet, feature_name, context)
        steps.extend(action_steps)
        
        # Add verification
        verification = self._build_verification(ac_bullet)
        steps.append(verification)
        
        # Final step: Close/Exit (mandatory, no expected)
        steps.append({"action": "Close/Exit the QuickDraw application", "expected": ""})
        
        return steps
    
    def _extract_actions(self, ac_bullet: str, feature_name: str, context: Dict) -> List[Dict]:
        """Extract action steps from AC."""
        steps = []
        entry_point = context['entry_point']
        
        # Generic action step
        steps.append({"action": f"Access {feature_name} via {entry_point}.", "expected": ""})
        
        return steps
    
    def _build_verification(self, ac_bullet: str) -> Dict:
        """Build verification step from AC."""
        ac_clean = re.sub(r'^\d+[\.)]\s*', '', ac_bullet).strip()
        
        action = "Verify the expected behavior is observed."
        expected = ac_clean[:150]  # Use AC as expected result
        
        return {"action": action, "expected": expected}
    
    def _build_objective(self, ac_bullet: str, feature_name: str) -> str:
        """Build objective from AC."""
        ac_clean = re.sub(r'^\d+[\.)]\s*', '', ac_bullet).strip()
        return ac_clean
    
    def _generate_qa_tests(
        self,
        story_id: int,
        feature_name: str,
        qa_planning: List[str],
        context: Dict
    ) -> List[Dict]:
        """Generate tests for QA planning coverage."""
        qa_tests = []
        
        # QA patterns that need separate tests
        qa_patterns = [
            (r'undo.*redo', 'Undo/Redo'),
            (r'save.*reopen|persist', 'Persistence'),
            (r'repeat|stability|multiple times', 'Repeated Actions'),
            (r'no side effects', 'No Side Effects'),
            (r'mixed.*types', 'Mixed Object Types')
        ]
        
        for qa_bullet in qa_planning:
            qa_lower = qa_bullet.lower()
            
            for pattern, test_type in qa_patterns:
                if re.search(pattern, qa_lower):
                    test_id = f"{story_id}-{self.test_id_counter:03d}"
                    self.test_id_counter += 5
                    
                    test = self._generate_qa_specific_test(
                        test_id, feature_name, test_type, context
                    )
                    qa_tests.append(test)
                    break
        
        return qa_tests
    
    def _generate_qa_specific_test(
        self,
        test_id: str,
        feature_name: str,
        test_type: str,
        context: Dict
    ) -> Dict:
        """Generate specific QA test."""
        entry_point = context['entry_point']
        
        if test_type == 'Undo/Redo':
            title = f"{test_id}: {feature_name} / Edit Menu / Undo Redo Supports {feature_name} Actions"
            steps = [
                {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
                {"action": "Launch the ENV QuickDraw application.", "expected": ""},
                {"action": "Perform setup for testing.", "expected": ""},
                {"action": f"Apply {feature_name} action.", "expected": ""},
                {"action": "Verify action is applied.", "expected": "Action is applied."},
                {"action": "Select Edit → Undo.", "expected": ""},
                {"action": "Verify action is reverted.", "expected": "Action is reverted."},
                {"action": "Select Edit → Redo.", "expected": ""},
                {"action": "Verify action is reapplied.", "expected": "Action is reapplied."},
                {"action": "Close/Exit the QuickDraw application", "expected": ""}
            ]
            objective = f"Verify that Undo and Redo correctly revert and reapply {feature_name} actions"
        
        elif test_type == 'Persistence':
            title = f"{test_id}: {feature_name} / File Menu / Changes Persist After Save And Reopen"
            steps = [
                {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
                {"action": "Launch the ENV QuickDraw application.", "expected": ""},
                {"action": f"Apply {feature_name} action.", "expected": ""},
                {"action": "Save the drawing.", "expected": ""},
                {"action": "Close and reopen the drawing.", "expected": ""},
                {"action": "Verify the changes persist.", "expected": "Changes are preserved."},
                {"action": "Close/Exit the QuickDraw application", "expected": ""}
            ]
            objective = f"Verify that {feature_name} changes persist after saving and reopening"
        
        else:  # Generic QA test
            title = f"{test_id}: {feature_name} / {entry_point} / {test_type}"
            steps = [
                {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
                {"action": "Launch the ENV QuickDraw application.", "expected": ""},
                {"action": f"Perform {test_type} scenario.", "expected": ""},
                {"action": "Verify expected behavior.", "expected": "Behavior is correct."},
                {"action": "Close/Exit the QuickDraw application", "expected": ""}
            ]
            objective = f"Verify that {test_type} works correctly"
        
        return {'id': test_id, 'title': title, 'steps': steps, 'objective': objective}
    
    def _generate_accessibility_tests(
        self,
        story_id: int,
        feature_name: str,
        context: Dict
    ) -> List[Dict]:
        """Generate accessibility tests split by device."""
        acc_tests = []
        entry_point = context['entry_point']
        
        # Windows 11
        test_id = f"{story_id}-{self.test_id_counter:03d}"
        self.test_id_counter += 5
        
        title = f"{test_id}: {feature_name} / Accessibility / Keyboard Navigation And Focus (Windows 11)"
        steps = [
            {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
            {"action": "PRE-REQ: Accessibility Insights for Windows tool is installed", "expected": ""},
            {"action": "Launch the ENV QuickDraw application on Windows 11.", "expected": ""},
            {"action": f"Navigate to {entry_point} → {feature_name} using keyboard.", "expected": ""},
            {"action": "Verify keyboard navigation and visible focus.",
             "expected": f"{feature_name} is keyboard operable with visible focus."},
            {"action": "Close/Exit the QuickDraw application", "expected": ""}
        ]
        objective = f"Verify that {feature_name} supports keyboard navigation and visible focus on Windows 11"
        acc_tests.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})
        
        # iPad
        test_id = f"{story_id}-{self.test_id_counter:03d}"
        self.test_id_counter += 5
        
        title = f"{test_id}: {feature_name} / Accessibility / VoiceOver Labels And Order (iPad)"
        steps = [
            {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
            {"action": "PRE-REQ: Apple built-in accessibility tools are available and enabled (e.g., VoiceOver)", "expected": ""},
            {"action": "Launch the ENV QuickDraw application on iPad.", "expected": ""},
            {"action": f"Navigate to {entry_point} → {feature_name} using VoiceOver.", "expected": ""},
            {"action": "Verify VoiceOver labels and reading order.",
             "expected": "VoiceOver announces with meaningful labels."},
            {"action": "Close/Exit the QuickDraw application", "expected": ""}
        ]
        objective = f"Verify that {feature_name} has meaningful VoiceOver labels on iPad"
        acc_tests.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})
        
        # Android Tablet
        test_id = f"{story_id}-{self.test_id_counter:03d}"
        self.test_id_counter += 5
        
        title = f"{test_id}: {feature_name} / Accessibility / Labels And Roles Scan (Android Tablet)"
        steps = [
            {"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""},
            {"action": "PRE-REQ: Accessibility Scanner (Google) Free tool is installed", "expected": ""},
            {"action": "Launch the ENV QuickDraw application on Android Tablet.", "expected": ""},
            {"action": f"Run Accessibility Scanner on {feature_name} controls.", "expected": ""},
            {"action": "Verify no critical label or role issues.",
             "expected": "Scanner reports no critical issues."},
            {"action": "Close/Exit the QuickDraw application", "expected": ""}
        ]
        objective = f"Verify that {feature_name} meets accessibility standards on Android Tablet"
        acc_tests.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})
        
        return acc_tests
    
    def _validate_quality_gates(
        self,
        test_cases: List[Dict],
        acs: List[str],
        qa: List[str]
    ) -> Dict:
        """Validate all quality gates (hard fail)."""
        all_errors = []
        warnings = []
        
        # Validate each test case
        for tc in test_cases:
            errors = QualityRules.validate_test_case(tc)
            all_errors.extend(errors)
        
        # Check AC1 exists
        ac1_tests = [tc for tc in test_cases if '-AC1' in tc['id']]
        if not ac1_tests:
            all_errors.append("CRITICAL: AC1 test is missing")
        elif 'Available' not in ac1_tests[0]['title']:
            all_errors.append("CRITICAL: AC1 must be availability test")
        
        # Check ID increments
        non_ac1_ids = [int(tc['id'].split('-')[1]) for tc in test_cases 
                       if '-AC1' not in tc['id'] and tc['id'].split('-')[1].isdigit()]
        for i in range(len(non_ac1_ids) - 1):
            if non_ac1_ids[i+1] - non_ac1_ids[i] != 5:
                all_errors.append(f"ID increment error: {non_ac1_ids[i]} -> {non_ac1_ids[i+1]}")
        
        # Check accessibility tests
        acc_tests = [tc for tc in test_cases if 'Accessibility' in tc['title']]
        required_devices = ['Windows 11', 'iPad', 'Android Tablet']
        for device in required_devices:
            if not any(device in tc['title'] for tc in acc_tests):
                warnings.append(f"No accessibility test for {device}")
        
        return {
            'is_valid': len(all_errors) == 0,
            'errors': all_errors,
            'warnings': warnings,
            'total_errors': len(all_errors),
            'total_warnings': len(warnings)
        }
    
    def generate_objectives_file(self, test_cases: List[Dict], output_file: str):
        """Generate 1:1 mapped objectives with proper formatting."""
        self.obj_gen.generate_objectives_file(test_cases, output_file)
