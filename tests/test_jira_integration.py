"""
Test Jira integration with mock stubs.

This test verifies the Jira repository works correctly without actual API calls.
"""
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.jira.jira_repository import JiraStoryRepository, JiraHtmlParser
from infrastructure.jira.http_client import JiraHttpClient
from core.domain.story import UserStory


class TestJiraHtmlParser:
    """Test the Jira HTML/ADF parser."""

    def test_parse_html_bulleted_list(self):
        """Test parsing HTML with bullet list."""
        html = """
        <ul>
            <li>User can log in with valid credentials</li>
            <li>User sees error message with invalid credentials</li>
            <li>Session expires after 30 minutes of inactivity</li>
        </ul>
        """
        result = JiraHtmlParser.normalize_to_text(html)
        assert "User can log in" in result
        assert "User sees error message" in result
        assert "Session expires" in result

    def test_parse_adf_document(self):
        """Test parsing Atlassian Document Format."""
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "Acceptance Criteria:"}
                    ]
                },
                {
                    "type": "bulletList",
                    "content": [
                        {
                            "type": "listItem",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [
                                        {"type": "text", "text": "User can create new account"}
                                    ]
                                }
                            ]
                        },
                        {
                            "type": "listItem",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [
                                        {"type": "text", "text": "Email verification is sent"}
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        result = JiraHtmlParser.normalize_to_text(adf)
        assert "Acceptance Criteria" in result
        assert "User can create new account" in result
        assert "Email verification" in result

    def test_parse_acceptance_criteria(self):
        """Test parsing AC into bullets."""
        ac_text = """
        • User can log in with valid credentials
        • User sees dashboard after login
        • User can log out from any page
        """
        bullets = JiraHtmlParser.parse_acceptance_criteria(ac_text)
        assert len(bullets) == 3
        assert "log in with valid credentials" in bullets[0]
        assert "dashboard after login" in bullets[1]
        assert "log out from any page" in bullets[2]


class TestJiraStoryRepository:
    """Test the Jira story repository with mocks."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = Mock(spec=JiraHttpClient)

    @patch('infrastructure.jira.jira_repository.JiraHttpClient')
    def test_get_story_success(self, mock_client_class):
        """Test fetching a story successfully."""
        # Setup mock response
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_client.get_issue.return_value = {
            'key': 'PROJ-123',
            'fields': {
                'summary': 'User Authentication Feature',
                'description': {
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": "Implement user authentication"}
                            ]
                        }
                    ]
                },
                'customfield_10100': {  # AC field
                    "type": "doc",
                    "content": [
                        {
                            "type": "bulletList",
                            "content": [
                                {
                                    "type": "listItem",
                                    "content": [
                                        {
                                            "type": "paragraph",
                                            "content": [
                                                {"type": "text", "text": "User can log in with email and password"}
                                            ]
                                        }
                                    ]
                                },
                                {
                                    "type": "listItem",
                                    "content": [
                                        {
                                            "type": "paragraph",
                                            "content": [
                                                {"type": "text", "text": "User receives error for invalid credentials"}
                                            ]
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            },
            'renderedFields': {}
        }

        # Mock field discovery
        mock_client.get.return_value = [
            {'id': 'customfield_10100', 'name': 'Acceptance Criteria'}
        ]

        # Create repository and fetch story
        repo = JiraStoryRepository(
            base_url='https://test.atlassian.net',
            email='test@example.com',
            api_token='test-token',
            project_key='PROJ',
            ac_field_name='customfield_10100'
        )

        story = repo.get_story(123)

        # Verify
        assert story is not None
        assert story.title == 'User Authentication Feature'
        assert len(story.acceptance_criteria) >= 1

    @patch('infrastructure.jira.jira_repository.JiraHttpClient')
    def test_get_story_not_found(self, mock_client_class):
        """Test handling story not found."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_issue.side_effect = Exception("Issue not found")

        repo = JiraStoryRepository(
            base_url='https://test.atlassian.net',
            email='test@example.com',
            api_token='test-token',
            project_key='PROJ'
        )

        story = repo.get_story(999)
        assert story is None

    @patch('infrastructure.jira.jira_repository.JiraHttpClient')
    def test_get_qa_prep_from_subtask(self, mock_client_class):
        """Test fetching QA prep from subtask."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Parent issue with subtasks
        mock_client.get_issue.side_effect = [
            {
                'key': 'PROJ-123',
                'fields': {
                    'summary': 'Main Story',
                    'subtasks': [
                        {
                            'key': 'PROJ-124',
                            'fields': {'summary': 'QA Prep for PROJ-123'}
                        }
                    ],
                    'issuelinks': []
                }
            },
            # QA Prep subtask
            {
                'key': 'PROJ-124',
                'fields': {
                    'summary': 'QA Prep for PROJ-123',
                    'description': 'Test environment setup instructions...'
                }
            }
        ]

        repo = JiraStoryRepository(
            base_url='https://test.atlassian.net',
            email='test@example.com',
            api_token='test-token',
            project_key='PROJ'
        )

        qa_prep = repo.get_qa_prep(123)
        assert qa_prep is not None
        assert 'Test environment' in qa_prep


class TestRepositoryFactory:
    """Test the repository factory selects correct implementations."""

    def test_create_ado_story_repository(self):
        """Test factory creates ADO repository for ADO config."""
        from infrastructure.repository_factory import RepositoryFactory
        from projects.project_config import ProjectConfig, ApplicationConfig, ADOProjectConfig

        config = ProjectConfig(
            project_id='test',
            application=ApplicationConfig(name='Test App'),
            ado=ADOProjectConfig(
                organization='test-org',
                project='test-project',
                area_path='Test\\Path',
                pat='test-pat'
            ),
            source_platform='ado',
            target_platform='ado'
        )

        # This should create ADO repository
        repo = RepositoryFactory.create_story_repository(config)
        assert repo is not None
        assert 'ADO' in type(repo).__name__

    def test_create_jira_story_repository(self):
        """Test factory creates Jira repository for Jira config."""
        from infrastructure.repository_factory import RepositoryFactory
        from projects.project_config import (
            ProjectConfig, ApplicationConfig, ADOProjectConfig, JiraProjectConfig
        )

        config = ProjectConfig(
            project_id='test',
            application=ApplicationConfig(name='Test App'),
            ado=ADOProjectConfig(
                organization='not-used',
                project='not-used',
                area_path='not-used'
            ),
            jira=JiraProjectConfig(
                base_url='https://test.atlassian.net',
                project_key='TEST',
                email='test@example.com',
                api_token='test-token'
            ),
            source_platform='jira',
            target_platform='ado'
        )

        # This should create Jira repository
        repo = RepositoryFactory.create_story_repository(config)
        assert repo is not None
        assert 'Jira' in type(repo).__name__


def run_tests():
    """Run all tests and report results."""
    import traceback

    test_classes = [
        TestJiraHtmlParser,
        TestJiraStoryRepository,
        TestRepositoryFactory
    ]

    total_tests = 0
    passed_tests = 0
    failed_tests = []

    for test_class in test_classes:
        instance = test_class()
        print(f"\nRunning {test_class.__name__}")

        test_methods = [m for m in dir(instance) if m.startswith('test_')]

        for method_name in test_methods:
            total_tests += 1
            method = getattr(instance, method_name)

            if hasattr(instance, 'setup_method'):
                instance.setup_method()

            try:
                method()
                print(f"  PASS: {method_name}")
                passed_tests += 1
            except Exception as e:
                print(f"  FAIL: {method_name}: {e}")
                failed_tests.append((test_class.__name__, method_name, traceback.format_exc()))

    print(f"\nTEST SUMMARY")
    print(f"Total: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {len(failed_tests)}")

    if failed_tests:
        print(f"\nFailed tests:")
        for class_name, method_name, tb in failed_tests:
            print(f"\n  {class_name}.{method_name}:")
            for line in tb.split('\n')[-5:]:
                if line.strip():
                    print(f"    {line}")

    return len(failed_tests) == 0


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
