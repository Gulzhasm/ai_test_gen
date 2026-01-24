"""
CSV Generator Module
Generates ADO-ready CSV files with exact column structure.
"""
import csv
from typing import Dict, List

import config


class CSVGenerator:
    """Generates ADO-ready CSV files."""
    
    def generate_csv(self, test_cases: List[Dict], output_file: str):
        """Generate ADO-ready CSV with exact column structure.
        
        CSV Structure:
        - One header row per test case (Work Item Type = Test Case)
        - Followed by step-per-row entries
        - Metadata columns blank on step rows
        - Plain text only (ADO-safe)
        - Newlines in text are replaced with spaces to prevent CSV breakage
        - Non-empty fields are quoted to match ADO export format
        """
        def clean_text(text: str) -> str:
            """Clean text for CSV: replace newlines with spaces, remove extra whitespace."""
            if not text:
                return ""
            # Replace newlines and carriage returns with spaces
            text = text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
            # Remove extra whitespace
            text = ' '.join(text.split())
            return text
        
        def format_csv_value(value):
            """Format CSV value: quote non-empty values, leave empty values unquoted."""
            if value == '' or value is None:
                return ''
            # Use csv module to properly escape quotes and commas
            import io
            output = io.StringIO()
            csv.writer(output, quoting=csv.QUOTE_MINIMAL).writerow([str(value)])
            formatted = output.getvalue().rstrip('\n\r')
            return formatted
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            # Write header manually (no quotes needed for header)
            header = ['ID', 'Work Item Type', 'Title', 'TestStep', 'Step Action', 'Step Expected',
                     'Area Path', 'AssignedTo', 'State']
            f.write(','.join(header) + '\n')
            
            # Write each test case
            for tc in test_cases:
                # Header row for test case - clean title to remove newlines
                clean_title = clean_text(tc['title'])
                row = [
                    '',  # ID
                    'Test Case',  # Work Item Type
                    clean_title,  # Title (cleaned)
                    '',  # TestStep
                    '',  # Step Action
                    '',  # Step Expected
                    config.ADO_AREA_PATH,  # Area Path
                    config.ASSIGNED_TO,  # Assigned To
                    config.DEFAULT_STATE  # State
                ]
                # Format row: quote non-empty fields
                formatted_row = [format_csv_value(val) for val in row]
                f.write(','.join(formatted_row) + '\n')
                
                # Step rows - clean action and expected text
                for idx, step in enumerate(tc['steps'], start=1):
                    clean_action = clean_text(step.get('action', ''))
                    clean_expected = clean_text(step.get('expected', ''))
                    row = [
                        '',  # ID
                        '',  # Work Item Type
                        '',  # Title
                        str(idx),  # TestStep
                        clean_action,  # Step Action (cleaned)
                        clean_expected,  # Step Expected (cleaned)
                        '',  # Area Path
                        '',  # Assigned To
                        ''  # State
                    ]
                    # Format row: quote non-empty fields
                    formatted_row = [format_csv_value(val) for val in row]
                    f.write(','.join(formatted_row) + '\n')
