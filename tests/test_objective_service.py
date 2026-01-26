"""Tests for ObjectiveService."""
import pytest
from core.domain.models import TestCase, TestStep, Objective, EvidenceModel
from core.services import ObjectiveService


class TestObjectiveService:
    """Tests for ObjectiveService."""

    @pytest.fixture
    def sample_test_cases(self):
        """Create sample test cases."""
        return [
            TestCase(
                test_id="12345-AC1",
                title="12345-AC1: Mirror Tool / Tools Menu / Horizontal Flip",
                steps=[
                    TestStep(index=1, action="Open Tools Menu", expected="Menu opens"),
                    TestStep(index=2, action="Select Mirror Tool", expected="Tool activates"),
                ],
                area="Tools Menu",
                objective="Verify that the user can flip objects horizontally."
            ),
            TestCase(
                test_id="12345-AC5",
                title="12345-AC5: Mirror Tool / Canvas / Vertical Flip",
                steps=[
                    TestStep(index=1, action="Select object", expected="Object selected"),
                ],
                area="Canvas"
            ),
        ]

    @pytest.fixture
    def sample_evidence(self):
        """Create sample evidence model."""
        return EvidenceModel(
            description_text="Mirror Tool enables flipping objects",
            ac_text="User can flip objects horizontally and vertically",
            test_titles=["Mirror Tool / Tools Menu / Horizontal Flip"]
        )

    def test_service_initialization(self):
        """Test ObjectiveService initialization."""
        service = ObjectiveService()
        assert service.llm_provider is None
        assert service.debug is False

    def test_service_with_debug(self):
        """Test ObjectiveService with debug enabled."""
        service = ObjectiveService(debug=True)
        assert service.debug is True

    def test_generate_objectives_uses_existing(self, sample_test_cases, sample_evidence):
        """Test that existing objectives are used when present."""
        service = ObjectiveService()
        objectives, lint_result = service.generate_objectives(sample_test_cases, sample_evidence)

        assert len(objectives) == 2
        # First test case has explicit objective
        assert objectives[0].objective_text == "Verify that the user can flip objects horizontally."

    def test_generate_objectives_creates_default(self, sample_test_cases, sample_evidence):
        """Test that default objectives are generated when not present."""
        service = ObjectiveService()
        objectives, lint_result = service.generate_objectives(sample_test_cases, sample_evidence)

        # Second test case has no explicit objective
        assert objectives[1].objective_text.startswith("Verify that")

    def test_objective_ids_match(self, sample_test_cases, sample_evidence):
        """Test that objective IDs match test case IDs."""
        service = ObjectiveService()
        objectives, lint_result = service.generate_objectives(sample_test_cases, sample_evidence)

        for obj, tc in zip(objectives, sample_test_cases):
            assert obj.test_id == tc.test_id

    def test_objective_titles_match(self, sample_test_cases, sample_evidence):
        """Test that objective titles match test case titles."""
        service = ObjectiveService()
        objectives, lint_result = service.generate_objectives(sample_test_cases, sample_evidence)

        for obj, tc in zip(objectives, sample_test_cases):
            assert obj.title == tc.title

    def test_lint_result_returned(self, sample_test_cases, sample_evidence):
        """Test that lint result is returned."""
        service = ObjectiveService()
        objectives, lint_result = service.generate_objectives(sample_test_cases, sample_evidence)

        assert lint_result is not None
        assert hasattr(lint_result, 'ok')
        assert hasattr(lint_result, 'errors')

    def test_default_objective_from_title(self):
        """Test default objective generation from title."""
        service = ObjectiveService()

        tc = TestCase(
            test_id="12345-AC10",
            title="12345-AC10: Feature / Area / User can save settings",
            steps=[TestStep(index=1, action="Test", expected="Result")],
            area="Settings"
        )

        objective = service._generate_default_objective(tc)
        assert "Verify that" in objective
        assert "save settings" in objective.lower()

    def test_default_objective_simple_title(self):
        """Test default objective for simple titles without slashes."""
        service = ObjectiveService()

        tc = TestCase(
            test_id="12345-AC10",
            title="Simple Test",
            steps=[TestStep(index=1, action="Test", expected="Result")],
            area="General"
        )

        objective = service._generate_default_objective(tc)
        assert "Verify that" in objective


class TestObjectiveServiceEdgeCases:
    """Edge case tests for ObjectiveService."""

    def test_empty_test_cases(self):
        """Test with empty test case list."""
        service = ObjectiveService()
        evidence = EvidenceModel(
            description_text="Test",
            ac_text="Test",
            test_titles=[]
        )

        objectives, lint_result = service.generate_objectives([], evidence)
        assert len(objectives) == 0

    def test_test_case_without_steps(self):
        """Test with test case that has no steps."""
        service = ObjectiveService()
        evidence = EvidenceModel(
            description_text="Test",
            ac_text="Test",
            test_titles=[]
        )

        tc = TestCase(
            test_id="12345-AC1",
            title="Test Case",
            steps=[],
            area="Area"
        )

        objectives, lint_result = service.generate_objectives([tc], evidence)
        assert len(objectives) == 1
