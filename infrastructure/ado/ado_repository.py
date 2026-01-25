"""
Azure DevOps repository implementations.

Implements repository interfaces for ADO data access.
"""
from typing import Optional, List, Dict, Any
import re
from bs4 import BeautifulSoup

from core.domain.story import UserStory
from core.domain.test_case import TestCase
from core.interfaces.repository import (
    IStoryRepository,
    ITestSuiteRepository,
    ITestCaseRepository
)
from core.interfaces.config_provider import IADOConfig
from .http_client import ADOHttpClient


class HtmlParser:
    """Utility class for parsing HTML content from ADO."""

    @staticmethod
    def normalize_to_text(html_content: str) -> str:
        """Convert HTML to plain text, preserving structure.

        Args:
            html_content: HTML string

        Returns:
            Plain text with preserved bullet points and line breaks
        """
        if not html_content:
            return ""

        soup = BeautifulSoup(html_content, 'html.parser')

        # Convert lists to bullet points
        for ul in soup.find_all(['ul', 'ol']):
            for li in ul.find_all('li', recursive=False):
                text = li.get_text().strip()
                if not text.startswith('•') and not text.startswith('-'):
                    li.insert(0, '• ')

        text = soup.get_text(separator='\n')

        # Clean up whitespace while preserving structure
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return '\n'.join(lines)

    @staticmethod
    def parse_acceptance_criteria(ac_text: str) -> List[str]:
        """Parse acceptance criteria text into list of bullets.

        Args:
            ac_text: Raw acceptance criteria text

        Returns:
            List of AC bullet strings
        """
        if not ac_text:
            return []

        bullets = []
        lines = ac_text.strip().split('\n')

        for line in lines:
            line = line.strip()
            # Remove bullet markers
            if line.startswith('•'):
                line = line[1:].strip()
            elif line.startswith('-'):
                line = line[1:].strip()
            elif re.match(r'^\d+\.', line):
                line = re.sub(r'^\d+\.\s*', '', line)

            if line:
                bullets.append(line)

        return bullets


class ADOStoryRepository(IStoryRepository):
    """Azure DevOps implementation of story repository."""

    def __init__(self, config: IADOConfig):
        """Initialize repository with ADO configuration.

        Args:
            config: Azure DevOps configuration (implements IADOConfig)
        """
        self._config = config
        self._client = ADOHttpClient(
            organization=config.organization,
            project=config.project,
            pat=config.pat
        )
        self._parser = HtmlParser()

    def get_story(self, story_id: int) -> Optional[UserStory]:
        """Retrieve a user story by ID."""
        try:
            data = self._client.get(
                f"_apis/wit/workitems/{story_id}",
                params={"$expand": "all"}
            )

            fields = data.get('fields', {})
            title = fields.get('System.Title', '')
            description_html = fields.get('System.Description', '')
            ac_html = fields.get('Microsoft.VSTS.Common.AcceptanceCriteria', '')

            description = self._parser.normalize_to_text(description_html)
            ac_text = self._parser.normalize_to_text(ac_html)

            # Try comments if AC field is empty
            if not ac_text:
                ac_text = self._extract_ac_from_comments(story_id)

            ac_bullets = self._parser.parse_acceptance_criteria(ac_text)

            return UserStory(
                story_id=story_id,
                title=title,
                description=description,
                acceptance_criteria_text=ac_text,
                acceptance_criteria=ac_bullets
            )
        except Exception as e:
            print(f"Error retrieving story {story_id}: {e}")
            return None

    def get_qa_prep(self, story_id: int) -> Optional[str]:
        """Retrieve QA Prep content for a story."""
        qa_prep_pattern = self._config.qa_prep_pattern
        if not qa_prep_pattern:
            return None

        qa_prep_title = qa_prep_pattern.format(story_id=story_id)

        try:
            # Search for QA Prep subtask
            query = (
                f"Select [System.Id], [System.Title] "
                f"From WorkItems "
                f"Where [System.Title] = '{qa_prep_title}' "
                f"And [System.WorkItemType] = 'Sub-task'"
            )

            result = self._client.execute_wiql(query)
            work_items = result.get('workItems', [])

            if work_items:
                work_item_id = work_items[0]['id']
                item_data = self._client.get(f"_apis/wit/workitems/{work_item_id}")
                description = item_data.get('fields', {}).get('System.Description', '')
                return self._parser.normalize_to_text(description)

            return None
        except Exception as e:
            print(f"Error retrieving QA Prep for story {story_id}: {e}")
            return None

    def _extract_ac_from_comments(self, story_id: int) -> str:
        """Extract AC from work item comments if AC field is empty."""
        try:
            comments = self._client.get(f"_apis/wit/workitems/{story_id}/comments")
            for comment in comments.get('comments', []):
                text = comment.get('text', '')
                if 'acceptance criteria' in text.lower() or '•' in text:
                    return self._parser.normalize_to_text(text)
        except Exception:
            pass
        return ""


class ADOTestSuiteRepository(ITestSuiteRepository):
    """Azure DevOps implementation of test suite repository."""

    def __init__(self, config: IADOConfig):
        """Initialize repository with ADO configuration."""
        self._config = config
        self._client = ADOHttpClient(
            organization=config.organization,
            project=config.project,
            pat=config.pat
        )

    def find_suite_by_story_id(self, story_id: int) -> Optional[Dict[str, Any]]:
        """Find test suite matching story ID pattern."""
        prefix = f"{story_id} :"

        try:
            # Get all test plans
            plans = self._client.get("_apis/testplan/plans")

            for plan in plans.get('value', []):
                plan_id = plan['id']
                suites = self._get_all_suites(plan_id)

                for suite in suites:
                    if suite.get('name', '').startswith(prefix):
                        return {
                            'id': suite['id'],
                            'name': suite['name'],
                            'plan_id': plan_id
                        }
        except Exception as e:
            print(f"Error finding test suite for story {story_id}: {e}")

        return None

    def _get_all_suites(self, plan_id: int) -> List[Dict]:
        """Get all suites in a test plan recursively."""
        suites = []
        try:
            result = self._client.get(f"_apis/testplan/Plans/{plan_id}/suites")
            suites.extend(result.get('value', []))
        except Exception:
            pass
        return suites

    def create_suite(
        self,
        plan_id: int,
        suite_name: str,
        story_id: int
    ) -> Optional[Dict[str, Any]]:
        """Create a new test suite."""
        try:
            # Get root suite
            plan = self._client.get(f"_apis/testplan/Plans/{plan_id}")
            root_suite_id = plan.get('rootSuite', {}).get('id', plan_id)

            # Create suite
            result = self._client.post(
                f"_apis/testplan/Plans/{plan_id}/suites/{root_suite_id}",
                data={
                    "suiteType": "staticTestSuite",
                    "name": suite_name
                }
            )

            return {
                'id': result['id'],
                'name': result['name'],
                'plan_id': plan_id
            }
        except Exception as e:
            print(f"Error creating test suite: {e}")
            return None

    def add_test_case_to_suite(
        self,
        plan_id: int,
        suite_id: int,
        test_case_id: int
    ) -> bool:
        """Add a test case to a test suite."""
        try:
            self._client.post(
                f"_apis/testplan/Plans/{plan_id}/Suites/{suite_id}/TestCase",
                data=[{'workItem': {'id': test_case_id}}]
            )
            return True
        except Exception as e:
            print(f"Error adding test case to suite: {e}")
            return False


class ADOTestCaseRepository(ITestCaseRepository):
    """Azure DevOps implementation of test case repository."""

    def __init__(self, config: IADOConfig):
        """Initialize repository with ADO configuration."""
        self._config = config
        self._client = ADOHttpClient(
            organization=config.organization,
            project=config.project,
            pat=config.pat
        )

    def create_test_case(
        self,
        title: str,
        steps: List[Dict[str, str]],
        objective: str,
        **kwargs
    ) -> Optional[int]:
        """Create a test case work item."""
        try:
            steps_xml = self._build_steps_xml(steps)

            patch_doc = [
                {"op": "add", "path": "/fields/System.Title", "value": title},
                {"op": "add", "path": "/fields/Microsoft.VSTS.TCM.Steps", "value": steps_xml}
            ]

            # Add optional fields
            if kwargs.get('assigned_to') or self._config.assigned_to:
                patch_doc.append({
                    "op": "add",
                    "path": "/fields/System.AssignedTo",
                    "value": kwargs.get('assigned_to', self._config.assigned_to)
                })

            if kwargs.get('area_path') or self._config.area_path:
                patch_doc.append({
                    "op": "add",
                    "path": "/fields/System.AreaPath",
                    "value": kwargs.get('area_path', self._config.area_path)
                })

            if kwargs.get('state') or self._config.default_state:
                patch_doc.append({
                    "op": "add",
                    "path": "/fields/System.State",
                    "value": kwargs.get('state', self._config.default_state)
                })

            if objective:
                patch_doc.append({
                    "op": "add",
                    "path": "/fields/System.Description",
                    "value": objective
                })

            result = self._client.patch(
                "_apis/wit/workitems/$Test Case",
                data=patch_doc
            )

            return result.get('id')
        except Exception as e:
            print(f"Error creating test case: {e}")
            return None

    def update_test_case(
        self,
        test_case_id: int,
        fields: Dict[str, Any]
    ) -> bool:
        """Update a test case."""
        try:
            patch_doc = []
            for field, value in fields.items():
                patch_doc.append({
                    "op": "replace",
                    "path": f"/fields/{field}",
                    "value": value
                })

            self._client.patch(
                f"_apis/wit/workitems/{test_case_id}",
                data=patch_doc
            )
            return True
        except Exception as e:
            print(f"Error updating test case {test_case_id}: {e}")
            return False

    def get_test_case(self, test_case_id: int) -> Optional[Dict[str, Any]]:
        """Get a test case by ID."""
        try:
            return self._client.get(f"_apis/wit/workitems/{test_case_id}")
        except Exception as e:
            print(f"Error getting test case {test_case_id}: {e}")
            return None

    def _build_steps_xml(self, steps: List[Dict[str, str]]) -> str:
        """Build XML for test steps."""
        if not steps:
            return ""

        xml_parts = [f'<steps id="0" last="{len(steps)}">']

        for idx, step in enumerate(steps, start=1):
            action = self._escape_xml(step.get('action', ''))
            expected = self._escape_xml(step.get('expected', ''))

            xml_parts.append(f'  <step id="{idx}" type="ValidateStep">')
            xml_parts.append(
                f'    <parameterizedString isformatted="true">'
                f'&lt;DIV&gt;&lt;P&gt;{action}&lt;/P&gt;&lt;/DIV&gt;'
                f'</parameterizedString>'
            )
            xml_parts.append(
                f'    <parameterizedString isformatted="true">'
                f'&lt;DIV&gt;&lt;P&gt;{expected}&lt;/P&gt;&lt;/DIV&gt;'
                f'</parameterizedString>'
            )
            xml_parts.append('    <description/>')
            xml_parts.append('  </step>')

        xml_parts.append('</steps>')
        return '\n'.join(xml_parts)

    @staticmethod
    def _escape_xml(text: str) -> str:
        """Escape special XML characters."""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&apos;'))
