"""
Test TestRail integration with mock stubs.

This test verifies the TestRail repository works correctly without actual API calls.
"""
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.testrail.testrail_repository import (
    TestRailTestCaseRepository,
    TestRailTestSuiteRepository
)
from infrastructure.testrail.http_client import TestRailHttpClient


class TestTestRailHttpClient:
    """Test the TestRail HTTP client."""

    def test_client_initialization(self):
        """Test client initializes with correct headers."""
        client = TestRailHttpClient(
            base_url='https://test.testrail.io',
            email='test@example.com',
            api_key='test-api-key'
        )
        assert client.base_url == 'https://test.testrail.io'
        assert 'Authorization' in client.headers
        assert 'Basic' in client.headers['Authorization']

    def test_client_requires_credentials(self):
        """Test client requires all credentials."""
        try:
            TestRailHttpClient(
                base_url='https://test.testrail.io',
                email='',
                api_key='test-key'
            )
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert 'Email' in str(e)


class TestTestRailTestSuiteRepository:
    """Test the TestRail suite repository with mocks."""

    @patch('infrastructure.testrail.testrail_repository.TestRailHttpClient')
    def test_find_suite_by_story_id(self, mock_client_class):
        """Test finding a section by story ID."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_client.get_sections.return_value = [
            {'id': 1, 'name': 'General Tests'},
            {'id': 2, 'name': '12345 : User Authentication'},
            {'id': 3, 'name': 'Other Tests'}
        ]

        repo = TestRailTestSuiteRepository(
            base_url='https://test.testrail.io',
            email='test@example.com',
            api_key='test-key',
            project_id=1
        )

        result = repo.find_suite_by_story_id(12345)
        assert result is not None
        assert result['id'] == 2
        assert '12345' in result['name']

    @patch('infrastructure.testrail.testrail_repository.TestRailHttpClient')
    def test_find_suite_not_found(self, mock_client_class):
        """Test handling section not found."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_client.get_sections.return_value = [
            {'id': 1, 'name': 'General Tests'}
        ]

        repo = TestRailTestSuiteRepository(
            base_url='https://test.testrail.io',
            email='test@example.com',
            api_key='test-key',
            project_id=1
        )

        result = repo.find_suite_by_story_id(99999)
        assert result is None

    @patch('infrastructure.testrail.testrail_repository.TestRailHttpClient')
    def test_create_suite(self, mock_client_class):
        """Test creating a new section."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_client.add_section.return_value = {
            'id': 10,
            'name': '12345 : New Feature'
        }

        repo = TestRailTestSuiteRepository(
            base_url='https://test.testrail.io',
            email='test@example.com',
            api_key='test-key',
            project_id=1
        )

        result = repo.create_suite(
            plan_id=1,
            suite_name='12345 : New Feature',
            story_id=12345
        )

        assert result is not None
        assert result['id'] == 10
        assert result['name'] == '12345 : New Feature'


class TestTestRailTestCaseRepository:
    """Test the TestRail test case repository with mocks."""

    @patch('infrastructure.testrail.testrail_repository.TestRailHttpClient')
    def test_create_test_case(self, mock_client_class):
        """Test creating a test case."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_client.add_case.return_value = {
            'id': 100,
            'title': 'Verify user can log in',
            'section_id': 5
        }

        repo = TestRailTestCaseRepository(
            base_url='https://test.testrail.io',
            email='test@example.com',
            api_key='test-key',
            project_id=1,
            default_section_id=5
        )

        test_case_id = repo.create_test_case(
            title='Verify user can log in',
            steps=[
                {'action': 'Navigate to login page', 'expected': 'Login form displayed'},
                {'action': 'Enter valid credentials', 'expected': 'Credentials accepted'},
                {'action': 'Click submit', 'expected': 'User logged in successfully'}
            ],
            objective='Verify basic login functionality'
        )

        assert test_case_id == 100
        mock_client.add_case.assert_called_once()

    @patch('infrastructure.testrail.testrail_repository.TestRailHttpClient')
    def test_create_test_case_without_section(self, mock_client_class):
        """Test creating test case fails without section."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        repo = TestRailTestCaseRepository(
            base_url='https://test.testrail.io',
            email='test@example.com',
            api_key='test-key',
            project_id=1
            # No default_section_id
        )

        test_case_id = repo.create_test_case(
            title='Test Case',
            steps=[],
            objective='Test'
            # No section_id provided
        )

        assert test_case_id is None

    @patch('infrastructure.testrail.testrail_repository.TestRailHttpClient')
    def test_build_steps_separated(self, mock_client_class):
        """Test building TestRail step format."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        repo = TestRailTestCaseRepository(
            base_url='https://test.testrail.io',
            email='test@example.com',
            api_key='test-key',
            project_id=1
        )

        steps = [
            {'action': 'Step 1 action', 'expected': 'Step 1 expected'},
            {'action': 'Step 2 action', 'expected': 'Step 2 expected'}
        ]

        testrail_steps = repo._build_steps_separated(steps)

        assert len(testrail_steps) == 2
        assert testrail_steps[0]['content'] == 'Step 1 action'
        assert testrail_steps[0]['expected'] == 'Step 1 expected'
        assert testrail_steps[1]['content'] == 'Step 2 action'

    @patch('infrastructure.testrail.testrail_repository.TestRailHttpClient')
    def test_bulk_create_test_cases(self, mock_client_class):
        """Test bulk creating test cases."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock returns different IDs for each call
        mock_client.add_case.side_effect = [
            {'id': 101},
            {'id': 102},
            {'id': 103}
        ]

        repo = TestRailTestCaseRepository(
            base_url='https://test.testrail.io',
            email='test@example.com',
            api_key='test-key',
            project_id=1
        )

        test_cases = [
            {'title': 'Test 1', 'steps': [], 'objective': 'Obj 1'},
            {'title': 'Test 2', 'steps': [], 'objective': 'Obj 2'},
            {'title': 'Test 3', 'steps': [], 'objective': 'Obj 3'}
        ]

        created_ids = repo.bulk_create_test_cases(
            section_id=5,
            test_cases=test_cases
        )

        assert len(created_ids) == 3
        assert 101 in created_ids
        assert 102 in created_ids
        assert 103 in created_ids


class TestRepositoryFactoryTestRail:
    """Test the repository factory for TestRail."""

    def test_create_testrail_repositories(self):
        """Test factory creates TestRail repositories."""
        from infrastructure.repository_factory import RepositoryFactory
        from projects.project_config import (
            ProjectConfig, ApplicationConfig, ADOProjectConfig, TestRailConfig
        )

        config = ProjectConfig(
            project_id='test',
            application=ApplicationConfig(name='Test App'),
            ado=ADOProjectConfig(
                organization='not-used',
                project='not-used',
                area_path='not-used'
            ),
            testrail=TestRailConfig(
                base_url='https://test.testrail.io',
                email='test@example.com',
                api_key='test-key',
                project_id=1
            ),
            source_platform='ado',
            target_platform='testrail'
        )

        suite_repo, case_repo = RepositoryFactory.create_test_repositories(config)
        assert suite_repo is not None
        assert case_repo is not None
        assert 'TestRail' in type(suite_repo).__name__
        assert 'TestRail' in type(case_repo).__name__


def run_tests():
    """Run all tests and report results."""
    import traceback

    test_classes = [
        TestTestRailHttpClient,
        TestTestRailTestSuiteRepository,
        TestTestRailTestCaseRepository,
        TestRepositoryFactoryTestRail
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
