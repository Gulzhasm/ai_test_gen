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
    ADOTestSuiteRepository,
    ADOTestCaseRepository,
    HtmlParser
)
from .jira import (
    JiraHttpClient,
    JiraStoryRepository
)
from .testrail import (
    TestRailHttpClient,
    TestRailTestCaseRepository,
    TestRailTestSuiteRepository
)
from .export import (
    CSVGenerator,
    CSVConfig,
    ObjectiveGenerator,
    QASummaryGenerator
)
from .repository_factory import (
    RepositoryFactory,
    get_story_repository,
    get_test_repositories
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
