"""Tests for domain models."""
import pytest
from models import (
    UserStory, TestCase, TestStep, Objective,
    SummaryPlan, EvidenceModel, LintResult
)


def test_user_story_creation():
    """Test UserStory model creation."""
    story = UserStory(
        story_id=12345,
        title="Test Story",
        description="Test description",
        acceptance_criteria="Test AC"
    )
    
    assert story.story_id == 12345
    assert story.title == "Test Story"
    assert story.description == "Test description"
    assert story.acceptance_criteria == "Test AC"


def test_user_story_to_dict():
    """Test UserStory.to_dict() conversion."""
    story = UserStory(
        story_id=12345,
        title="Test Story",
        description="Test description",
        acceptance_criteria="Test AC"
    )
    
    story_dict = story.to_dict()
    assert story_dict['story_id'] == 12345
    assert story_dict['title'] == "Test Story"
    assert story_dict['description_text'] == "Test description"
    assert story_dict['acceptance_criteria_text'] == "Test AC"


def test_test_case_creation():
    """Test TestCase model creation."""
    steps = [
        TestStep(index=1, action="Step 1", expected="Expected 1"),
        TestStep(index=2, action="Step 2", expected="")
    ]
    
    tc = TestCase(
        test_id="12345-AC1",
        title="Test Title",
        steps=steps,
        area="Tools Menu",
        requires_object=True,
        is_accessibility=False
    )
    
    assert tc.test_id == "12345-AC1"
    assert tc.title == "Test Title"
    assert len(tc.steps) == 2
    assert tc.area == "Tools Menu"
    assert tc.requires_object is True


def test_evidence_model_is_supported():
    """Test EvidenceModel.is_supported()."""
    evidence = EvidenceModel(
        description_text="The mirror tool flips objects horizontally",
        ac_text="Tool can be activated from Tools Menu",
        test_titles=["Test 1: Mirror Tool / Canvas / Flip"]
    )
    
    # Should find exact matches
    assert evidence.is_supported("mirror") is True
    assert evidence.is_supported("tools menu") is True
    assert evidence.is_supported("canvas") is True
    
    # Should not find unsupported terms
    assert evidence.is_supported("invented term") is False


def test_evidence_model_is_forbidden():
    """Test EvidenceModel.is_forbidden()."""
    evidence = EvidenceModel(
        forbidden_words=['assumingly', 'generally']
    )
    
    assert evidence.is_forbidden("assumingly") is True
    assert evidence.is_forbidden("generally speaking") is True
    assert evidence.is_forbidden("normal word") is False


def test_lint_result():
    """Test LintResult operations."""
    result = LintResult(ok=True)
    
    assert result.ok is True
    assert len(result.errors) == 0
    
    result.add_error("Error 1")
    assert result.ok is False
    assert len(result.errors) == 1
    
    result.add_warning("Warning 1")
    assert len(result.warnings) == 1


def test_summary_plan_validation():
    """Test SummaryPlan validation."""
    # Valid plan
    plan = SummaryPlan(
        intro_facts="This work item introduces the Mirror Tool.",
        bullet_themes=["Bullet 1", "Bullet 2", "Bullet 3", "Bullet 4", "Bullet 5", "Bullet 6"],
        dependencies=["menu navigation", "canvas rendering"],
        accessibility_clause="Accessibility testing will validate...",
        platform_clause="Tests will be executed on..."
    )
    
    is_valid, errors = plan.validate()
    assert is_valid is True
    assert len(errors) == 0
    
    # Invalid plan (too few bullets)
    plan_invalid = SummaryPlan(
        intro_facts="Short intro",
        bullet_themes=["Bullet 1", "Bullet 2"],  # Only 2 bullets
        dependencies=["dep 1"],
        accessibility_clause="Accessibility clause",
        platform_clause="Platform clause"
    )
    
    is_valid, errors = plan_invalid.validate()
    assert is_valid is False
    assert any("Too few bullets" in err for err in errors)
