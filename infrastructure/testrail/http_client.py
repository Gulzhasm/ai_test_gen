"""
TestRail HTTP Client - Low-level HTTP interactions with TestRail.

This class handles only HTTP concerns for TestRail API.
"""
import base64
from typing import Dict, Optional, Any, List
import requests


class TestRailHttpClient:
    """Low-level HTTP client for TestRail API."""

    def __init__(
        self,
        base_url: str,
        email: str,
        api_key: str,
        timeout: int = 30
    ):
        """Initialize TestRail HTTP client.

        Args:
            base_url: TestRail instance URL (e.g., "https://company.testrail.io")
            email: User email for authentication
            api_key: API key (found in My Settings > API Keys)
            timeout: Request timeout in seconds
        """
        if not api_key:
            raise ValueError("API key is required")
        if not base_url:
            raise ValueError("Base URL is required")
        if not email:
            raise ValueError("Email is required")

        self._base_url = base_url.rstrip('/')
        self._email = email
        self._api_key = api_key
        self._timeout = timeout
        self._headers = self._create_headers()

    @property
    def base_url(self) -> str:
        """Base URL for API calls."""
        return self._base_url

    @property
    def headers(self) -> Dict[str, str]:
        """Headers for API calls."""
        return self._headers.copy()

    def _create_headers(self) -> Dict[str, str]:
        """Create authentication headers."""
        # TestRail uses Basic Auth with email:api_key
        credentials = base64.b64encode(
            f"{self._email}:{self._api_key}".encode()
        ).decode()
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {credentials}'
        }

    def _get_api_url(self, endpoint: str) -> str:
        """Get the full API URL for an endpoint."""
        return f"{self._base_url}/index.php?/api/v2/{endpoint}"

    def get(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """Make GET request to TestRail API.

        Args:
            endpoint: API endpoint (e.g., "get_case/1")
            params: Optional query parameters

        Returns:
            JSON response

        Raises:
            requests.HTTPError: If request fails
        """
        url = self._get_api_url(endpoint)

        response = requests.get(
            url,
            headers=self._headers,
            params=params,
            timeout=self._timeout
        )
        response.raise_for_status()
        return response.json()

    def post(
        self,
        endpoint: str,
        data: Dict[str, Any]
    ) -> Any:
        """Make POST request to TestRail API.

        Args:
            endpoint: API endpoint
            data: Request body

        Returns:
            JSON response
        """
        url = self._get_api_url(endpoint)

        response = requests.post(
            url,
            headers=self._headers,
            json=data,
            timeout=self._timeout
        )
        response.raise_for_status()
        return response.json()

    # Projects

    def get_projects(self) -> List[Dict]:
        """Get all projects."""
        result = self.get("get_projects")
        # TestRail may return dict with 'projects' key or direct list
        if isinstance(result, dict):
            return result.get('projects', [])
        return result

    def get_project(self, project_id: int) -> Dict:
        """Get a specific project."""
        return self.get(f"get_project/{project_id}")

    # Test Suites

    def get_suites(self, project_id: int) -> List[Dict]:
        """Get all test suites in a project."""
        return self.get(f"get_suites/{project_id}")

    def get_suite(self, suite_id: int) -> Dict:
        """Get a specific test suite."""
        return self.get(f"get_suite/{suite_id}")

    def add_suite(self, project_id: int, name: str, description: str = "") -> Dict:
        """Create a new test suite.

        Args:
            project_id: Project ID
            name: Suite name
            description: Suite description

        Returns:
            Created suite data
        """
        return self.post(f"add_suite/{project_id}", {
            "name": name,
            "description": description
        })

    # Sections

    def get_sections(self, project_id: int, suite_id: Optional[int] = None) -> List[Dict]:
        """Get all sections in a project/suite."""
        endpoint = f"get_sections/{project_id}"
        params = {}
        if suite_id:
            params['suite_id'] = suite_id
        return self.get(endpoint, params=params or None)

    def add_section(
        self,
        project_id: int,
        name: str,
        suite_id: Optional[int] = None,
        parent_id: Optional[int] = None,
        description: str = ""
    ) -> Dict:
        """Create a new section.

        Args:
            project_id: Project ID
            name: Section name
            suite_id: Suite ID (required for multi-suite projects)
            parent_id: Parent section ID for nested sections
            description: Section description

        Returns:
            Created section data
        """
        data = {"name": name}
        if suite_id:
            data['suite_id'] = suite_id
        if parent_id:
            data['parent_id'] = parent_id
        if description:
            data['description'] = description

        return self.post(f"add_section/{project_id}", data)

    # Test Cases

    def get_cases(
        self,
        project_id: int,
        suite_id: Optional[int] = None,
        section_id: Optional[int] = None
    ) -> List[Dict]:
        """Get test cases.

        Args:
            project_id: Project ID
            suite_id: Suite ID (optional)
            section_id: Section ID (optional)

        Returns:
            List of test cases
        """
        endpoint = f"get_cases/{project_id}"
        params = {}
        if suite_id:
            params['suite_id'] = suite_id
        if section_id:
            params['section_id'] = section_id

        result = self.get(endpoint, params=params or None)
        # Handle paginated response
        if isinstance(result, dict):
            return result.get('cases', [])
        return result

    def get_case(self, case_id: int) -> Dict:
        """Get a specific test case."""
        return self.get(f"get_case/{case_id}")

    def add_case(
        self,
        section_id: int,
        title: str,
        **kwargs
    ) -> Dict:
        """Create a new test case.

        Args:
            section_id: Section ID where the case will be added
            title: Test case title
            **kwargs: Additional fields:
                - template_id: Template ID
                - type_id: Test type ID
                - priority_id: Priority ID
                - estimate: Time estimate (e.g., "1m", "1h")
                - milestone_id: Milestone ID
                - refs: Reference IDs (comma-separated)
                - custom_*: Custom fields

        Returns:
            Created test case data
        """
        data = {"title": title}
        data.update(kwargs)
        return self.post(f"add_case/{section_id}", data)

    def update_case(self, case_id: int, **kwargs) -> Dict:
        """Update an existing test case.

        Args:
            case_id: Test case ID
            **kwargs: Fields to update

        Returns:
            Updated test case data
        """
        return self.post(f"update_case/{case_id}", kwargs)

    # Test Runs

    def get_runs(self, project_id: int) -> List[Dict]:
        """Get all test runs in a project."""
        result = self.get(f"get_runs/{project_id}")
        if isinstance(result, dict):
            return result.get('runs', [])
        return result

    def add_run(
        self,
        project_id: int,
        name: str,
        suite_id: Optional[int] = None,
        description: str = "",
        milestone_id: Optional[int] = None,
        case_ids: Optional[List[int]] = None
    ) -> Dict:
        """Create a new test run.

        Args:
            project_id: Project ID
            name: Run name
            suite_id: Suite ID
            description: Run description
            milestone_id: Milestone ID
            case_ids: List of case IDs to include (None for all)

        Returns:
            Created run data
        """
        data = {"name": name}
        if suite_id:
            data['suite_id'] = suite_id
        if description:
            data['description'] = description
        if milestone_id:
            data['milestone_id'] = milestone_id
        if case_ids is not None:
            data['include_all'] = False
            data['case_ids'] = case_ids
        else:
            data['include_all'] = True

        return self.post(f"add_run/{project_id}", data)

    # Test Results

    def add_result(
        self,
        test_id: int,
        status_id: int,
        comment: str = "",
        **kwargs
    ) -> Dict:
        """Add a test result.

        Args:
            test_id: Test ID (from test run)
            status_id: Status ID (1=Passed, 2=Blocked, 3=Untested, 4=Retest, 5=Failed)
            comment: Result comment
            **kwargs: Additional fields (elapsed, defects, etc.)

        Returns:
            Created result data
        """
        data = {"status_id": status_id}
        if comment:
            data['comment'] = comment
        data.update(kwargs)
        return self.post(f"add_result/{test_id}", data)

    # Case Fields

    def get_case_fields(self) -> List[Dict]:
        """Get all case fields (including custom fields)."""
        return self.get("get_case_fields")

    def get_case_types(self) -> List[Dict]:
        """Get all case types."""
        return self.get("get_case_types")

    def get_priorities(self) -> List[Dict]:
        """Get all priorities."""
        return self.get("get_priorities")

    def get_templates(self, project_id: int) -> List[Dict]:
        """Get all templates for a project."""
        return self.get(f"get_templates/{project_id}")
