"""
Repository factory for platform-agnostic data access.

Creates the appropriate repository implementations based on configuration.
"""
from typing import Optional, Tuple

from core.interfaces.repository import (
    IStoryRepository,
    ITestSuiteRepository,
    ITestCaseRepository
)
from projects.project_config import ProjectConfig

# Import platform-specific implementations
from infrastructure.ado.ado_repository import (
    ADOStoryRepository,
    ADOTestSuiteRepository,
    ADOTestCaseRepository
)
from infrastructure.jira.jira_repository import JiraStoryRepository
from infrastructure.testrail.testrail_repository import (
    TestRailTestSuiteRepository,
    TestRailTestCaseRepository
)


class RepositoryFactory:
    """
    Factory for creating platform-appropriate repository instances.

    Supports:
    - Source platforms: ADO, Jira (for fetching stories)
    - Target platforms: ADO, TestRail (for uploading test cases)
    """

    @staticmethod
    def create_story_repository(config: ProjectConfig) -> IStoryRepository:
        """
        Create a story repository based on the source platform configuration.

        Args:
            config: Project configuration

        Returns:
            Story repository implementation

        Raises:
            ValueError: If source platform is not supported
        """
        source_platform = config.source_platform.lower()

        if source_platform == 'ado':
            return ADOStoryRepository(config.ado)

        elif source_platform == 'jira':
            if not config.jira:
                raise ValueError(
                    "Jira configuration required when source_platform='jira'. "
                    "Add 'jira' section to your project config."
                )
            return JiraStoryRepository(
                base_url=config.jira.base_url,
                email=config.jira.email,
                api_token=config.jira.api_token,
                project_key=config.jira.project_key,
                ac_field_name=config.jira.ac_field_name,
                is_cloud=config.jira.is_cloud
            )

        else:
            raise ValueError(
                f"Unsupported source platform: '{source_platform}'. "
                f"Supported platforms: 'ado', 'jira'"
            )

    @staticmethod
    def create_test_repositories(
        config: ProjectConfig
    ) -> Tuple[ITestSuiteRepository, ITestCaseRepository]:
        """
        Create test suite and test case repositories based on target platform.

        Args:
            config: Project configuration

        Returns:
            Tuple of (suite_repository, test_case_repository)

        Raises:
            ValueError: If target platform is not supported
        """
        target_platform = config.target_platform.lower()

        if target_platform == 'ado':
            suite_repo = ADOTestSuiteRepository(config.ado)
            case_repo = ADOTestCaseRepository(config.ado)
            return suite_repo, case_repo

        elif target_platform == 'testrail':
            if not config.testrail:
                raise ValueError(
                    "TestRail configuration required when target_platform='testrail'. "
                    "Add 'testrail' section to your project config."
                )
            suite_repo = TestRailTestSuiteRepository(
                base_url=config.testrail.base_url,
                email=config.testrail.email,
                api_key=config.testrail.api_key,
                project_id=config.testrail.project_id,
                suite_id=config.testrail.suite_id
            )
            case_repo = TestRailTestCaseRepository(
                base_url=config.testrail.base_url,
                email=config.testrail.email,
                api_key=config.testrail.api_key,
                project_id=config.testrail.project_id,
                suite_id=config.testrail.suite_id,
                default_section_id=config.testrail.default_section_id
            )
            return suite_repo, case_repo

        else:
            raise ValueError(
                f"Unsupported target platform: '{target_platform}'. "
                f"Supported platforms: 'ado', 'testrail'"
            )

    @staticmethod
    def create_all_repositories(
        config: ProjectConfig
    ) -> Tuple[IStoryRepository, ITestSuiteRepository, ITestCaseRepository]:
        """
        Create all repositories needed for the full workflow.

        Args:
            config: Project configuration

        Returns:
            Tuple of (story_repository, suite_repository, test_case_repository)
        """
        story_repo = RepositoryFactory.create_story_repository(config)
        suite_repo, case_repo = RepositoryFactory.create_test_repositories(config)
        return story_repo, suite_repo, case_repo


def get_story_repository(config: ProjectConfig) -> IStoryRepository:
    """Convenience function to get story repository."""
    return RepositoryFactory.create_story_repository(config)


def get_test_repositories(
    config: ProjectConfig
) -> Tuple[ITestSuiteRepository, ITestCaseRepository]:
    """Convenience function to get test repositories."""
    return RepositoryFactory.create_test_repositories(config)
