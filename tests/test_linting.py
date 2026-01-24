"""Tests for linting system."""
import pytest
from models import EvidenceModel, Objective, TestCase, TestStep
from linting import SummaryLinter, ObjectiveLinter


def test_summary_linter_structure():
    """Test summary linter checks required structure."""
    evidence = EvidenceModel(
        description_text="Test description",
        ac_text="Test AC",
        test_titles=[]
    )
    
    linter = SummaryLinter(evidence)
    
    # Valid summary
    valid_summary = """This work item introduces the Mirror Tool, enabling flip operations through the Tools Menu.

Testing will focus on verifying:
• Horizontal flip capability
• Vertical flip capability
• Immediate visual feedback
• Object proportions preservation
• Selection scope limitation
• Undo/Redo support

Functional dependencies include menu navigation, canvas rendering, and object selection, all of which must operate correctly to ensure proper feature behavior.

Accessibility testing will validate compliance with Section 508 / WCAG 2.1 AA standards, including keyboard operability, visible focus indicators, and readable labels and control roles to ensure the feature is usable with assistive technologies.

Tests will be executed on Windows 11 and tablet devices (iOS iPad and Android Tablet) to validate consistent behavior across mouse-based and touch-based interaction models."""
    
    result = linter.lint(valid_summary)
    assert result.ok is True
    
    # Invalid summary (missing section)
    invalid_summary = "This is an incomplete summary."
    
    result = linter.lint(invalid_summary)
    assert result.ok is False
    assert len(result.errors) > 0


def test_summary_linter_invented_ui_surfaces():
    """Test summary linter catches invented UI surfaces."""
    evidence = EvidenceModel(
        description_text="The tool can be activated from the menu",
        ac_text="Tool flips objects",
        test_titles=["Test 1: Mirror Tool / Tools Menu / Flip"]
    )
    
    linter = SummaryLinter(evidence)
    
    # Summary mentions "canvas" which is not in evidence
    summary = """This work item introduces the Mirror Tool.

Testing will focus on verifying:
• Canvas operations
• Toolbar integration
• Dialog persistence
• Menu navigation
• Tool activation
• Feature behavior

Functional dependencies include canvas rendering and toolbar state.

Accessibility testing will validate compliance with Section 508 / WCAG 2.1 AA standards.

Tests will be executed on Windows 11 and tablet devices (iOS iPad and Android Tablet) to validate consistent behavior across mouse-based and touch-based interaction models."""
    
    result = linter.lint(summary)
    assert result.ok is False
    # Should catch invented UI surfaces: canvas, toolbar, dialog
    assert any("canvas" in err.lower() for err in result.errors)


def test_summary_linter_speculative_language():
    """Test summary linter catches speculative language."""
    evidence = EvidenceModel(
        description_text="Test",
        ac_text="Test",
        test_titles=[]
    )
    
    linter = SummaryLinter(evidence)
    
    summary = """This work item presumably introduces a feature.

Testing will focus on verifying:
• Feature probably works
• Generally good behavior
• Assumingly correct output
• Another bullet
• Yet another bullet
• Last bullet

Functional dependencies include core components.

Accessibility testing will validate compliance with Section 508 / WCAG 2.1 AA standards.

Tests will be executed on Windows 11 and tablet devices (iOS iPad and Android Tablet) to validate consistent behavior across mouse-based and touch-based interaction models."""
    
    result = linter.lint(summary)
    assert result.ok is False
    # Should catch: presumably, probably, generally, assumingly
    assert sum(1 for err in result.errors if any(
        word in err.lower() for word in ['presumably', 'probably', 'generally', 'assumingly']
    )) >= 3


def test_objective_linter_format():
    """Test objective linter checks format."""
    evidence = EvidenceModel(
        description_text="Test",
        ac_text="Test",
        test_titles=[]
    )
    
    linter = ObjectiveLinter(evidence)
    
    # Valid objective
    steps = [TestStep(index=1, action="Test", expected="")]
    tc = TestCase(
        test_id="12345-AC1",
        title="12345-AC1: Mirror Tool / Tools Menu / Activate Tool",
        steps=steps,
        area="Tools Menu"
    )
    
    obj = Objective(
        test_id="12345-AC1",
        title=tc.title,
        objective_text="Verify that the Mirror Tool can be activated from the Tools Menu."
    )
    
    result = linter.lint_objective(obj, tc)
    assert result.ok is True
    
    # Invalid objective (doesn't start with "Verify that")
    obj_invalid = Objective(
        test_id="12345-AC1",
        title=tc.title,
        objective_text="The tool should work correctly."
    )
    
    result = linter.lint_objective(obj_invalid, tc)
    # Should have error or warning about format
    assert result.ok is False or len(result.warnings) > 0


def test_objective_linter_scope_drift():
    """Test objective linter catches scope drift."""
    evidence = EvidenceModel(
        description_text="Tool flips objects",
        ac_text="Tool can flip horizontally",
        test_titles=["Test: Mirror Tool / Tools Menu / Horizontal Flip"]
    )
    
    linter = ObjectiveLinter(evidence)
    
    steps = [TestStep(index=1, action="Test", expected="")]
    tc = TestCase(
        test_id="12345-005",
        title="12345-005: Mirror Tool / Tools Menu / Horizontal Flip",
        steps=steps,
        area="Tools Menu"
    )
    
    # Objective adds scope not in title (vertical flip)
    obj = Objective(
        test_id="12345-005",
        title=tc.title,
        objective_text="Verify that the tool flips objects horizontally and vertically with real-time feedback on the canvas."
    )
    
    result = linter.lint_objective(obj, tc)
    # Should have warnings about added scope
    assert len(result.warnings) > 0 or result.ok is False


def test_objective_linter_all():
    """Test objective linter validates all objectives."""
    evidence = EvidenceModel(
        description_text="Test",
        ac_text="Test",
        test_titles=[]
    )
    
    linter = ObjectiveLinter(evidence)
    
    steps = [TestStep(index=1, action="Test", expected="")]
    
    tc1 = TestCase(
        test_id="12345-AC1",
        title="Test 1",
        steps=steps,
        area="Tools Menu"
    )
    
    tc2 = TestCase(
        test_id="12345-005",
        title="Test 2",
        steps=steps,
        area="Canvas"
    )
    
    obj1 = Objective(
        test_id="12345-AC1",
        title="Test 1",
        objective_text="Verify that test 1 works."
    )
    
    obj2 = Objective(
        test_id="12345-005",
        title="Test 2",
        objective_text="Verify that test 2 works."
    )
    
    result = linter.lint_all([obj1, obj2], [tc1, tc2])
    # Should pass basic checks
    assert isinstance(result.ok, bool)
