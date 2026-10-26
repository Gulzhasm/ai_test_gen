"""
Infrastructure layer - implementations of interfaces.

Contains:
- ado: Azure DevOps integration
- jira: Jira integration (story source)
- testrail: TestRail integration (test case target)
- export: Output generators (CSV, objectives, summaries)
- repository_factory: Platform-agnostic repository creation
"""
from .ado import (
    ADOHttpClient,
    ADOStoryRepository,
    ADOTestCaseRepository,
    ADOTestSuiteRepository,
    HtmlParser,
)
from .export import CSVConfig, CSVGenerator, ObjectiveGenerator, QASummaryGenerator
from .jira import JiraHttpClient, JiraStoryRepository
from .repository_factory import (
    RepositoryFactory,
    get_story_repository,
    get_test_repositories,
)
from .testrail import (
    TestRailHttpClient,
    TestRailTestCaseRepository,
    TestRailTestSuiteRepository,
)

__all__ = [
    # ADO
    'ADOHttpClient',
    'ADOStoryRepository',
    'ADOTestSuiteRepository',
    'ADOTestCaseRepository',
    'HtmlParser',
    # Jira
    'JiraHttpClient',
    'JiraStoryRepository',
    # TestRail
    'TestRailHttpClient',
    'TestRailTestCaseRepository',
    'TestRailTestSuiteRepository',
    # Export
    'CSVGenerator',
    'CSVConfig',
    'ObjectiveGenerator',
    'QASummaryGenerator',
    # Repository Factory
    'RepositoryFactory',
    'get_story_repository',
    'get_test_repositories',
]
