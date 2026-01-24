"""Tests for services."""
import pytest
from models import UserStory, TestCase, TestStep, EvidenceModel
from services import SummaryService, ObjectiveService


def test_summary_service_no_llm():
    """Test SummaryService generates deterministic output."""
    service = SummaryService(llm_provider=None, debug=False)
    
    story = UserStory(
        story_id=12345,
        title="As a user, I want Mirror Tool",
        description="The Mirror Tool flips objects horizontally or vertically.",
        acceptance_criteria="""
• Tool can be activated from Tools Menu
• Horizontal flip option is available
• Vertical flip option is available
• Object proportions remain unchanged
• Selection scope is limited to selected objects
• Undo/Redo is supported
"""
    )
    
    steps = [
        TestStep(index=1, action="PRE-REQ: ENV QuickDraw application is installed", expected=""),
        TestStep(index=2, action="Launch ENV QuickDraw application.", expected=""),
        TestStep(index=3, action="Close/Exit the QuickDraw application.", expected="")
    ]
    
    test_cases = [
        TestCase(
            test_id="12345-AC1",
            title="12345-AC1: Mirror Tool / Tools Menu / Activate Tool",
            steps=steps,
            area="Tools Menu",
            objective="Verify that the Mirror Tool can be activated from the Tools Menu."
        ),
        TestCase(
            test_id="12345-005",
            title="12345-005: Mirror Tool / Canvas / Horizontal Flip",
            steps=steps,
            area="Canvas",
            objective="Verify that horizontal flip works correctly."
        )
    ]
    
    summary_text, plan, lint_result = service.generate_summary(story, test_cases)
    
    # Check basic structure
    assert "This work item introduces" in summary_text
    assert "Testing will focus on verifying:" in summary_text
    assert "Functional dependencies include" in summary_text
    assert "Accessibility testing will validate" in summary_text
    assert "Tests will be executed on" in summary_text
    
    # Check plan structure
    assert len(plan.bullet_themes) >= 6
    assert len(plan.bullet_themes) <= 9
    assert len(plan.dependencies) > 0
    
    # Check lint passed (deterministic should always pass)
    assert lint_result.ok is True


def test_summary_service_evidence_model():
    """Test SummaryService builds correct evidence model."""
    service = SummaryService(llm_provider=None, debug=False)
    
    story = UserStory(
        story_id=12345,
        title="Test Story",
        description="Tool flips objects on canvas",
        acceptance_criteria="Tool can be activated from Tools Menu"
    )
    
    steps = [TestStep(index=1, action="Test", expected="")]
    test_cases = [
        TestCase(
            test_id="12345-AC1",
            title="12345-AC1: Test / Tools Menu / Test",
            steps=steps,
            area="Tools Menu"
        )
    ]
    
    evidence = service._build_evidence(story, test_cases)
    
    assert evidence.description_text == story.description
    assert evidence.ac_text == story.acceptance_criteria
    assert len(evidence.test_titles) == 1
    assert "Tools Menu" in evidence.allowed_entry_points


def test_objective_service_no_llm():
    """Test ObjectiveService generates deterministic objectives."""
    service = ObjectiveService(llm_provider=None, debug=False)
    
    evidence = EvidenceModel(
        description_text="Tool flips objects",
        ac_text="Tool can be activated",
        test_titles=[]
    )
    
    steps = [TestStep(index=1, action="Test", expected="")]
    test_cases = [
        TestCase(
            test_id="12345-AC1",
            title="12345-AC1: Mirror Tool / Tools Menu / Activate Tool",
            steps=steps,
            area="Tools Menu",
            objective="Verify that the Mirror Tool can be activated from the Tools Menu."
        ),
        TestCase(
            test_id="12345-005",
            title="12345-005: Mirror Tool / Canvas / Horizontal Flip",
            steps=steps,
            area="Canvas",
            objective="Verify that horizontal flip works correctly."
        )
    ]
    
    objectives, lint_result = service.generate_objectives(test_cases, evidence)
    
    # Check count matches
    assert len(objectives) == len(test_cases)
    
    # Check objectives match test case IDs
    for obj, tc in zip(objectives, test_cases):
        assert obj.test_id == tc.test_id
        assert obj.title == tc.title
        assert obj.objective_text.startswith("Verify that")


def test_objective_service_default_generation():
    """Test ObjectiveService generates default objectives."""
    service = ObjectiveService(llm_provider=None, debug=False)
    
    steps = [TestStep(index=1, action="Test", expected="")]
    tc = TestCase(
        test_id="12345-AC1",
        title="12345-AC1: Mirror Tool / Tools Menu / Activate Tool",
        steps=steps,
        area="Tools Menu",
        objective=None  # No objective provided
    )
    
    default_obj = service._generate_default_objective(tc)
    
    assert "Verify that" in default_obj
    assert default_obj.endswith(".")
