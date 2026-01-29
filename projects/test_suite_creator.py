"""
Auto Test Suite Creator - Creates test plans and test suites in ADO.

Note: This module is intentionally ADO-specific because test plans and test suites
are ADO concepts. For TestRail, sections are created via the TestRailTestSuiteRepository.
The UploadWorkflow handles platform selection automatically.
"""
from typing import Dict, Optional, List, Tuple
import requests
from requests.auth import HTTPBasicAuth
from dataclasses import dataclass

from .project_config import ProjectConfig


@dataclass
class TestPlanInfo:
    """Information about a created or found test plan."""
    id: int
    name: str
    url: str
    is_new: bool = False


@dataclass
class TestSuiteInfo:
    """Information about a created or found test suite."""
    id: int
    name: str
    plan_id: int
    url: str
    is_new: bool = False


class TestSuiteCreator:
    """
    Creates test plans and test suites in Azure DevOps.
    Used when projects don't have pre-existing test organization.
    """

    def __init__(self, config: ProjectConfig):
        """
        Initialize the test suite creator.

        Args:
            config: Project configuration containing ADO settings.
        """
        self.config = config
        self.ado = config.ado
        self.auth = HTTPBasicAuth('', self.ado.pat or '')
        self.headers = {'Content-Type': 'application/json'}

    @property
    def base_url(self) -> str:
        """Get the ADO API base URL."""
        return f"https://dev.azure.com/{self.ado.organization}/{self.ado.project}"

    def get_or_create_test_plan(
        self,
        plan_name: str,
        area_path: str = None,
        iteration_path: str = None
    ) -> TestPlanInfo:
        """
        Get an existing test plan or create a new one.

        Args:
            plan_name: Name for the test plan.
            area_path: Optional area path override.
            iteration_path: Optional iteration path.

        Returns:
            TestPlanInfo with plan details.
        """
        # First, try to find existing plan
        existing = self._find_test_plan(plan_name)
        if existing:
            return existing

        # Create new test plan
        return self._create_test_plan(plan_name, area_path, iteration_path)

    def get_or_create_test_suite(
        self,
        story_id: str,
        story_name: str,
        test_plan_id: int
    ) -> TestSuiteInfo:
        """
        Get an existing test suite or create a new one for a story.

        Args:
            story_id: The story/work item ID.
            story_name: Name of the story.
            test_plan_id: ID of the parent test plan.

        Returns:
            TestSuiteInfo with suite details.
        """
        # Build suite name using project pattern
        suite_name = self.ado.test_suite_pattern.format(
            story_id=story_id,
            story_name=story_name
        )

        # Try to find existing suite
        existing = self._find_test_suite(test_plan_id, story_id)
        if existing:
            return existing

        # Create new test suite
        return self._create_test_suite(test_plan_id, suite_name, story_id)

    def create_test_organization(
        self,
        story_id: str,
        story_name: str,
        plan_name: str = None
    ) -> Tuple[TestPlanInfo, TestSuiteInfo]:
        """
        Create complete test organization for a story.

        This method:
        1. Creates or finds a test plan
        2. Creates or finds a test suite for the story

        Args:
            story_id: The story/work item ID.
            story_name: Name of the story.
            plan_name: Optional test plan name. Defaults to project-based name.

        Returns:
            Tuple of (TestPlanInfo, TestSuiteInfo).
        """
        # Default plan name based on project
        if plan_name is None:
            plan_name = f"{self.config.application.name} Test Plan"

        # Get or create the test plan
        plan = self.get_or_create_test_plan(plan_name)
        print(f"  Test Plan: {plan.name} (ID: {plan.id})" +
              (" [NEW]" if plan.is_new else " [EXISTING]"))

        # Get or create the test suite
        suite = self.get_or_create_test_suite(story_id, story_name, plan.id)
        print(f"  Test Suite: {suite.name} (ID: {suite.id})" +
              (" [NEW]" if suite.is_new else " [EXISTING]"))

        return plan, suite

    def add_test_cases_to_suite(
        self,
        suite_id: int,
        plan_id: int,
        test_case_ids: List[int]
    ) -> bool:
        """
        Add test cases to a test suite.

        Args:
            suite_id: ID of the test suite.
            plan_id: ID of the test plan.
            test_case_ids: List of test case work item IDs.

        Returns:
            True if successful, False otherwise.
        """
        if not test_case_ids:
            return True

        url = (f"{self.base_url}/_apis/testplan/Plans/{plan_id}/suites/{suite_id}"
               f"/testcases?api-version=7.1")

        # Build the payload
        test_cases = [{"id": tc_id} for tc_id in test_case_ids]

        try:
            response = requests.post(
                url,
                json=test_cases,
                auth=self.auth,
                headers=self.headers
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"  Error adding test cases to suite: {e}")
            return False

    # Private Methods

    def _find_test_plan(self, plan_name: str) -> Optional[TestPlanInfo]:
        """Find an existing test plan by name."""
        url = f"{self.base_url}/_apis/testplan/plans?api-version=7.1"

        try:
            response = requests.get(url, auth=self.auth, headers=self.headers)
            response.raise_for_status()
            plans = response.json().get('value', [])

            for plan in plans:
                if plan.get('name', '').lower() == plan_name.lower():
                    return TestPlanInfo(
                        id=plan['id'],
                        name=plan['name'],
                        url=plan.get('url', ''),
                        is_new=False
                    )
        except requests.exceptions.RequestException as e:
            print(f"  Warning: Could not search for test plans: {e}")

        return None

    def _create_test_plan(
        self,
        plan_name: str,
        area_path: str = None,
        iteration_path: str = None
    ) -> TestPlanInfo:
        """Create a new test plan."""
        url = f"{self.base_url}/_apis/testplan/plans?api-version=7.1"

        payload = {
            "name": plan_name,
            "area": {
                "name": area_path or self.ado.area_path
            }
        }

        if iteration_path:
            payload["iteration"] = iteration_path

        try:
            response = requests.post(
                url,
                json=payload,
                auth=self.auth,
                headers=self.headers
            )
            response.raise_for_status()
            data = response.json()

            return TestPlanInfo(
                id=data['id'],
                name=data['name'],
                url=data.get('url', ''),
                is_new=True
            )
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to create test plan: {e}")

    def _find_test_suite(self, plan_id: int, story_id: str) -> Optional[TestSuiteInfo]:
        """Find an existing test suite by story ID prefix."""
        url = f"{self.base_url}/_apis/testplan/Plans/{plan_id}/suites?api-version=7.1"

        try:
            response = requests.get(url, auth=self.auth, headers=self.headers)
            response.raise_for_status()
            suites = response.json().get('value', [])

            # Look for suite matching the story ID pattern
            prefix = self.ado.get_test_suite_prefix(story_id)

            for suite in suites:
                suite_name = suite.get('name', '')
                if suite_name.startswith(prefix):
                    return TestSuiteInfo(
                        id=suite['id'],
                        name=suite_name,
                        plan_id=plan_id,
                        url=suite.get('url', ''),
                        is_new=False
                    )
        except requests.exceptions.RequestException as e:
            print(f"  Warning: Could not search for test suites: {e}")

        return None

    def _create_test_suite(
        self,
        plan_id: int,
        suite_name: str,
        story_id: str
    ) -> TestSuiteInfo:
        """Create a new test suite under a test plan."""
        # Get the root suite ID first
        root_suite_id = self._get_root_suite_id(plan_id)

        url = (f"{self.base_url}/_apis/testplan/Plans/{plan_id}/suites/{root_suite_id}"
               f"?api-version=7.1")

        payload = {
            "suiteType": "staticTestSuite",
            "name": suite_name
        }

        try:
            response = requests.post(
                url,
                json=payload,
                auth=self.auth,
                headers=self.headers
            )
            response.raise_for_status()
            data = response.json()

            return TestSuiteInfo(
                id=data['id'],
                name=data['name'],
                plan_id=plan_id,
                url=data.get('url', ''),
                is_new=True
            )
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to create test suite: {e}")

    def _get_root_suite_id(self, plan_id: int) -> int:
        """Get the root suite ID for a test plan."""
        url = f"{self.base_url}/_apis/testplan/Plans/{plan_id}?api-version=7.1"

        try:
            response = requests.get(url, auth=self.auth, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            return data.get('rootSuite', {}).get('id', plan_id)
        except requests.exceptions.RequestException as e:
            # Fall back to plan_id as root suite
            return plan_id


class QAPrepGenerator:
    """
    Generates QA Prep-equivalent content when no QA Prep task exists.
    Uses LLM to analyze story and generate testing guidance.
    """

    def __init__(self, config: ProjectConfig, llm_provider=None):
        """
        Initialize QA Prep generator.

        Args:
            config: Project configuration.
            llm_provider: Optional LLM provider for AI-assisted generation.
        """
        self.config = config
        self.llm_provider = llm_provider

    def generate_qa_prep_content(
        self,
        story_data: Dict,
        acceptance_criteria: List[str]
    ) -> Dict:
        """
        Generate QA Prep equivalent content from story data.

        Args:
            story_data: Story information from ADO.
            acceptance_criteria: List of acceptance criteria.

        Returns:
            Dictionary with QA Prep-style information:
            - entry_points: List of UI entry points
            - platforms: List of target platforms
            - edge_cases: List of edge case scenarios
            - negative_scenarios: List of negative test scenarios
        """
        story_title = story_data.get('title', '')
        story_desc = story_data.get('description', '')
        combined_text = f"{story_title} {story_desc} {' '.join(acceptance_criteria)}".lower()

        # Extract entry points from story content
        entry_points = self._extract_entry_points(combined_text)

        # Determine platforms
        platforms = self._extract_platforms(combined_text)

        # Generate edge cases
        edge_cases = self._generate_edge_cases(combined_text, acceptance_criteria)

        # Generate negative scenarios
        negative_scenarios = self._generate_negative_scenarios(combined_text)

        return {
            'entry_points': entry_points,
            'platforms': platforms,
            'edge_cases': edge_cases,
            'negative_scenarios': negative_scenarios,
            'units': 'unit' in combined_text or 'metric' in combined_text or 'imperial' in combined_text,
            'visibility': 'visibility' in combined_text or 'show' in combined_text or 'hide' in combined_text,
            'undo_redo_actions': self._extract_undo_redo_actions(combined_text),
        }

    async def generate_with_llm(
        self,
        story_data: Dict,
        acceptance_criteria: List[str]
    ) -> Dict:
        """
        Generate comprehensive QA Prep content using LLM.

        Args:
            story_data: Story information from ADO.
            acceptance_criteria: List of acceptance criteria.

        Returns:
            Dictionary with QA Prep-style information.
        """
        if not self.llm_provider:
            return self.generate_qa_prep_content(story_data, acceptance_criteria)

        prompt = f"""Analyze this user story and generate testing guidance.

Story Title: {story_data.get('title', '')}
Description: {story_data.get('description', '')}
Acceptance Criteria:
{chr(10).join(f'- {ac}' for ac in acceptance_criteria)}

Application: {self.config.application.name}
UI Surfaces: {', '.join(self.config.application.main_ui_surfaces)}
Platforms: {', '.join(self.config.application.supported_platforms)}

Generate a JSON object with:
- entry_points: List of UI locations where this feature is accessed
- platforms: List of platforms to test on
- edge_cases: List of edge case scenarios to test
- negative_scenarios: List of negative/error scenarios
- special_considerations: Any special testing considerations

Only return valid JSON."""

        try:
            response = await self.llm_provider.generate(prompt)
            import json
            return json.loads(response)
        except Exception as e:
            print(f"  LLM QA Prep generation failed: {e}")
            return self.generate_qa_prep_content(story_data, acceptance_criteria)

    # Private Methods

    def _extract_entry_points(self, text: str) -> List[str]:
        """Extract entry points from text using project config."""
        entry_points = []

        for keyword, entry_point in self.config.application.entry_point_mappings.items():
            if keyword in text:
                if entry_point not in entry_points:
                    entry_points.append(entry_point)

        # Default to first UI surface if none found
        if not entry_points and self.config.application.main_ui_surfaces:
            entry_points.append(self.config.application.main_ui_surfaces[0])

        return entry_points

    def _extract_platforms(self, text: str) -> List[str]:
        """Extract platforms from text.

        Returns all supported platforms when none are explicitly mentioned,
        ensuring comprehensive test coverage across all configured platforms.
        """
        platforms = []

        for platform in self.config.application.supported_platforms:
            if platform.lower() in text:
                platforms.append(platform)

        # Default to ALL supported platforms if none explicitly mentioned
        # This ensures comprehensive test coverage (accessibility, tablet, etc.)
        if not platforms and self.config.application.supported_platforms:
            platforms = list(self.config.application.supported_platforms)

        return platforms

    def _generate_edge_cases(self, text: str, acs: List[str]) -> List[str]:
        """Generate edge case scenarios based on content."""
        edge_cases = []

        # Check for common edge case indicators
        if 'empty' in text or 'no data' in text:
            edge_cases.append('empty_state')

        if 'duplicate' in text or 'already exists' in text:
            edge_cases.append('duplicate_prevention')

        if 'multiple' in text or 'batch' in text:
            edge_cases.append('multiple_items')

        if 'large' in text or 'many' in text:
            edge_cases.append('large_dataset')

        if 'concurrent' in text or 'simultaneous' in text:
            edge_cases.append('concurrent_access')

        return edge_cases

    def _generate_negative_scenarios(self, text: str) -> List[str]:
        """Generate negative test scenarios."""
        scenarios = []

        if 'select' in text or 'selection' in text:
            scenarios.append('no_selection')

        if 'type' in text or 'valid' in text:
            scenarios.append('invalid_type')

        if 'permission' in text or 'access' in text:
            scenarios.append('insufficient_permissions')

        if 'network' in text or 'connection' in text:
            scenarios.append('network_error')

        return scenarios

    def _extract_undo_redo_actions(self, text: str) -> List[str]:
        """Extract undo/redo applicable actions."""
        actions = []

        if 'undo' in text or 'redo' in text:
            if 'add' in text or 'create' in text:
                actions.append('add/remove')
            if 'edit' in text or 'modify' in text:
                actions.append('edit')
            if 'visibility' in text or 'show' in text or 'hide' in text:
                actions.append('visibility')

        return actions
