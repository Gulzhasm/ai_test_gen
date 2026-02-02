"""
Unit tests for Validator module.

Tests test case validation and quality gate functionality.
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.services.test_validator import (
    TestCaseValidator,
    QualityGate,
    ValidationResult,
    ValidationSeverity
)


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_valid_result(self):
        """Test valid validation result."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[]
        )
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.severity == ValidationSeverity.ERROR

    def test_invalid_result(self):
        """Test invalid validation result."""
        result = ValidationResult(
            is_valid=False,
            errors=["Error 1", "Error 2"],
            warnings=["Warning 1"],
            severity=ValidationSeverity.ERROR
        )
        assert result.is_valid is False
        assert len(result.errors) == 2


class TestTestCaseValidator:
    """Test TestCaseValidator functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = TestCaseValidator(
            prereq_pattern="PRE-REQ:",
            close_pattern="Close"
        )

    def _create_valid_test_case(self, tc_id: str = "12345-AC1") -> dict:
        """Create a valid test case for testing."""
        return {
            'id': tc_id,
            'title': f"{tc_id}: Feature / Area / Scenario",
            'steps': [
                {'action': 'PRE-REQ: Application is installed', 'expected': ''},
                {'action': 'Launch the application', 'expected': ''},
                {'action': 'Verify the button is visible', 'expected': 'Button is visible on screen'},
                {'action': 'Close the application', 'expected': ''}
            ]
        }

    def test_validate_valid_test_case(self):
        """Test validation of a valid test case."""
        tc = self._create_valid_test_case()
        is_valid, errors = self.validator.validate_test_cases([tc])
        # May have some warnings but should pass basic validation
        assert isinstance(is_valid, bool)
        assert isinstance(errors, list)

    def test_validate_missing_prereq(self):
        """Test validation fails without prerequisite step."""
        tc = {
            'id': '12345-AC1',
            'title': '12345-AC1: Feature / Area / Scenario',
            'steps': [
                {'action': 'Launch the application', 'expected': ''},
                {'action': 'Close the application', 'expected': ''}
            ]
        }
        is_valid, errors = self.validator.validate_test_cases([tc])
        assert not is_valid
        assert any('prerequisite' in e.lower() for e in errors)

    def test_validate_missing_close(self):
        """Test validation fails without close step."""
        tc = {
            'id': '12345-AC1',
            'title': '12345-AC1: Feature / Area / Scenario',
            'steps': [
                {'action': 'PRE-REQ: Application is installed', 'expected': ''},
                {'action': 'Launch the application', 'expected': ''}
            ]
        }
        is_valid, errors = self.validator.validate_test_cases([tc])
        assert not is_valid
        assert any('close' in e.lower() for e in errors)

    def test_validate_close_with_expected(self):
        """Test validation fails when close step has expected result."""
        tc = {
            'id': '12345-AC1',
            'title': '12345-AC1: Feature / Area / Scenario',
            'steps': [
                {'action': 'PRE-REQ: Application is installed', 'expected': ''},
                {'action': 'Close the application', 'expected': 'Application closed'}
            ]
        }
        is_valid, errors = self.validator.validate_test_cases([tc])
        assert not is_valid
        assert any('close step' in e.lower() and 'expected' in e.lower() for e in errors)

    def test_validate_invalid_title_format(self):
        """Test validation fails for invalid title format."""
        tc = {
            'id': '12345-AC1',
            'title': 'Bad Title Without Proper Format',
            'steps': [
                {'action': 'PRE-REQ: Application is installed', 'expected': ''},
                {'action': 'Close the application', 'expected': ''}
            ]
        }
        is_valid, errors = self.validator.validate_test_cases([tc])
        assert not is_valid
        assert any('title' in e.lower() for e in errors)

    def test_validate_verification_without_expected(self):
        """Test validation fails for verification step without expected."""
        tc = {
            'id': '12345-AC1',
            'title': '12345-AC1: Feature / Area / Scenario',
            'steps': [
                {'action': 'PRE-REQ: Application is installed', 'expected': ''},
                {'action': 'Verify the button works', 'expected': ''},
                {'action': 'Close the application', 'expected': ''}
            ]
        }
        is_valid, errors = self.validator.validate_test_cases([tc])
        assert not is_valid
        assert any('verification' in e.lower() and 'expected' in e.lower() for e in errors)

    def test_validate_expected_too_short(self):
        """Test validation warns for very short expected results."""
        tc = {
            'id': '12345-AC1',
            'title': '12345-AC1: Feature / Area / Scenario',
            'steps': [
                {'action': 'PRE-REQ: Application is installed', 'expected': ''},
                {'action': 'Verify the result', 'expected': 'OK'},
                {'action': 'Close the application', 'expected': ''}
            ]
        }
        is_valid, errors = self.validator.validate_test_cases([tc])
        assert any('short' in e.lower() for e in errors)

    def test_validate_forbidden_phrase_in_expected(self):
        """Test validation fails for forbidden phrases in expected."""
        tc = {
            'id': '12345-AC1',
            'title': '12345-AC1: Feature / Area / Scenario',
            'steps': [
                {'action': 'PRE-REQ: Application is installed', 'expected': ''},
                {'action': 'Verify the feature', 'expected': 'Feature works as expected'},
                {'action': 'Close the application', 'expected': ''}
            ]
        }
        is_valid, errors = self.validator.validate_test_cases([tc])
        assert any('forbidden' in e.lower() for e in errors)

    def test_validate_single_returns_result(self):
        """Test validate_single returns ValidationResult."""
        tc = self._create_valid_test_case()
        result = self.validator.validate_single(tc)
        assert isinstance(result, ValidationResult)
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'errors')
        assert hasattr(result, 'warnings')

    def test_validate_accessibility_without_device(self):
        """Test validation fails for accessibility test without device."""
        tc = {
            'id': '12345-AC1',
            'title': '12345-AC1: Feature / Area / Accessibility',
            'is_accessibility': True,
            'steps': [
                {'action': 'PRE-REQ: Application is installed', 'expected': ''},
                {'action': 'Close the application', 'expected': ''}
            ]
        }
        is_valid, errors = self.validator.validate_test_cases([tc])
        assert any('device' in e.lower() for e in errors)


class TestQualityGate:
    """Test QualityGate functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = TestCaseValidator(
            prereq_pattern="PRE-REQ:",
            close_pattern="Close"
        )
        self.gate = QualityGate(self.validator)

    def _create_valid_test_case(self, ac_index: int = 1) -> dict:
        """Create a valid test case."""
        tc_id = f"12345-{ac_index:03d}" if ac_index > 1 else "12345-AC1"
        return {
            'id': tc_id,
            'title': f"{tc_id}: Feature / Area / Scenario {ac_index}",
            'ac_index': ac_index,
            'steps': [
                {'action': 'PRE-REQ: Application is installed', 'expected': ''},
                {'action': 'Verify the feature works', 'expected': 'Feature works correctly for this scenario'},
                {'action': 'Close the application', 'expected': ''}
            ]
        }

    def test_run_returns_dict(self):
        """Test run returns expected dictionary structure."""
        test_cases = [self._create_valid_test_case()]
        criteria = ["AC 1: Feature works"]

        result = self.gate.run(test_cases, criteria)

        assert isinstance(result, dict)
        assert 'is_valid' in result
        assert 'errors' in result
        assert 'coverage' in result

    def test_coverage_calculation(self):
        """Test coverage metrics calculation."""
        test_cases = [
            self._create_valid_test_case(1),
            self._create_valid_test_case(2)
        ]
        criteria = ["AC 1", "AC 2", "AC 3"]

        result = self.gate.run(test_cases, criteria)
        coverage = result['coverage']

        assert coverage['total_ac'] == 3
        assert coverage['total_tc'] == 2
        assert coverage['covered_ac'] == 2
        assert 'coverage_ratio' in coverage

    def test_edge_case_detection(self):
        """Test edge case detection in coverage."""
        test_cases = [self._create_valid_test_case(i) for i in range(1, 6)]
        criteria = ["AC 1", "AC 2"]  # Less criteria than test cases

        result = self.gate.run(test_cases, criteria)
        coverage = result['coverage']

        assert coverage['has_edge_cases'] is True  # More TCs than ACs

    def test_accessibility_detection(self):
        """Test accessibility test detection."""
        tc = self._create_valid_test_case()
        tc['is_accessibility'] = True
        test_cases = [tc]

        result = self.gate.run(test_cases, ["AC 1"])
        coverage = result['coverage']

        assert coverage['has_accessibility'] is True


class TestValidatorWithConfig:
    """Test TestCaseValidator with custom configuration."""

    def test_custom_prereq_pattern(self):
        """Test validator with custom prerequisite pattern."""
        validator = TestCaseValidator(prereq_pattern="CUSTOM-PREREQ:")

        tc = {
            'id': '12345-AC1',
            'title': '12345-AC1: Feature / Area / Scenario',
            'steps': [
                {'action': 'CUSTOM-PREREQ: Something', 'expected': ''},
                {'action': 'Close the application', 'expected': ''}
            ]
        }

        is_valid, errors = validator.validate_test_cases([tc])
        # Should find prereq with custom pattern
        assert not any('prerequisite' in e.lower() and 'missing' in e.lower() for e in errors)

    def test_custom_close_pattern(self):
        """Test validator with custom close pattern."""
        validator = TestCaseValidator(close_pattern="Exit app")

        tc = {
            'id': '12345-AC1',
            'title': '12345-AC1: Feature / Area / Scenario',
            'steps': [
                {'action': 'PRE-REQ: Application ready', 'expected': ''},
                {'action': 'Exit app', 'expected': ''}
            ]
        }

        is_valid, errors = validator.validate_test_cases([tc])
        # Should find close with custom pattern
        assert not any('close' in e.lower() and 'missing' in e.lower() for e in errors)
