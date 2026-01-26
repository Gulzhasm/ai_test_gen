"""Tests for SummaryService."""
import pytest
from core.domain.models import UserStory, TestCase, TestStep, SummaryPlan
from core.services import SummaryService


class TestSummaryService:
    """Tests for SummaryService."""

    @pytest.fixture
    def sample_story(self):
        """Create a sample user story."""
        return UserStory(
            story_id=12345,
            title="As a user, I want to flip objects using the Mirror Tool",
            description="The Mirror Tool enables users to flip selected objects horizontally or vertically.",
            acceptance_criteria="""
            - User can flip objects horizontally
            - User can flip objects vertically
            - Flip operation preserves object proportions
            - Undo/Redo support for flip operations
            - Accessibility: WCAG 2.1 AA compliant
            """
        )

    @pytest.fixture
    def sample_test_cases(self):
        """Create sample test cases."""
        return [
            TestCase(
                test_id="12345-AC1",
                title="12345-AC1: Mirror Tool / Tools Menu / Horizontal Flip",
                steps=[TestStep(index=1, action="Test", expected="Result")],
                area="Tools Menu"
            ),
            TestCase(
                test_id="12345-AC5",
                title="12345-AC5: Mirror Tool / Canvas / Vertical Flip",
                steps=[TestStep(index=1, action="Test", expected="Result")],
                area="Canvas"
            ),
            TestCase(
                test_id="12345-AC10",
                title="12345-AC10: Mirror Tool / Tools Menu / Accessibility (Windows 11)",
                steps=[TestStep(index=1, action="Test", expected="Result")],
                area="Tools Menu",
                is_accessibility=True
            ),
        ]

    def test_service_initialization(self):
        """Test SummaryService initialization."""
        service = SummaryService()
        assert service.llm_provider is None
        assert service.debug is False

    def test_service_with_debug(self):
        """Test SummaryService with debug enabled."""
        service = SummaryService(debug=True)
        assert service.debug is True

    def test_generate_summary_returns_tuple(self, sample_story, sample_test_cases):
        """Test that generate_summary returns proper tuple."""
        service = SummaryService()
        result = service.generate_summary(sample_story, sample_test_cases)

        assert isinstance(result, tuple)
        assert len(result) == 3
        summary_text, plan, lint_result = result
        assert isinstance(summary_text, str)
        assert isinstance(plan, SummaryPlan)

    def test_summary_contains_intro(self, sample_story, sample_test_cases):
        """Test that summary contains introduction."""
        service = SummaryService()
        summary_text, _, _ = service.generate_summary(sample_story, sample_test_cases)

        assert "work item" in summary_text.lower() or "introduces" in summary_text.lower()

    def test_summary_contains_bullets(self, sample_story, sample_test_cases):
        """Test that summary contains bullet points."""
        service = SummaryService()
        summary_text, _, _ = service.generate_summary(sample_story, sample_test_cases)

        assert "•" in summary_text or "Testing will focus on" in summary_text

    def test_summary_contains_accessibility(self, sample_story, sample_test_cases):
        """Test that summary contains accessibility section."""
        service = SummaryService()
        summary_text, _, _ = service.generate_summary(sample_story, sample_test_cases)

        assert "accessibility" in summary_text.lower()
        assert "wcag" in summary_text.lower() or "508" in summary_text.lower()

    def test_summary_contains_platform(self, sample_story, sample_test_cases):
        """Test that summary contains platform section."""
        service = SummaryService()
        summary_text, _, _ = service.generate_summary(sample_story, sample_test_cases)

        assert "windows" in summary_text.lower() or "tablet" in summary_text.lower()

    def test_plan_has_required_fields(self, sample_story, sample_test_cases):
        """Test that plan has all required fields."""
        service = SummaryService()
        _, plan, _ = service.generate_summary(sample_story, sample_test_cases)

        assert plan.intro_facts is not None
        assert plan.bullet_themes is not None
        assert plan.dependencies is not None
        assert plan.accessibility_clause is not None
        assert plan.platform_clause is not None

    def test_plan_bullets_not_empty(self, sample_story, sample_test_cases):
        """Test that plan has bullet themes."""
        service = SummaryService()
        _, plan, _ = service.generate_summary(sample_story, sample_test_cases)

        assert len(plan.bullet_themes) > 0


class TestSummaryServiceHelpers:
    """Tests for SummaryService helper methods."""

    def test_extract_feature_name(self):
        """Test feature name extraction from title."""
        service = SummaryService()

        # Simple title
        name = service._extract_feature_name("Mirror Tool")
        assert name == "Mirror Tool"

        # User story format
        name = service._extract_feature_name("As a user, I want to flip objects")
        assert "flip" in name.lower()

    def test_extract_behaviors(self):
        """Test behavior extraction from AC text."""
        service = SummaryService()

        ac_text = "User can flip, rotate, and select objects. Display results clearly."
        behaviors = service._extract_behaviors(ac_text)

        assert "flip" in behaviors
        assert "rotate" in behaviors
        assert "select" in behaviors
        assert "display" in behaviors

    def test_parse_ac(self):
        """Test AC parsing into bullets."""
        service = SummaryService()

        ac_text = """
        - First criterion
        - Second criterion
        - Third criterion
        """

        bullets = service._parse_ac(ac_text)
        assert len(bullets) >= 3

    def test_parse_ac_numbered(self):
        """Test AC parsing with numbered items."""
        service = SummaryService()

        ac_text = """
        1. First criterion
        2. Second criterion
        3) Third criterion
        """

        bullets = service._parse_ac(ac_text)
        assert len(bullets) >= 3

    def test_format_ui_surface_single(self):
        """Test UI surface formatting with single entry."""
        service = SummaryService()

        result = service._format_ui_surface(["Tools Menu"])
        assert "Tools Menu" in result

    def test_format_ui_surface_multiple(self):
        """Test UI surface formatting with multiple entries."""
        service = SummaryService()

        result = service._format_ui_surface(["Tools Menu", "Canvas", "Properties Panel"])
        assert "Tools Menu" in result
        assert "Canvas" in result
        assert "Properties Panel" in result


class TestSummaryServiceEdgeCases:
    """Edge case tests for SummaryService."""

    def test_empty_test_cases(self):
        """Test with empty test case list."""
        service = SummaryService()
        story = UserStory(
            story_id=12345,
            title="Test Story",
            description="Description",
            acceptance_criteria="AC items"
        )

        summary_text, plan, lint_result = service.generate_summary(story, [])
        assert isinstance(summary_text, str)

    def test_minimal_story(self):
        """Test with minimal story data."""
        service = SummaryService()
        story = UserStory(
            story_id=12345,
            title="Test",
            description="",
            acceptance_criteria=""
        )

        test_cases = [
            TestCase(
                test_id="12345-AC1",
                title="Test",
                steps=[TestStep(index=1, action="Test", expected="Result")],
                area="Area"
            )
        ]

        summary_text, plan, lint_result = service.generate_summary(story, test_cases)
        assert isinstance(summary_text, str)
        assert len(summary_text) > 0
