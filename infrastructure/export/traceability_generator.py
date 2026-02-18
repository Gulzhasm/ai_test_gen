"""
Traceability Matrix Generator

Generates a traceability matrix JSON mapping test cases to automation artifacts
(Playwright scripts, Postman collections). Pure Python — no LLM required.
"""
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional


class TraceabilityGenerator:
    """Generates traceability mapping between test cases and automation artifacts."""

    def generate_traceability(
        self,
        story_id: str,
        story_title: str,
        test_cases: List[Dict],
        output_files: Dict[str, str],
        playwright_script: Optional[str] = None,
        postman_collection: Optional[Dict] = None,
        output_file: Optional[str] = None
    ) -> Dict:
        """Generate traceability matrix and optionally save to file."""
        matrix = self._build_matrix(
            story_id, story_title, test_cases,
            output_files, playwright_script, postman_collection
        )
        if output_file:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(matrix, f, indent=2)
        return matrix

    def _build_matrix(
        self,
        story_id: str,
        story_title: str,
        test_cases: List[Dict],
        output_files: Dict[str, str],
        playwright_script: Optional[str],
        postman_collection: Optional[Dict]
    ) -> Dict:
        """Build the traceability matrix dict."""
        artifacts = {}

        if 'csv' in output_files:
            artifacts['test_cases'] = {
                'file': os.path.basename(output_files['csv']),
                'count': len(test_cases)
            }

        if 'playwright' in output_files:
            test_count = playwright_script.count("test('") if playwright_script else 0
            artifacts['playwright_scripts'] = {
                'file': os.path.basename(output_files['playwright']),
                'test_count': test_count,
                'is_fallback': playwright_script is not None and '// TODO: Implement step' in playwright_script
            }

        if 'postman' in output_files:
            request_count = self._count_postman_requests(postman_collection) if postman_collection else 0
            artifacts['postman_collection'] = {
                'file': os.path.basename(output_files['postman']),
                'request_count': request_count,
                'is_fallback': postman_collection is not None and any(
                    item.get('name', '').startswith('TODO')
                    for item in postman_collection.get('item', [])
                )
            }

        # Build per-test-case mappings
        mappings = []
        for tc in test_cases:
            tc_id = tc.get('id', '')
            is_accessibility = 'accessibility' in tc.get('title', '').lower()

            mapping = {
                'test_case_id': tc_id,
                'test_case_title': tc.get('title', ''),
                'playwright_function': None,
                'postman_request': None,
                'skipped_reason': None
            }

            if is_accessibility:
                mapping['skipped_reason'] = 'Accessibility test — requires Axe/a11y tooling'
            elif playwright_script and tc_id in playwright_script:
                mapping['playwright_function'] = f"test('{tc_id}: ...')"

            mappings.append(mapping)

        return {
            'story_id': story_id,
            'story_title': story_title,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'artifacts': artifacts,
            'mappings': mappings
        }

    @staticmethod
    def _count_postman_requests(collection: Optional[Dict]) -> int:
        """Count total requests in a Postman collection (including nested folders)."""
        if not collection:
            return 0
        count = 0
        for item in collection.get('item', []):
            if 'request' in item:
                count += 1
            for sub_item in item.get('item', []):
                if 'request' in sub_item:
                    count += 1
        return count
