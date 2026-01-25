"""
CSV Generator Module

Generates ADO-ready CSV files with configurable column structure.
Supports dependency injection for project-specific settings.
"""
import csv
import io
from typing import Dict, List, Optional, Protocol
from dataclasses import dataclass


@dataclass
class CSVConfig:
    """Configuration for CSV generation."""
    area_path: str
    assigned_to: str
    default_state: str = "Design"


class ICSVConfig(Protocol):
    """Protocol for CSV configuration."""
    @property
    def area_path(self) -> str: ...
    @property
    def assigned_to(self) -> str: ...
    @property
    def default_state(self) -> str: ...


class CSVGenerator:
    """
    Generates ADO-ready CSV files.

    Supports configurable area path, assignee, and state via dependency injection.
    """

    # CSV column headers (ADO format)
    HEADERS = [
        'ID', 'Work Item Type', 'Title', 'TestStep',
        'Step Action', 'Step Expected', 'Area Path', 'AssignedTo', 'State'
    ]

    def __init__(self, config: Optional[ICSVConfig] = None):
        """
        Initialize CSV generator with optional configuration.

        Args:
            config: Configuration object with area_path, assigned_to, default_state
        """
        self._config = config
        self._area_path = config.area_path if config else ""
        self._assigned_to = config.assigned_to if config else ""
        self._default_state = config.default_state if config else "Design"

    @property
    def area_path(self) -> str:
        """Get area path for test cases."""
        return self._area_path

    @property
    def assigned_to(self) -> str:
        """Get default assignee."""
        return self._assigned_to

    @property
    def default_state(self) -> str:
        """Get default test case state."""
        return self._default_state

    def generate_csv(self, test_cases: List[Dict], output_file: str) -> None:
        """
        Generate ADO-ready CSV with exact column structure.

        CSV Structure:
        - One header row per test case (Work Item Type = Test Case)
        - Followed by step-per-row entries
        - Metadata columns blank on step rows
        - Plain text only (ADO-safe)
        - Newlines in text are replaced with spaces

        Args:
            test_cases: List of test case dictionaries
            output_file: Output file path
        """
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            # Write header row (no quotes needed)
            f.write(','.join(self.HEADERS) + '\n')

            # Write each test case
            for tc in test_cases:
                self._write_test_case(f, tc)

    def generate_csv_string(self, test_cases: List[Dict]) -> str:
        """
        Generate CSV content as a string.

        Args:
            test_cases: List of test case dictionaries

        Returns:
            CSV content as string
        """
        output = io.StringIO()

        # Write header
        output.write(','.join(self.HEADERS) + '\n')

        # Write each test case
        for tc in test_cases:
            self._write_test_case_to_stream(output, tc)

        return output.getvalue()

    def _write_test_case(self, f, tc: Dict) -> None:
        """Write a single test case to file."""
        # Header row for test case
        clean_title = self._clean_text(tc.get('title', ''))
        row = [
            '',  # ID
            'Test Case',  # Work Item Type
            clean_title,  # Title
            '',  # TestStep
            '',  # Step Action
            '',  # Step Expected
            self._area_path,  # Area Path
            self._assigned_to,  # Assigned To
            self._default_state  # State
        ]
        formatted_row = [self._format_csv_value(val) for val in row]
        f.write(','.join(formatted_row) + '\n')

        # Step rows
        for idx, step in enumerate(tc.get('steps', []), start=1):
            clean_action = self._clean_text(step.get('action', ''))
            clean_expected = self._clean_text(step.get('expected', ''))
            step_row = [
                '',  # ID
                '',  # Work Item Type
                '',  # Title
                str(idx),  # TestStep
                clean_action,  # Step Action
                clean_expected,  # Step Expected
                '',  # Area Path
                '',  # Assigned To
                ''  # State
            ]
            formatted_row = [self._format_csv_value(val) for val in step_row]
            f.write(','.join(formatted_row) + '\n')

    def _write_test_case_to_stream(self, output: io.StringIO, tc: Dict) -> None:
        """Write a single test case to string stream."""
        # Header row
        clean_title = self._clean_text(tc.get('title', ''))
        row = [
            '', 'Test Case', clean_title, '', '', '',
            self._area_path, self._assigned_to, self._default_state
        ]
        formatted_row = [self._format_csv_value(val) for val in row]
        output.write(','.join(formatted_row) + '\n')

        # Step rows
        for idx, step in enumerate(tc.get('steps', []), start=1):
            clean_action = self._clean_text(step.get('action', ''))
            clean_expected = self._clean_text(step.get('expected', ''))
            step_row = ['', '', '', str(idx), clean_action, clean_expected, '', '', '']
            formatted_row = [self._format_csv_value(val) for val in step_row]
            output.write(','.join(formatted_row) + '\n')

    @staticmethod
    def _clean_text(text: str) -> str:
        """
        Clean text for CSV: replace newlines with spaces.

        Args:
            text: Input text

        Returns:
            Cleaned text safe for CSV
        """
        if not text:
            return ""
        # Replace newlines and carriage returns with spaces
        text = text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
        # Remove extra whitespace
        text = ' '.join(text.split())
        return text

    @staticmethod
    def _format_csv_value(value) -> str:
        """
        Format CSV value: quote non-empty values.

        Args:
            value: Value to format

        Returns:
            Properly quoted/escaped CSV value
        """
        if value == '' or value is None:
            return ''
        # Use csv module to properly escape quotes and commas
        output = io.StringIO()
        csv.writer(output, quoting=csv.QUOTE_MINIMAL).writerow([str(value)])
        formatted = output.getvalue().rstrip('\n\r')
        return formatted
