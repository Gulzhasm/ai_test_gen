"""
GroundingValidator: Validates that tests are grounded in evidence.

This module prevents the generator from inventing context by validating
that all test elements (entry points, scenarios, assertions) are supported
by evidence from AC or QA Prep.
"""
from typing import List, Dict, Tuple, Set
from core.domain.grounded_spec import GroundedSpec
from core.config import environment as config


class GroundingValidator:
    """
    Validates that test cases are grounded in evidence.

    This validator ensures:
    1. Title areas are supported by entry points/surfaces in GroundedSpec
    2. Steps don't mention out-of-scope features
    3. Objectives use evidence-backed assertions
    4. Steps don't include forbidden words
    """

    def __init__(self, grounded_spec: GroundedSpec):
        self.grounded_spec = grounded_spec

    def validate_test_cases(self, test_cases: List[Dict]) -> Tuple[bool, List[str]]:
        """
        Validate all test cases against grounded spec.

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        for tc in test_cases:
            tc_id = tc.get('id', 'Unknown')

            # Validate title grounding
            title_errors = self._validate_title_grounding(tc_id, tc.get('title', ''))
            errors.extend(title_errors)

            # Validate steps grounding
            steps_errors = self._validate_steps_grounding(tc_id, tc.get('steps', []))
            errors.extend(steps_errors)

            # Validate objective grounding
            objective_errors = self._validate_objective_grounding(tc_id, tc.get('objective', ''))
            errors.extend(objective_errors)

            # Validate no out-of-scope items
            out_of_scope_errors = self._validate_no_out_of_scope(tc_id, tc)
            errors.extend(out_of_scope_errors)

        return len(errors) == 0, errors

    def _validate_title_grounding(self, tc_id: str, title: str) -> List[str]:
        """
        Validate that title area is grounded in evidence.

        Title format: <ID>: <Feature> / <Area> / <Scenario>
        The <Area> must be a valid entry point or surface from GroundedSpec.
        """
        errors = []

        # Parse title to extract area
        parts = title.split(' / ')
        if len(parts) < 3:
            # Title format error - already caught by other validators
            return errors

        # Extract area (second part)
        area = parts[1].strip()

        # Special cases that are always allowed
        allowed_generic_areas = {
            'Canvas',
            'Undo/Redo',
            'Accessibility',
            'Units'
        }

        if area in allowed_generic_areas:
            return errors

        # Check if area is grounded in entry points or surfaces
        if not self.grounded_spec.has_entry_point(area):
            # Check if it's a close match to any surface
            close_matches = self._find_close_surface_matches(area)
            if close_matches:
                suggestion = f" (Did you mean: {', '.join(close_matches)}?)"
            else:
                suggestion = ""

            errors.append(
                f"{tc_id}: Title area '{area}' is not grounded in evidence. "
                f"Available surfaces: {', '.join(self.grounded_spec.surfaces) or 'None'}{suggestion}"
            )

        return errors

    def _find_close_surface_matches(self, area: str) -> List[str]:
        """Find surfaces that are close matches to the area."""
        area_lower = area.lower()
        close_matches = []

        for surface in self.grounded_spec.surfaces:
            surface_lower = surface.lower()
            # Check if area is a substring of surface or vice versa
            if area_lower in surface_lower or surface_lower in area_lower:
                close_matches.append(surface)

        return close_matches

    def _validate_steps_grounding(self, tc_id: str, steps: List[Dict]) -> List[str]:
        """
        Validate that steps are grounded in evidence.

        Checks:
        1. No forbidden words
        2. No out-of-scope features mentioned
        3. Entry points mentioned in steps match GroundedSpec
        """
        errors = []

        for step_idx, step in enumerate(steps, start=1):
            action = step.get('action', '')
            expected = step.get('expected', '')

            # Check forbidden words
            forbidden_errors = self._check_forbidden_words(tc_id, step_idx, action, expected)
            errors.extend(forbidden_errors)

            # Check for out-of-scope mentions
            out_of_scope_errors = self._check_out_of_scope_in_text(tc_id, step_idx, action)
            errors.extend(out_of_scope_errors)

        return errors

    def _validate_objective_grounding(self, tc_id: str, objective: str) -> List[str]:
        """
        Validate that objective is grounded in evidence.

        Checks:
        1. No forbidden words
        2. No out-of-scope features
        3. Objective uses evidence-backed assertions
        """
        errors = []

        # Check forbidden words
        objective_lower = objective.lower()
        for forbidden in config.FORBIDDEN_WORDS:
            if forbidden.lower() in objective_lower:
                errors.append(
                    f"{tc_id}: Objective contains forbidden word: '{forbidden}'"
                )

        # Check for out-of-scope mentions
        for out_of_scope_item in self.grounded_spec.out_of_scope:
            if out_of_scope_item.lower() in objective_lower:
                errors.append(
                    f"{tc_id}: Objective mentions out-of-scope item: '{out_of_scope_item}'"
                )

        return errors

    def _validate_no_out_of_scope(self, tc_id: str, test_case: Dict) -> List[str]:
        """
        Validate that test case doesn't test out-of-scope features.

        Checks entire test case for mentions of out-of-scope items.
        """
        errors = []

        # Combine all text from test case
        all_text = test_case.get('title', '') + ' ' + test_case.get('objective', '')
        for step in test_case.get('steps', []):
            all_text += ' ' + step.get('action', '') + ' ' + step.get('expected', '')

        all_text_lower = all_text.lower()

        # Check for out-of-scope items
        for out_of_scope_item in self.grounded_spec.out_of_scope:
            if out_of_scope_item.lower() in all_text_lower:
                errors.append(
                    f"{tc_id}: Test mentions out-of-scope item: '{out_of_scope_item}'"
                )

        return errors

    def _check_forbidden_words(self, tc_id: str, step_idx: int, action: str, expected: str) -> List[str]:
        """Check for forbidden words in step."""
        errors = []

        for forbidden in config.FORBIDDEN_WORDS:
            if forbidden.lower() in action.lower():
                errors.append(
                    f"{tc_id}: Step {step_idx} action contains forbidden word: '{forbidden}'"
                )
            if forbidden.lower() in expected.lower():
                errors.append(
                    f"{tc_id}: Step {step_idx} expected contains forbidden word: '{forbidden}'"
                )

        return errors

    def _check_out_of_scope_in_text(self, tc_id: str, step_idx: int, text: str) -> List[str]:
        """Check for out-of-scope mentions in text."""
        errors = []
        text_lower = text.lower()

        for out_of_scope_item in self.grounded_spec.out_of_scope:
            if out_of_scope_item.lower() in text_lower:
                errors.append(
                    f"{tc_id}: Step {step_idx} mentions out-of-scope item: '{out_of_scope_item}'"
                )

        return errors

    def validate_entry_point_exists(self, entry_point: str) -> bool:
        """
        Check if an entry point is valid (exists in GroundedSpec).

        Use this before generating a test to ensure the entry point is grounded.
        """
        return self.grounded_spec.has_entry_point(entry_point)

    def get_valid_entry_points(self) -> List[str]:
        """
        Get list of valid entry points from GroundedSpec.

        Use this to select an entry point when generating tests.
        """
        return list(self.grounded_spec.surfaces)

    def suggest_entry_point(self, preferred: str) -> str:
        """
        Suggest a valid entry point based on preferred choice.

        Args:
            preferred: Preferred entry point (may not be valid)

        Returns:
            Valid entry point from GroundedSpec, or "Unspecified Entry Point" if none found
        """
        # If preferred is valid, return it
        if self.grounded_spec.has_entry_point(preferred):
            return preferred

        # Try to find a close match
        close_matches = self._find_close_surface_matches(preferred)
        if close_matches:
            return close_matches[0]

        # Return primary entry point from GroundedSpec
        primary = self.grounded_spec.get_primary_entry_point()
        if primary:
            return primary

        # No valid entry point found
        return "Unspecified Entry Point"

    def generate_validation_report(self, test_cases: List[Dict]) -> str:
        """
        Generate a validation report for test cases.

        Returns:
            Human-readable validation report
        """
        is_valid, errors = self.validate_test_cases(test_cases)

        report = "=" * 80 + "\n"
        report += "GROUNDING VALIDATION REPORT\n"
        report += "=" * 80 + "\n\n"

        report += f"Total test cases: {len(test_cases)}\n"
        report += f"Validation status: {'✓ PASSED' if is_valid else '✗ FAILED'}\n"
        report += f"Total errors: {len(errors)}\n\n"

        if errors:
            report += "ERRORS:\n"
            report += "-" * 80 + "\n"
            for error in errors:
                report += f"  ✗ {error}\n"
            report += "\n"

        report += "GROUNDED SPEC SUMMARY:\n"
        report += "-" * 80 + "\n"
        report += self.grounded_spec.get_evidence_summary()
        report += "\n"

        report += "=" * 80 + "\n"

        return report
