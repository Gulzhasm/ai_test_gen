"""
TestRail repository implementations.

Implements repository interfaces for TestRail data access.
"""
from typing import Optional, List, Dict, Any

from core.interfaces.repository import ITestSuiteRepository, ITestCaseRepository
from .http_client import TestRailHttpClient


class TestRailTestSuiteRepository(ITestSuiteRepository):
    """TestRail implementation of test suite repository."""

    def __init__(
        self,
        base_url: str,
        email: str,
        api_key: str,
        project_id: int,
        suite_id: Optional[int] = None
    ):
        """Initialize repository with TestRail configuration.

        Args:
            base_url: TestRail instance URL
            email: User email
            api_key: API key
            project_id: TestRail project ID
            suite_id: Default suite ID (for multi-suite projects)
        """
        self._client = TestRailHttpClient(
            base_url=base_url,
            email=email,
            api_key=api_key
        )
        self._project_id = project_id
        self._suite_id = suite_id
        self._section_cache: Dict[str, int] = {}

    def find_suite_by_story_id(self, story_id: int) -> Optional[Dict[str, Any]]:
        """Find test suite/section matching story ID pattern.

        In TestRail, we map story IDs to sections within a suite.

        Args:
            story_id: The story ID

        Returns:
            Section info dict with 'id', 'name', 'suite_id' if found
        """
        section_prefix = f"{story_id} :"

        try:
            sections = self._client.get_sections(
                self._project_id,
                suite_id=self._suite_id
            )

            for section in sections:
                section_name = section.get('name', '')
                if section_name.startswith(section_prefix):
                    return {
                        'id': section['id'],
                        'name': section_name,
                        'plan_id': self._suite_id or self._project_id,
                        'suite_id': self._suite_id
                    }

            return None

        except Exception as e:
            print(f"Error finding section for story {story_id}: {e}")
            return None

    def create_suite(
        self,
        plan_id: int,
        suite_name: str,
        story_id: int
    ) -> Optional[Dict[str, Any]]:
        """Create a new section for the story.

        In TestRail, we create sections rather than suites for individual stories.

        Args:
            plan_id: Suite ID (or project ID for single-suite projects)
            suite_name: Section name
            story_id: Story ID

        Returns:
            Section info dict if created
        """
        try:
            result = self._client.add_section(
                project_id=self._project_id,
                name=suite_name,
                suite_id=self._suite_id,
                description=f"Test cases for Story {story_id}"
            )

            return {
                'id': result['id'],
                'name': result['name'],
                'plan_id': self._suite_id or self._project_id,
                'suite_id': self._suite_id
            }

        except Exception as e:
            print(f"Error creating section: {e}")
            return None

    def add_test_case_to_suite(
        self,
        plan_id: int,
        suite_id: int,
        test_case_id: int
    ) -> bool:
        """Test cases in TestRail are automatically in their section.

        This is a no-op for TestRail since cases are created directly in sections.

        Args:
            plan_id: Not used for TestRail
            suite_id: Section ID
            test_case_id: Test case ID

        Returns:
            True (always succeeds for TestRail)
        """
        # In TestRail, test cases are already in their section when created
        return True

    def get_or_create_section(self, section_name: str) -> Optional[int]:
        """Get existing section or create a new one.

        Args:
            section_name: Section name

        Returns:
            Section ID if found or created
        """
        # Check cache first
        if section_name in self._section_cache:
            return self._section_cache[section_name]

        try:
            # Search for existing section
            sections = self._client.get_sections(
                self._project_id,
                suite_id=self._suite_id
            )

            for section in sections:
                if section.get('name') == section_name:
                    self._section_cache[section_name] = section['id']
                    return section['id']

            # Create new section
            result = self._client.add_section(
                project_id=self._project_id,
                name=section_name,
                suite_id=self._suite_id
            )

            section_id = result['id']
            self._section_cache[section_name] = section_id
            return section_id

        except Exception as e:
            print(f"Error getting/creating section '{section_name}': {e}")
            return None


class TestRailTestCaseRepository(ITestCaseRepository):
    """TestRail implementation of test case repository."""

    # TestRail status IDs
    STATUS_PASSED = 1
    STATUS_BLOCKED = 2
    STATUS_UNTESTED = 3
    STATUS_RETEST = 4
    STATUS_FAILED = 5

    def __init__(
        self,
        base_url: str,
        email: str,
        api_key: str,
        project_id: int,
        suite_id: Optional[int] = None,
        default_section_id: Optional[int] = None
    ):
        """Initialize repository with TestRail configuration.

        Args:
            base_url: TestRail instance URL
            email: User email
            api_key: API key
            project_id: TestRail project ID
            suite_id: Default suite ID (for multi-suite projects)
            default_section_id: Default section ID for new test cases
        """
        self._client = TestRailHttpClient(
            base_url=base_url,
            email=email,
            api_key=api_key
        )
        self._project_id = project_id
        self._suite_id = suite_id
        self._default_section_id = default_section_id

    def create_test_case(
        self,
        title: str,
        steps: List[Dict[str, str]],
        objective: str,
        **kwargs
    ) -> Optional[int]:
        """Create a test case in TestRail.

        Args:
            title: Test case title
            steps: List of step dicts with 'action' and 'expected'
            objective: Test case objective/description
            **kwargs: Additional fields:
                - section_id: Section ID (required if no default)
                - priority_id: Priority ID (1=Low, 2=Medium, 3=High, 4=Critical)
                - type_id: Test type ID
                - refs: Reference IDs (e.g., story IDs)
                - template_id: Template ID
                - custom_*: Custom fields

        Returns:
            Test case ID if created, None otherwise
        """
        section_id = kwargs.pop('section_id', self._default_section_id)
        if not section_id:
            print("Error: section_id is required to create a test case")
            return None

        try:
            # Build test case data
            data = {
                "title": title,
            }

            # Add objective/preconditions
            if objective:
                data['custom_preconds'] = objective

            # Convert steps to TestRail format
            if steps:
                steps_separated = self._build_steps_separated(steps)
                data['custom_steps_separated'] = steps_separated

            # Add optional fields
            if kwargs.get('priority_id'):
                data['priority_id'] = kwargs['priority_id']
            if kwargs.get('type_id'):
                data['type_id'] = kwargs['type_id']
            if kwargs.get('refs'):
                data['refs'] = kwargs['refs']
            if kwargs.get('template_id'):
                data['template_id'] = kwargs['template_id']

            # Add any custom fields
            for key, value in kwargs.items():
                if key.startswith('custom_'):
                    data[key] = value

            result = self._client.add_case(section_id, title, **{k: v for k, v in data.items() if k != 'title'})
            return result.get('id')

        except Exception as e:
            print(f"Error creating test case: {e}")
            return None

    def _build_steps_separated(self, steps: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Build TestRail separated steps format.

        Args:
            steps: List of step dicts with 'action' and 'expected'

        Returns:
            List in TestRail format with 'content' and 'expected'
        """
        testrail_steps = []
        for step in steps:
            testrail_steps.append({
                'content': step.get('action', ''),
                'expected': step.get('expected', '')
            })
        return testrail_steps

    def update_test_case(
        self,
        test_case_id: int,
        fields: Dict[str, Any]
    ) -> bool:
        """Update a test case.

        Args:
            test_case_id: Test case ID
            fields: Fields to update

        Returns:
            True if successful
        """
        try:
            # Convert steps if present
            if 'steps' in fields:
                fields['custom_steps_separated'] = self._build_steps_separated(fields.pop('steps'))

            # Convert objective to preconditions
            if 'objective' in fields:
                fields['custom_preconds'] = fields.pop('objective')

            self._client.update_case(test_case_id, **fields)
            return True

        except Exception as e:
            print(f"Error updating test case {test_case_id}: {e}")
            return False

    def get_test_case(self, test_case_id: int) -> Optional[Dict[str, Any]]:
        """Get a test case by ID.

        Args:
            test_case_id: Test case ID

        Returns:
            Test case data if found
        """
        try:
            return self._client.get_case(test_case_id)
        except Exception as e:
            print(f"Error getting test case {test_case_id}: {e}")
            return None

    def bulk_create_test_cases(
        self,
        section_id: int,
        test_cases: List[Dict[str, Any]]
    ) -> List[int]:
        """Create multiple test cases in a section.

        Args:
            section_id: Section ID
            test_cases: List of test case data dicts

        Returns:
            List of created test case IDs
        """
        created_ids = []
        for tc in test_cases:
            case_id = self.create_test_case(
                title=tc.get('title', 'Untitled'),
                steps=tc.get('steps', []),
                objective=tc.get('objective', ''),
                section_id=section_id,
                **{k: v for k, v in tc.items() if k not in ['title', 'steps', 'objective']}
            )
            if case_id:
                created_ids.append(case_id)

        return created_ids
