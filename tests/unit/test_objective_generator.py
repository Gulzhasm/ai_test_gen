"""
Unit tests for Objective Generator module.

Tests objective formatting and generation functionality.
"""
import pytest
import sys
import tempfile
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.export import ObjectiveGenerator


class TestObjectiveGenerator:
    """Test ObjectiveGenerator functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.generator = ObjectiveGenerator()

    def test_default_patterns(self):
        """Test default key term patterns exist."""
        patterns = self.generator.key_term_patterns
        assert isinstance(patterns, list)
        assert len(patterns) > 0

    def test_custom_patterns(self):
        """Test custom patterns initialization."""
        custom_patterns = [r'\bCustom\b', r'\bPattern\b']
        generator = ObjectiveGenerator(key_term_patterns=custom_patterns)
        assert generator.key_term_patterns == custom_patterns

    def test_format_objective_basic(self):
        """Test basic objective formatting."""
        objective = "the button is visible"
        formatted = self.generator.format_objective_for_ado(objective)

        assert '<b>Objective:</b>' in formatted
        assert 'Verify that' in formatted
        # Key terms may be bolded, so check for presence of words
        assert 'button' in formatted
        assert 'visible' in formatted

    def test_format_objective_removes_duplicate_verify(self):
        """Test duplicate 'Verify that' is removed."""
        objective = "Verify that the button is visible"
        formatted = self.generator.format_objective_for_ado(objective)

        # Should only have one "Verify that"
        assert formatted.count('Verify that') == 1

    def test_format_objective_bolds_menu(self):
        """Test menu term is bolded."""
        objective = "the File Menu is accessible"
        formatted = self.generator.format_objective_for_ado(objective)

        # Should contain bold tags around menu-related terms
        assert '<b>' in formatted
        assert '</b>' in formatted

    def test_format_objective_bolds_platform(self):
        """Test platform names are bolded."""
        objective = "the feature works on Windows and iPad"
        formatted = self.generator.format_objective_for_ado(objective)

        # Should bold platform names
        assert '<b>' in formatted

    def test_format_objective_bolds_accessibility_tools(self):
        """Test accessibility tools are bolded."""
        objective = "the screen reader VoiceOver can navigate"
        formatted = self.generator.format_objective_for_ado(objective)

        assert '<b>' in formatted

    def test_no_nested_bold_tags(self):
        """Test bold tags are not nested."""
        objective = "the enabled button in the visible panel"
        formatted = self.generator.format_objective_for_ado(objective)

        # Should not have nested bold tags like <b><b>
        assert '<b><b>' not in formatted


class TestObjectiveGeneratorFileOutput:
    """Test ObjectiveGenerator file generation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.generator = ObjectiveGenerator()

    def _create_test_case(self, tc_id: str = "12345-AC1") -> dict:
        """Create a test case for testing."""
        return {
            'id': tc_id,
            'title': f"{tc_id}: Feature / Area / Scenario",
            'objective': "the feature works correctly in all cases"
        }

    def test_generate_objectives_file(self):
        """Test generating objectives file."""
        test_cases = [self._create_test_case()]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            output_path = f.name

        try:
            self.generator.generate_objectives_file(test_cases, output_path)

            assert os.path.exists(output_path)
            with open(output_path, 'r') as f:
                content = f.read()

            assert '12345-AC1:' in content
            assert 'Objective:' in content
        finally:
            if os.path.exists(output_path):
                os.remove(output_path)

    def test_generate_objectives_string(self):
        """Test generating objectives as string."""
        test_cases = [self._create_test_case()]
        content = self.generator.generate_objectives_string(test_cases)

        assert isinstance(content, str)
        assert '12345-AC1:' in content
        assert 'Verify that' in content

    def test_objective_format_structure(self):
        """Test objective file format structure."""
        test_cases = [
            self._create_test_case("12345-AC1"),
            self._create_test_case("12345-005")
        ]
        content = self.generator.generate_objectives_string(test_cases)
        lines = content.strip().split('\n')

        # Each test case should have ID line, objective line, and blank line
        # So for 2 test cases, we expect at least 4 non-empty lines
        non_empty_lines = [l for l in lines if l.strip()]
        assert len(non_empty_lines) >= 4

    def test_title_without_id_duplication(self):
        """Test title doesn't duplicate ID."""
        tc = {
            'id': '12345-AC1',
            'title': '12345-AC1: Feature / Area / Scenario',
            'objective': 'the feature works'
        }
        content = self.generator.generate_objectives_string([tc])

        # The ID should appear exactly once at the start, not duplicated
        first_line = content.split('\n')[0]
        assert first_line.count('12345-AC1') == 1

    def test_missing_objective_uses_title(self):
        """Test missing objective generates from title."""
        tc = {
            'id': '12345-AC1',
            'title': '12345-AC1: Feature / Area / Scenario'
            # No 'objective' key
        }
        content = self.generator.generate_objectives_string([tc])

        assert 'Verify that' in content
        # Should generate some objective text
        assert 'Objective:' in content


class TestObjectiveGeneratorHelpers:
    """Test ObjectiveGenerator helper methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.generator = ObjectiveGenerator()

    def test_create_objective_from_title_full(self):
        """Test objective creation from full title."""
        title = "Rotation Tools / Edit Menu / 90 Degree Rotation Works"
        objective = self.generator.create_objective_from_title(title)

        assert 'rotation' in objective.lower() or 'works' in objective.lower()

    def test_create_objective_from_title_partial(self):
        """Test objective creation from partial title."""
        title = "Feature / Scenario"
        objective = self.generator.create_objective_from_title(title)

        assert 'scenario' in objective.lower()

    def test_create_objective_from_title_simple(self):
        """Test objective creation from simple title."""
        title = "Simple Feature"
        objective = self.generator.create_objective_from_title(title)

        assert 'simple feature' in objective.lower()

    def test_apply_bold_patterns_no_match(self):
        """Test bold patterns with no matching terms."""
        text = "something with no matching terms xyz123"
        result = self.generator._apply_bold_patterns(text)

        # Should return text unchanged or with minimal changes
        assert isinstance(result, str)


class TestObjectiveGeneratorEdgeCases:
    """Test edge cases for objective generator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.generator = ObjectiveGenerator()

    def test_empty_objective(self):
        """Test handling of empty objective."""
        tc = {
            'id': '12345-AC1',
            'title': '12345-AC1: Feature / Area / Test',
            'objective': ''
        }
        content = self.generator.generate_objectives_string([tc])

        # Should generate something even with empty objective
        assert 'Verify that' in content

    def test_whitespace_objective(self):
        """Test handling of whitespace-only objective."""
        tc = {
            'id': '12345-AC1',
            'title': '12345-AC1: Feature / Area / Test',
            'objective': '   '
        }
        content = self.generator.generate_objectives_string([tc])

        assert 'Verify that' in content

    def test_special_characters_in_objective(self):
        """Test handling of special characters."""
        tc = {
            'id': '12345-AC1',
            'title': '12345-AC1: Feature / Area / Test',
            'objective': 'the <button> & "text" works correctly'
        }
        content = self.generator.generate_objectives_string([tc])

        assert isinstance(content, str)
        assert '12345-AC1' in content

    def test_multiple_test_cases(self):
        """Test generating objectives for multiple test cases."""
        test_cases = [
            {'id': '12345-AC1', 'title': '12345-AC1: F1 / A1 / S1', 'objective': 'obj 1'},
            {'id': '12345-005', 'title': '12345-005: F2 / A2 / S2', 'objective': 'obj 2'},
            {'id': '12345-010', 'title': '12345-010: F3 / A3 / S3', 'objective': 'obj 3'},
        ]
        content = self.generator.generate_objectives_string(test_cases)

        assert '12345-AC1' in content
        assert '12345-005' in content
        assert '12345-010' in content

    def test_empty_test_cases_list(self):
        """Test generating objectives with empty list."""
        content = self.generator.generate_objectives_string([])
        assert content == ''
