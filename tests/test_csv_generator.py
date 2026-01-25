"""
Unit tests for CSV Generator module.

Tests ADO-ready CSV generation functionality.
"""
import pytest
import sys
import tempfile
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.export import CSVGenerator, CSVConfig


class TestCSVConfig:
    """Test CSVConfig dataclass."""

    def test_config_creation(self):
        """Test CSVConfig instantiation."""
        config = CSVConfig(
            area_path="Project\\Area",
            assigned_to="user@example.com",
            default_state="Design"
        )
        assert config.area_path == "Project\\Area"
        assert config.assigned_to == "user@example.com"
        assert config.default_state == "Design"

    def test_config_default_state(self):
        """Test CSVConfig default state value."""
        config = CSVConfig(
            area_path="Area",
            assigned_to="user@test.com"
        )
        assert config.default_state == "Design"


class TestCSVGenerator:
    """Test CSVGenerator functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = CSVConfig(
            area_path="TestProject\\TestArea",
            assigned_to="test@example.com",
            default_state="Design"
        )
        self.generator = CSVGenerator(self.config)

    def _create_test_case(self, tc_id: str = "12345-AC1") -> dict:
        """Create a test case for testing."""
        return {
            'id': tc_id,
            'title': f"{tc_id}: Feature / Area / Scenario",
            'steps': [
                {'action': 'PRE-REQ: Application is installed', 'expected': ''},
                {'action': 'Launch the application', 'expected': ''},
                {'action': 'Verify the feature', 'expected': 'Feature works correctly'},
                {'action': 'Close the application', 'expected': ''}
            ]
        }

    def test_generator_initialization(self):
        """Test generator initializes with config values."""
        assert self.generator.area_path == "TestProject\\TestArea"
        assert self.generator.assigned_to == "test@example.com"
        assert self.generator.default_state == "Design"

    def test_generator_without_config(self):
        """Test generator works without config."""
        generator = CSVGenerator()
        assert generator.area_path == ""
        assert generator.assigned_to == ""
        assert generator.default_state == "Design"

    def test_headers_correct(self):
        """Test CSV headers are correct."""
        expected_headers = [
            'ID', 'Work Item Type', 'Title', 'TestStep',
            'Step Action', 'Step Expected', 'Area Path', 'AssignedTo', 'State'
        ]
        assert self.generator.HEADERS == expected_headers

    def test_generate_csv_string(self):
        """Test generating CSV as string."""
        test_cases = [self._create_test_case()]
        csv_content = self.generator.generate_csv_string(test_cases)

        assert isinstance(csv_content, str)
        assert 'ID,Work Item Type,Title' in csv_content
        assert 'Test Case' in csv_content
        assert self.config.area_path in csv_content

    def test_generate_csv_file(self):
        """Test generating CSV file."""
        test_cases = [self._create_test_case()]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = f.name

        try:
            self.generator.generate_csv(test_cases, output_path)

            assert os.path.exists(output_path)
            with open(output_path, 'r') as f:
                content = f.read()

            assert 'Test Case' in content
            assert 'Feature / Area / Scenario' in content
        finally:
            if os.path.exists(output_path):
                os.remove(output_path)

    def test_clean_text_removes_newlines(self):
        """Test newline removal from text."""
        text_with_newlines = "Line 1\nLine 2\r\nLine 3"
        cleaned = self.generator._clean_text(text_with_newlines)

        assert '\n' not in cleaned
        assert '\r' not in cleaned
        assert 'Line 1 Line 2 Line 3' == cleaned

    def test_clean_text_empty(self):
        """Test cleaning empty text."""
        assert self.generator._clean_text("") == ""
        assert self.generator._clean_text(None) == ""

    def test_format_csv_value_empty(self):
        """Test formatting empty CSV value."""
        assert self.generator._format_csv_value("") == ""
        assert self.generator._format_csv_value(None) == ""

    def test_format_csv_value_quotes_commas(self):
        """Test formatting value with commas is properly quoted."""
        value = "Text, with, commas"
        formatted = self.generator._format_csv_value(value)
        # CSV values with commas should be quoted
        assert formatted.startswith('"') or ',' not in formatted

    def test_multiple_test_cases(self):
        """Test generating CSV with multiple test cases."""
        test_cases = [
            self._create_test_case("12345-AC1"),
            self._create_test_case("12345-005"),
            self._create_test_case("12345-010")
        ]
        csv_content = self.generator.generate_csv_string(test_cases)

        # Should have header + 3 test case headers + all steps
        lines = csv_content.strip().split('\n')
        header_line = lines[0]

        # Count 'Test Case' occurrences (one per test case)
        test_case_count = csv_content.count('Test Case')
        assert test_case_count == 3

    def test_step_numbering(self):
        """Test step numbers are correct."""
        test_cases = [self._create_test_case()]
        csv_content = self.generator.generate_csv_string(test_cases)
        lines = csv_content.strip().split('\n')

        # Find step rows (have numbers in TestStep column)
        step_numbers = []
        for line in lines[2:]:  # Skip header and test case header
            parts = line.split(',')
            if len(parts) > 3 and parts[3].strip('"'):
                step_numbers.append(int(parts[3].strip('"')))

        assert step_numbers == [1, 2, 3, 4]

    def test_area_path_in_header_row_only(self):
        """Test area path is only in header row, not step rows."""
        test_cases = [self._create_test_case()]
        csv_content = self.generator.generate_csv_string(test_cases)
        lines = csv_content.strip().split('\n')

        # Header line (column names)
        # Test case header line should have area path
        # Step lines should not have area path

        area_path_count = csv_content.count(self.config.area_path)
        assert area_path_count == 1  # Only in test case header row


class TestCSVGeneratorEdgeCases:
    """Test edge cases for CSV generator."""

    def test_empty_test_cases(self):
        """Test generating CSV with no test cases."""
        generator = CSVGenerator()
        csv_content = generator.generate_csv_string([])

        lines = csv_content.strip().split('\n')
        assert len(lines) == 1  # Only header

    def test_test_case_without_steps(self):
        """Test generating CSV with test case without steps."""
        generator = CSVGenerator()
        tc = {'id': '12345-AC1', 'title': 'Test', 'steps': []}
        csv_content = generator.generate_csv_string([tc])

        assert 'Test Case' in csv_content
        assert ',Test,' in csv_content

    def test_special_characters_in_text(self):
        """Test handling of special characters."""
        generator = CSVGenerator()
        tc = {
            'id': '12345-AC1',
            'title': 'Test with "quotes" and, commas',
            'steps': [
                {'action': 'Step with <html> tags', 'expected': ''}
            ]
        }
        csv_content = generator.generate_csv_string([tc])

        assert 'Test with' in csv_content
        # Should handle special chars without breaking CSV
        assert isinstance(csv_content, str)

    def test_unicode_characters(self):
        """Test handling of unicode characters."""
        generator = CSVGenerator()
        tc = {
            'id': '12345-AC1',
            'title': 'Test with émojis 🎉 and ñ',
            'steps': [
                {'action': 'Stëp with ünicode', 'expected': 'Rësult'}
            ]
        }
        csv_content = generator.generate_csv_string([tc])

        assert isinstance(csv_content, str)
        # Should preserve unicode
        assert 'ünicode' in csv_content or 'unicode' in csv_content.lower()
