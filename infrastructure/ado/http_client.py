"""
ADO HTTP Client - Low-level HTTP interactions with Azure DevOps.

This class handles only HTTP concerns, keeping infrastructure separate from domain logic.
"""
import base64
from typing import Any

import requests


class ADOHttpClient:
    """Low-level HTTP client for Azure DevOps API."""

    API_VERSION = "7.1"

    def __init__(
        self,
        organization: str,
        project: str,
        pat: str,
        timeout: int = 30
    ):
        """Initialize ADO HTTP client.

        Args:
            organization: ADO organization name
            project: ADO project name
            pat: Personal Access Token
            timeout: Request timeout in seconds
        """
        if not pat:
            raise ValueError("Personal Access Token (PAT) is required")
        if not organization:
            raise ValueError("Organization name is required")
        if not project:
            raise ValueError("Project name is required")

        self._organization = organization
        self._project = project
        self._pat = pat
        self._timeout = timeout
        self._base_url = f"https://dev.azure.com/{organization}/{project}"
        self._headers = self._create_headers()

    @property
    def base_url(self) -> str:
        """Base URL for API calls."""
        return self._base_url

    @property
    def headers(self) -> dict[str, str]:
        """Headers for API calls."""
        return self._headers.copy()

    def _create_headers(self) -> dict[str, str]:
        """Create authentication headers."""
        credentials = base64.b64encode(f":{self._pat}".encode()).decode()
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {credentials}'
        }

    def get(self, endpoint: str, params: dict | None = None) -> dict[str, Any]:
        """Make GET request to ADO API.

        Args:
            endpoint: API endpoint (relative to base URL)
            params: Optional query parameters

        Returns:
            JSON response as dictionary

        Raises:
            requests.HTTPError: If request fails
        """
        url = f"{self._base_url}/{endpoint}"
        if 'api-version' not in (params or {}):
            params = params or {}
            params['api-version'] = self.API_VERSION

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
        data: dict[str, Any],
        params: dict | None = None
    ) -> dict[str, Any]:
        """Make POST request to ADO API.

        Args:
            endpoint: API endpoint
            data: Request body
            params: Optional query parameters

        Returns:
            JSON response as dictionary
        """
        url = f"{self._base_url}/{endpoint}"
        if 'api-version' not in (params or {}):
            params = params or {}
            params['api-version'] = self.API_VERSION

        response = requests.post(
            url,
            headers=self._headers,
            json=data,
            params=params,
            timeout=self._timeout
        )
        response.raise_for_status()
        return response.json()

    def patch(
        self,
        endpoint: str,
        data: Any,
        content_type: str = 'application/json-patch+json',
        params: dict | None = None
    ) -> dict[str, Any]:
        """Make PATCH request to ADO API.

        Args:
            endpoint: API endpoint
            data: Request body
            content_type: Content type header
            params: Optional query parameters

        Returns:
            JSON response as dictionary
        """
        url = f"{self._base_url}/{endpoint}"
        if 'api-version' not in (params or {}):
            params = params or {}
            params['api-version'] = self.API_VERSION

        headers = self._headers.copy()
        headers['Content-Type'] = content_type

        response = requests.patch(
            url,
            headers=headers,
            json=data,
            params=params,
            timeout=self._timeout
        )
        response.raise_for_status()
        return response.json()

    def execute_wiql(self, query: str) -> dict[str, Any]:
        """Execute a WIQL query.

        Args:
            query: WIQL query string

        Returns:
            Query results
        """
        return self.post("_apis/wit/wiql", {"query": query})
