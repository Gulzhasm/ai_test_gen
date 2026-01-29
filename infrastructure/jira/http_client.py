"""
Jira HTTP Client - Low-level HTTP interactions with Jira Cloud/Server.

This class handles only HTTP concerns, keeping infrastructure separate from domain logic.
"""
import base64
from typing import Dict, Optional, Any, List
import requests


class JiraHttpClient:
    """Low-level HTTP client for Jira API."""

    API_VERSION = "3"  # Jira Cloud REST API v3

    def __init__(
        self,
        base_url: str,
        email: str,
        api_token: str,
        timeout: int = 30,
        is_cloud: bool = True
    ):
        """Initialize Jira HTTP client.

        Args:
            base_url: Jira instance URL (e.g., "https://company.atlassian.net")
            email: User email for authentication
            api_token: API token (Cloud) or password (Server)
            timeout: Request timeout in seconds
            is_cloud: True for Jira Cloud, False for Jira Server/Data Center
        """
        if not api_token:
            raise ValueError("API token is required")
        if not base_url:
            raise ValueError("Base URL is required")
        if not email:
            raise ValueError("Email is required")

        self._base_url = base_url.rstrip('/')
        self._email = email
        self._api_token = api_token
        self._timeout = timeout
        self._is_cloud = is_cloud
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
        # Jira Cloud uses Basic Auth with email:api_token
        # Jira Server uses Basic Auth with username:password
        credentials = base64.b64encode(
            f"{self._email}:{self._api_token}".encode()
        ).decode()
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {credentials}',
            'Accept': 'application/json'
        }

    def _get_api_base(self) -> str:
        """Get the appropriate API base URL."""
        if self._is_cloud:
            return f"{self._base_url}/rest/api/{self.API_VERSION}"
        else:
            # Jira Server uses /rest/api/2
            return f"{self._base_url}/rest/api/2"

    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make GET request to Jira API.

        Args:
            endpoint: API endpoint (relative to API base)
            params: Optional query parameters

        Returns:
            JSON response as dictionary

        Raises:
            requests.HTTPError: If request fails
        """
        url = f"{self._get_api_base()}/{endpoint}"

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
        data: Dict[str, Any],
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make POST request to Jira API.

        Args:
            endpoint: API endpoint
            data: Request body
            params: Optional query parameters

        Returns:
            JSON response as dictionary
        """
        url = f"{self._get_api_base()}/{endpoint}"

        response = requests.post(
            url,
            headers=self._headers,
            json=data,
            params=params,
            timeout=self._timeout
        )
        response.raise_for_status()
        return response.json()

    def put(
        self,
        endpoint: str,
        data: Dict[str, Any],
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make PUT request to Jira API.

        Args:
            endpoint: API endpoint
            data: Request body
            params: Optional query parameters

        Returns:
            JSON response as dictionary
        """
        url = f"{self._get_api_base()}/{endpoint}"

        response = requests.put(
            url,
            headers=self._headers,
            json=data,
            params=params,
            timeout=self._timeout
        )
        response.raise_for_status()
        return response.json()

    def search_issues(
        self,
        jql: str,
        fields: Optional[List[str]] = None,
        start_at: int = 0,
        max_results: int = 50
    ) -> Dict[str, Any]:
        """Search issues using JQL.

        Args:
            jql: JQL query string
            fields: List of fields to return (None for all)
            start_at: Starting index for pagination
            max_results: Maximum results per page

        Returns:
            Search results with issues
        """
        data = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results
        }
        if fields:
            data["fields"] = fields

        return self.post("search", data)

    def get_issue(
        self,
        issue_key: str,
        fields: Optional[List[str]] = None,
        expand: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get a single issue by key.

        Args:
            issue_key: Issue key (e.g., "PROJ-123")
            fields: List of fields to return
            expand: List of expansions (e.g., ["changelog", "renderedFields"])

        Returns:
            Issue data
        """
        params = {}
        if fields:
            params['fields'] = ','.join(fields)
        if expand:
            params['expand'] = ','.join(expand)

        return self.get(f"issue/{issue_key}", params=params or None)

    def get_issue_comments(
        self,
        issue_key: str,
        start_at: int = 0,
        max_results: int = 50
    ) -> Dict[str, Any]:
        """Get comments for an issue.

        Args:
            issue_key: Issue key
            start_at: Starting index
            max_results: Maximum results

        Returns:
            Comments data
        """
        params = {
            "startAt": start_at,
            "maxResults": max_results
        }
        return self.get(f"issue/{issue_key}/comment", params=params)
