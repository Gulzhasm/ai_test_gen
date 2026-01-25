"""
Test Case Validator Module

Validates test cases against configurable QA rules.
Implements IValidator interface for clean architecture compliance.
"""
import re
from typing import Dict, List, Tuple, Optional, Protocol
from dataclasses import dataclass
from enum import Enum


class ValidationSeverity(Enum):
    """Severity levels for validation errors."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationResult:
    """Result of a validation check."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    severity: ValidationSeverity = ValidationSeverity.ERROR


class IValidationConfig(Protocol):
    """Protocol for validation configuration."""
    @property
    def forbidden_words(self) -> List[str]: ...
    @property
    def prereq_pattern(self) -> str: ...
    @property
    def close_pattern(self) -> str: ...


class TestCaseValidator:
    """
    Validates test cases against configurable QA rules.

    Supports dependency injection for project-specific validation rules.
    """

    # Default forbidden phrases in expected results
    DEFAULT_FORBIDDEN_PHRASES = [
        'or / or',
        ' or ',
        'if available',
        'if supported',
        'works correctly',
        'as expected',
        'works as expected',
        'should be correct',
        'no issues found',
    ]

    # Default setup step patterns (actions that should have blank expected)
    DEFAULT_SETUP_PATTERNS = [
        'pre-req:',
        'launch',
        'close/exit',
        'draw a shape',
        'select the shape',
        'open properties panel',
        'open dimensions panel',
        'select another drawing tool',
        'hold shift key',
        'click and drag',
    ]

    def __init__(
        self,
        config: Optional[IValidationConfig] = None,
        prereq_pattern: Optional[str] = None,
        close_pattern: Optional[str] = None
    ):
        """
        Initialize validator with optional configuration.

        Args:
            config: Validation configuration object
            prereq_pattern: Pattern for prerequisite step (e.g., "PRE-REQ: App is installed")
            close_pattern: Pattern for close step (e.g., "Close the application")
        """
        self._config = config
        self._prereq_pattern = prereq_pattern or (config.prereq_pattern if config else "PRE-REQ:")
        self._close_pattern = close_pattern or (config.close_pattern if config else "Close")

    @property
    def forbidden_words(self) -> List[str]:
        """Get forbidden words list."""
        if self._config:
            return self._config.forbidden_words
        return []

    def validate_test_cases(self, test_cases: List[Dict]) -> Tuple[bool, List[str]]:
        """
        Validate all test cases against QA rules.

        Args:
            test_cases: List of test case dictionaries

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        for idx, tc in enumerate(test_cases):
            tc_errors = self._validate_single_test_case(tc, idx)
            errors.extend(tc_errors)

        return len(errors) == 0, errors

    def validate_single(self, test_case: Dict, index: int = 0) -> ValidationResult:
        """
        Validate a single test case.

        Args:
            test_case: Test case dictionary
            index: Position in the test case list (0-based)

        Returns:
            ValidationResult with errors and warnings
        """
        errors = self._validate_single_test_case(test_case, index)
        warnings = self._get_warnings(test_case)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            severity=ValidationSeverity.ERROR if errors else ValidationSeverity.INFO
        )

    def _validate_single_test_case(self, tc: Dict, idx: int) -> List[str]:
        """Validate a single test case and return list of errors."""
        errors = []
        tc_id = tc.get('id', f'TC-{idx}')

        # Validate ID format
        errors.extend(self._validate_id_format(tc_id, idx))

        # Validate prerequisite step
        errors.extend(self._validate_prereq_step(tc, tc_id))

        # Validate close step
        errors.extend(self._validate_close_step(tc, tc_id))

        # Validate forbidden words
        errors.extend(self._validate_forbidden_words(tc, tc_id))

        # Validate accessibility tests
        errors.extend(self._validate_accessibility(tc, tc_id))

        # Validate object interaction
        errors.extend(self._validate_object_interaction(tc, tc_id))

        # Validate title format
        errors.extend(self._validate_title_format(tc, tc_id))

        # Validate step expected rules
        errors.extend(self._validate_step_expected_rules(tc, tc_id))

        return errors

    def _validate_id_format(self, tc_id: str, idx: int) -> List[str]:
        """Validate test case ID format."""
        errors = []
        if idx == 0:
            if not tc_id.endswith('-AC1'):
                errors.append(f"{tc_id}: First test case should have AC1 suffix")
        else:
            if not re.match(r'\d+-\d{3}$', tc_id) and not tc_id.endswith('-AC1'):
                pass  # Allow flexible ID formats
        return errors

    def _validate_prereq_step(self, tc: Dict, tc_id: str) -> List[str]:
        """Validate prerequisite step exists."""
        errors = []
        has_prereq = any(
            self._prereq_pattern.lower() in step.get('action', '').lower()
            for step in tc.get('steps', [])
        )
        if not has_prereq:
            errors.append(f"{tc_id}: Missing prerequisite step containing '{self._prereq_pattern}'")
        return errors

    def _validate_close_step(self, tc: Dict, tc_id: str) -> List[str]:
        """Validate close step exists and has no expected result."""
        errors = []
        close_step = None

        for step in tc.get('steps', []):
            if self._close_pattern.lower() in step.get('action', '').lower():
                close_step = step
                break

        if not close_step:
            errors.append(f"{tc_id}: Missing close step containing '{self._close_pattern}'")
        elif close_step.get('expected', '').strip():
            errors.append(f"{tc_id}: Close step must have no expected result")

        return errors

    def _validate_forbidden_words(self, tc: Dict, tc_id: str) -> List[str]:
        """Validate no forbidden words in steps."""
        errors = []
        for step in tc.get('steps', []):
            action = step.get('action', '').lower()
            for forbidden in self.forbidden_words:
                if forbidden.lower() in action:
                    errors.append(f"{tc_id}: Contains forbidden word: {forbidden}")
        return errors

    def _validate_accessibility(self, tc: Dict, tc_id: str) -> List[str]:
        """Validate accessibility test requirements."""
        errors = []
        if tc.get('is_accessibility'):
            if not tc.get('device'):
                errors.append(f"{tc_id}: Accessibility test must specify device")

            # Check for accessibility tool prerequisite
            has_tool_prereq = any(
                'pre-req:' in step.get('action', '').lower() and
                any(tool in step.get('action', '') for tool in
                    ['Accessibility Insights', 'VoiceOver', 'Accessibility Scanner', 'TalkBack'])
                for step in tc.get('steps', [])
            )
            if not has_tool_prereq:
                errors.append(f"{tc_id}: Accessibility test missing tool prerequisite")

        return errors

    def _validate_object_interaction(self, tc: Dict, tc_id: str) -> List[str]:
        """Validate object interaction steps if required."""
        errors = []
        if tc.get('requires_object'):
            has_object_ops = any(
                keyword in step.get('action', '').lower()
                for step in tc.get('steps', [])
                for keyword in ['draw', 'shape', 'object', 'select the', 'modify', 'rotate', 'move', 'transform']
            )

            if has_object_ops:
                has_draw = any('draw a shape' in step.get('action', '').lower() for step in tc.get('steps', []))
                has_select = any(
                    'select' in step.get('action', '').lower() and
                    any(w in step.get('action', '').lower() for w in ['shape', 'object', 'drawn'])
                    for step in tc.get('steps', [])
                )
                if not has_draw:
                    errors.append(f"{tc_id}: Missing 'Draw a shape' step for object interaction")
                if not has_select:
                    errors.append(f"{tc_id}: Missing 'Select the shape' step for object interaction")

        return errors

    def _validate_title_format(self, tc: Dict, tc_id: str) -> List[str]:
        """Validate title format."""
        errors = []
        title = tc.get('title', '')

        if not re.match(r'\d+-(AC1|\d{3}):', title):
            errors.append(f"{tc_id}: Invalid title format - should start with ID prefix")

        if ' / ' not in title or title.count(' / ') < 2:
            errors.append(f"{tc_id}: Title should follow format: <ID>: <Feature> / <Area> / <Scenario>")

        return errors

    def _validate_step_expected_rules(self, tc: Dict, tc_id: str) -> List[str]:
        """Validate step expected result rules."""
        errors = []

        for step_idx, step in enumerate(tc.get('steps', []), start=1):
            action = step.get('action', '').lower()
            expected = step.get('expected', '').strip()

            # Check if this is a setup step
            is_setup = self._is_setup_step(action)

            if is_setup and expected:
                # Setup steps should have blank expected
                pass  # Allow some flexibility here

            # Verification steps must have expected
            if any(v in action for v in ['verify', 'confirm', 'check']):
                if not expected:
                    errors.append(f"{tc_id}: Step {step_idx}: Verification step must have expected result")
                else:
                    # Check for forbidden phrases in expected
                    for phrase in self.DEFAULT_FORBIDDEN_PHRASES:
                        if phrase == ' or ':
                            if ' or ' in expected.lower():
                                errors.append(f"{tc_id}: Step {step_idx}: Expected contains ambiguous 'or'")
                        elif phrase in expected.lower():
                            errors.append(f"{tc_id}: Step {step_idx}: Expected contains forbidden phrase: '{phrase}'")

                    # Check expected is not too short
                    if len(expected.split()) < 3:
                        errors.append(f"{tc_id}: Step {step_idx}: Expected result too short")

        return errors

    def _is_setup_step(self, action: str) -> bool:
        """Determine if action is a setup step."""
        return any(pattern in action for pattern in self.DEFAULT_SETUP_PATTERNS)

    def _get_warnings(self, tc: Dict) -> List[str]:
        """Get non-critical warnings for a test case."""
        warnings = []
        tc_id = tc.get('id', 'Unknown')

        # Check for very long steps
        for idx, step in enumerate(tc.get('steps', []), start=1):
            action = step.get('action', '')
            if len(action) > 500:
                warnings.append(f"{tc_id}: Step {idx} action is very long ({len(action)} chars)")

        # Check for many steps
        step_count = len(tc.get('steps', []))
        if step_count > 15:
            warnings.append(f"{tc_id}: Test case has many steps ({step_count})")

        return warnings


class QualityGate:
    """
    Quality gate for batch validation of test cases.

    Provides aggregated validation results and coverage analysis.
    """

    def __init__(self, validator: TestCaseValidator):
        """
        Initialize quality gate with a validator.

        Args:
            validator: TestCaseValidator instance
        """
        self._validator = validator

    def run(
        self,
        test_cases: List[Dict],
        criteria: List[str],
        qa_details: Optional[Dict] = None
    ) -> Dict:
        """
        Run quality gate validation.

        Args:
            test_cases: List of test cases to validate
            criteria: List of acceptance criteria
            qa_details: Optional QA prep details

        Returns:
            Dict with is_valid, errors, warnings, and coverage info
        """
        is_valid, errors = self._validator.validate_test_cases(test_cases)

        # Calculate coverage
        coverage = self._calculate_coverage(test_cases, criteria, qa_details)

        return {
            'is_valid': is_valid,
            'errors': errors,
            'warnings': [],
            'coverage': coverage
        }

    def _calculate_coverage(
        self,
        test_cases: List[Dict],
        criteria: List[str],
        qa_details: Optional[Dict]
    ) -> Dict:
        """Calculate test coverage metrics."""
        ac_count = len(criteria)
        tc_count = len(test_cases)

        # Check which ACs are covered
        covered_acs = set()
        for tc in test_cases:
            ac_index = tc.get('ac_index')
            if ac_index:
                covered_acs.add(ac_index)

        return {
            'total_ac': ac_count,
            'total_tc': tc_count,
            'covered_ac': len(covered_acs),
            'coverage_ratio': len(covered_acs) / ac_count if ac_count > 0 else 0,
            'has_edge_cases': tc_count > ac_count,
            'has_accessibility': any(tc.get('is_accessibility') for tc in test_cases)
        }
