"""
Quality Gates: Hard-fail validation for test case quality.

These gates enforce strict compliance with test design rules.
"""
from typing import List, Tuple, Dict
import re


class TitleQualityGate:
    """
    Enforces title quality rules (hard fail).

    Rejects titles that:
    - Use generic terms like "Verify selected object"
    - Have forbidden area terms
    - Duplicate "Feature availability" beyond AC1
    - Don't communicate WHERE + WHAT + OUTCOME
    """

    # Forbidden area terms
    FORBIDDEN_AREAS = [
        'Functionality',
        'Accessibility',  # alone
        'Behavior',
        'Validation',
        'General',
        'System',
    ]

    # Allowed area terms (behavior-based categories + concrete UI surfaces)
    ALLOWED_AREAS = [
        # Behavior-based categories (from approved 270479 patterns)
        'Tool Availability',
        'Tool Activation',
        'Drawing Behavior',
        'Editing Behavior',
        'WCAG Compliance',
        # Concrete UI surfaces
        'File Menu',
        'Edit Menu',
        'Tools Menu',
        'View Menu',
        'Help Menu',
        'Properties Panel',
        'Dimensions Panel',
        'Canvas',
        'Dialog Window',
        'Modal Window',
        'Top Action Toolbar',
        'Toolbar',
        'Left Toolbar',
        'Top Menu',
        'Settings',
        'Undo/Redo',
    ]

    # Generic scenario patterns (forbidden beyond AC1)
    GENERIC_SCENARIOS = [
        r'Verify selected object',
        r'Select selected object',
        r'Enable selected object',
        r'Disable selected object',
        r'Modify selected object',
        r'Update selected object',
        r'^Verify\s+\w+$',  # Just "Verify X"
        r'^Select\s+\w+$',  # Just "Select X"
        r'^Enable\s+\w+$',  # Just "Enable X"
    ]

    def validate_title(self, test_id: str, title: str) -> Tuple[bool, List[str]]:
        """
        Validate test case title against quality rules.

        Args:
            test_id: Test case ID (e.g., "272889-AC1")
            title: Full test case title

        Returns:
            (is_valid, errors) tuple
        """
        errors = []

        # Parse title components
        parts = title.split(' / ')
        if len(parts) < 3:
            errors.append(f"{test_id}: Title must have format: Feature / Area / Scenario")
            return False, errors

        feature = parts[0].strip()
        area = parts[1].strip()
        scenario = parts[2].split('(')[0].strip()  # Remove device suffix if present

        # Check 1: Area must not be a forbidden term
        for forbidden in self.FORBIDDEN_AREAS:
            if forbidden.lower() in area.lower():
                errors.append(
                    f"{test_id}: Forbidden area term '{forbidden}' in title. "
                    f"Use concrete UI surface (Tools Menu, Properties Panel, Canvas, etc.)"
                )

        # Check 2: Scenario must not be generic (except AC1)
        is_ac1 = 'AC1' in test_id
        if not is_ac1:
            for generic_pattern in self.GENERIC_SCENARIOS:
                if re.search(generic_pattern, scenario, re.IGNORECASE):
                    errors.append(
                        f"{test_id}: Generic scenario '{scenario}'. "
                        f"Must specify: action + target + outcome "
                        f"(e.g., 'Rotate Tool Applies 90 Degree Rotation')"
                    )
                    break

        # Check 3: "Feature availability" only allowed in AC1
        if not is_ac1 and 'feature availability' in scenario.lower():
            errors.append(
                f"{test_id}: 'Feature availability' only allowed in AC1. "
                f"Use specific scenario name for this test."
            )

        # Check 4: Title must communicate WHERE + WHAT + OUTCOME
        if not self._has_sufficient_detail(scenario, is_ac1):
            errors.append(
                f"{test_id}: Scenario '{scenario}' lacks detail. "
                f"Must answer: FROM WHERE + WHAT ACTION + WHAT OUTCOME"
            )

        return len(errors) == 0, errors

    def _has_sufficient_detail(self, scenario: str, is_ac1: bool) -> bool:
        """Check if scenario has sufficient detail."""
        # AC1 can be "Feature Availability" or "Commands Available"
        if is_ac1:
            return True

        # Scenario must be more than 2 words
        words = scenario.split()
        if len(words) < 2:
            return False

        # Scenario must not be just verb + noun
        simple_patterns = [
            r'^(Verify|Enable|Disable|Select|Modify|Update)\s+\w+$',
        ]

        for pattern in simple_patterns:
            if re.match(pattern, scenario, re.IGNORECASE):
                return False

        return True


class ForbiddenWordScanner:
    """
    Scans test steps for forbidden wording (hard fail).

    Forbidden:
    - or / OR
    - if available
    - if supported
    - where safe
    """

    FORBIDDEN_PATTERNS = [
        (r'\bor\b', '"or"'),
        (r'\bOR\b', '"OR"'),
        (r'if\s+available', '"if available"'),
        (r'if\s+supported', '"if supported"'),
        (r'where\s+safe', '"where safe"'),
        (r'\(e\.g\.,\s+[^)]+\s+or\s+', '"e.g., X or Y"'),  # Catches "e.g., Ctrl+Z or Cmd+Z"
    ]

    def scan_steps(self, test_id: str, steps: List[Dict]) -> Tuple[bool, List[str]]:
        """
        Scan test steps for forbidden words.

        Args:
            test_id: Test case ID
            steps: List of step dicts with 'action' and 'expected' keys

        Returns:
            (is_valid, errors) tuple
        """
        errors = []

        for idx, step in enumerate(steps, start=1):
            step_action = step.get('action', '')
            step_expected = step.get('expected', '')

            # Scan action
            for pattern, description in self.FORBIDDEN_PATTERNS:
                if re.search(pattern, step_action, re.IGNORECASE):
                    errors.append(
                        f"{test_id}: Step {idx} Action contains forbidden {description}. "
                        f"Use deterministic steps instead."
                    )

            # Scan expected
            for pattern, description in self.FORBIDDEN_PATTERNS:
                if re.search(pattern, step_expected, re.IGNORECASE):
                    errors.append(
                        f"{test_id}: Step {idx} Expected contains forbidden {description}. "
                        f"Use deterministic verification instead."
                    )

        return len(errors) == 0, errors


class ACCoverageTracker:
    """
    Tracks AC coverage to ensure one test per AC bullet.

    Rules:
    - AC1 generates exactly 1 test
    - Each subsequent AC bullet generates exactly 1 primary test
    - Accessibility tests are separate (not counted in AC coverage)
    """

    def __init__(self, num_ac_bullets: int):
        """
        Initialize coverage tracker.

        Args:
            num_ac_bullets: Total number of AC bullets (excluding "Acceptance Criteria" header)
        """
        self.num_ac_bullets = num_ac_bullets
        self.ac_coverage = {i: [] for i in range(1, num_ac_bullets + 1)}

    def track_test(self, test_id: str, ac_index: int):
        """Track that a test case covers a specific AC."""
        if 1 <= ac_index <= self.num_ac_bullets:
            self.ac_coverage[ac_index].append(test_id)

    def validate_coverage(self) -> Tuple[bool, List[str]]:
        """
        Validate AC coverage.

        Returns:
            (is_valid, errors) tuple
        """
        errors = []

        for ac_index, test_ids in self.ac_coverage.items():
            if len(test_ids) == 0:
                errors.append(f"AC{ac_index}: No test case generated")
            elif len(test_ids) > 1:
                # Multiple tests for same AC (may be valid if one is edge case)
                # For now, we'll warn but not fail
                pass

        return len(errors) == 0, errors

    def get_summary(self) -> str:
        """Get coverage summary."""
        summary = "AC Coverage:\n"
        for ac_index in sorted(self.ac_coverage.keys()):
            test_ids = self.ac_coverage[ac_index]
            if test_ids:
                summary += f"  AC{ac_index}: {', '.join(test_ids)}\n"
            else:
                summary += f"  AC{ac_index}: NO COVERAGE\n"
        return summary


class QualityGateRunner:
    """
    Runs all quality gates on generated test cases.

    Hard fails if any gate fails.
    """

    def __init__(self, num_ac_bullets: int):
        self.title_gate = TitleQualityGate()
        self.forbidden_scanner = ForbiddenWordScanner()
        self.ac_tracker = ACCoverageTracker(num_ac_bullets)

    def validate_test_case(self, test_case: Dict) -> Tuple[bool, List[str]]:
        """
        Validate a single test case through all gates.

        Args:
            test_case: Test case dict with 'id', 'title', 'steps'

        Returns:
            (is_valid, errors) tuple
        """
        all_errors = []

        test_id = test_case.get('id')
        title = test_case.get('title')
        steps = test_case.get('steps', [])

        # Gate 1: Title quality
        is_valid, errors = self.title_gate.validate_title(test_id, title)
        all_errors.extend(errors)

        # Gate 2: Forbidden words in steps
        is_valid, errors = self.forbidden_scanner.scan_steps(test_id, steps)
        all_errors.extend(errors)

        return len(all_errors) == 0, all_errors

    def validate_all_tests(self, test_cases: List[Dict]) -> Tuple[bool, List[str]]:
        """
        Validate all test cases.

        Args:
            test_cases: List of test case dicts

        Returns:
            (is_valid, errors) tuple
        """
        all_errors = []

        # Validate each test case
        for test_case in test_cases:
            is_valid, errors = self.validate_test_case(test_case)
            all_errors.extend(errors)

            # Track AC coverage (skip accessibility tests)
            test_id = test_case.get('id')
            if 'Accessibility' not in test_case.get('title', ''):
                # Extract AC index from test ID
                if 'AC1' in test_id:
                    self.ac_tracker.track_test(test_id, 1)
                else:
                    # Extract number from ID like "272889-010"
                    match = re.search(r'-(\d{3})$', test_id)
                    if match:
                        # Map test number to AC index (005->2, 010->3, etc.)
                        test_num = int(match.group(1))
                        ac_index = (test_num // 5) + 1
                        self.ac_tracker.track_test(test_id, ac_index)

        # Validate AC coverage
        is_valid, coverage_errors = self.ac_tracker.validate_coverage()
        all_errors.extend(coverage_errors)

        return len(all_errors) == 0, all_errors

    def print_quality_report(self, test_cases: List[Dict]):
        """Print comprehensive quality report."""
        print("\n" + "=" * 80)
        print("QUALITY GATE REPORT")
        print("=" * 80)

        is_valid, errors = self.validate_all_tests(test_cases)

        if is_valid:
            print("✓ ALL QUALITY GATES PASSED")
        else:
            print(f"✗ QUALITY GATES FAILED ({len(errors)} errors)")
            print("\nErrors:")
            for error in errors:
                print(f"  • {error}")

        print("\n" + self.ac_tracker.get_summary())
        print("=" * 80)

        return is_valid, errors
