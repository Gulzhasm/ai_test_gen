"""
Unit tests for TestRules module.

Tests rule-based templates and patterns for test case generation.
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.services import TestRules, StepTemplate


class TestTestRulesDefaults:
    """Test TestRules with default configuration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.rules = TestRules()

    def test_forbidden_words_default(self):
        """Test default forbidden words list."""
        forbidden = self.rules.forbidden_words
        assert 'or / OR' in forbidden
        assert 'if available' in forbidden
        assert 'if supported' in forbidden

    def test_forbidden_scenario_terms_default(self):
        """Test default forbidden scenario terms."""
        terms = self.rules.forbidden_scenario_terms
        assert 'Functionality' in terms
        assert 'General' in terms

    def test_cancelled_indicators_default(self):
        """Test default cancelled indicators."""
        indicators = self.rules.cancelled_indicators
        assert 'cancelled' in indicators
        assert 'out of scope' in indicators

    def test_is_cancelled_true(self):
        """Test is_cancelled returns True for cancelled text."""
        assert self.rules.is_cancelled("This feature is cancelled")
        assert self.rules.is_cancelled("Out of scope for this sprint")
        assert self.rules.is_cancelled("Feature will not be implemented")

    def test_is_cancelled_false(self):
        """Test is_cancelled returns False for valid text."""
        assert not self.rules.is_cancelled("User can rotate objects")
        assert not self.rules.is_cancelled("The button should be visible")

    def test_clean_forbidden_words(self):
        """Test removal of forbidden words from text."""
        text = "Check if available functionality works"
        cleaned = self.rules.clean_forbidden_words(text)
        assert 'if available' not in cleaned
        assert 'functionality' not in cleaned.lower()

    def test_extract_feature_name_simple(self):
        """Test feature name extraction from simple title."""
        title = "Draw Order Tools"
        assert self.rules.extract_feature_name(title) == "Draw Order Tools"

    def test_extract_feature_name_with_prefix(self):
        """Test feature name extraction with user story prefix."""
        title = "As a user, I want to rotate objects so that I can adjust position"
        result = self.rules.extract_feature_name(title)
        assert 'As a' not in result
        # The function extracts text after the prefix
        assert len(result) > 0

    def test_requires_object_interaction_true(self):
        """Test detection of object interaction keywords."""
        assert self.rules.requires_object_interaction("rotate the selected object")
        assert self.rules.requires_object_interaction("move the shape")
        assert self.rules.requires_object_interaction("flip horizontally")

    def test_requires_object_interaction_false(self):
        """Test non-object interaction text."""
        assert not self.rules.requires_object_interaction("open the menu")
        assert not self.rules.requires_object_interaction("click the button")


class TestTestRulesTemplates:
    """Test TestRules step templates."""

    def setup_method(self):
        """Set up test fixtures."""
        self.rules = TestRules()

    def test_prereq_step(self):
        """Test prerequisite step generation."""
        step = self.rules.get_prereq_step()
        assert 'action' in step
        assert 'expected' in step
        assert step['expected'] == ""  # Prereq should have blank expected

    def test_launch_step(self):
        """Test launch step generation."""
        step = self.rules.get_launch_step()
        assert 'action' in step
        assert 'expected' in step

    def test_close_step(self):
        """Test close step generation."""
        step = self.rules.get_close_step()
        assert 'action' in step
        assert step['expected'] == ""  # Close should have blank expected

    def test_object_setup_steps(self):
        """Test object setup steps generation."""
        steps = self.rules.get_object_setup_steps()
        assert isinstance(steps, list)
        assert len(steps) >= 2
        # Should include drawing and selecting
        actions = [s['action'].lower() for s in steps]
        assert any('draw' in a for a in actions)
        assert any('select' in a for a in actions)

    def test_undo_redo_steps(self):
        """Test undo/redo steps generation."""
        steps = self.rules.get_undo_redo_steps(
            action_description="Rotate the object 90 degrees",
            post_state="Object is rotated 90 degrees",
            pre_state="Object is at original rotation"
        )
        assert isinstance(steps, list)
        assert len(steps) >= 4
        actions = ' '.join([s['action'].lower() for s in steps])
        assert 'undo' in actions
        assert 'redo' in actions

    def test_add_remove_steps(self):
        """Test add/remove pattern steps."""
        steps = self.rules.get_add_remove_steps(
            add_action="Enable measurement",
            added_state="Measurement is visible",
            remove_action="Disable measurement"
        )
        assert isinstance(steps, list)
        assert len(steps) >= 3

    def test_should_skip_expected_result_true(self):
        """Test routine steps should skip expected result."""
        assert self.rules.should_skip_expected_result("Launch the application")
        assert self.rules.should_skip_expected_result("Close the application")
        assert self.rules.should_skip_expected_result("Navigate to File Menu")

    def test_should_skip_expected_result_false(self):
        """Test verification steps should have expected result."""
        assert not self.rules.should_skip_expected_result("Verify the button is visible")
        assert not self.rules.should_skip_expected_result("Confirm the action completed")


class TestTestRulesAccessibility:
    """Test TestRules accessibility features."""

    def setup_method(self):
        """Set up test fixtures."""
        self.rules = TestRules()

    def test_windows_accessibility_tool(self):
        """Test Windows accessibility tool detection."""
        tool, interaction, keyboard = self.rules.get_accessibility_device_tool("Windows 11")
        assert "Accessibility Insights" in tool
        assert keyboard is True

    def test_ipad_accessibility_tool(self):
        """Test iPad accessibility tool detection."""
        tool, interaction, keyboard = self.rules.get_accessibility_device_tool("iPad")
        assert "VoiceOver" in tool
        assert interaction == "touch"
        assert keyboard is False

    def test_android_accessibility_tool(self):
        """Test Android accessibility tool detection."""
        tool, interaction, keyboard = self.rules.get_accessibility_device_tool("Android Tablet")
        assert "TalkBack" in tool or "Accessibility Scanner" in tool
        assert keyboard is False

    def test_unknown_device_accessibility_tool(self):
        """Test fallback for unknown device."""
        tool, interaction, keyboard = self.rules.get_accessibility_device_tool("Unknown Device")
        assert "assistive" in tool.lower()


class TestTestRulesWithConfig:
    """Test TestRules with custom configuration."""

    def test_custom_forbidden_words(self):
        """Test custom forbidden words via config."""
        class MockRulesConfig:
            forbidden_words = ['custom_word', 'another_word']
            forbidden_area_terms = ['CustomTerm']
            allowed_areas = ['Custom Area']
            cancelled_indicators = ['custom_cancel']

        rules = TestRules(rules_config=MockRulesConfig())
        assert 'custom_word' in rules.forbidden_words
        assert 'another_word' in rules.forbidden_words

    def test_custom_app_templates(self):
        """Test custom application templates via config."""
        class MockAppConfig:
            prereq_template = "Custom prereq"
            launch_step = "Custom launch"
            launch_expected = "Custom expected"
            close_step = "Custom close"

            def requires_object_interaction(self, text):
                return 'custom' in text.lower()

        rules = TestRules(app_config=MockAppConfig())
        assert rules.prereq_template == "Custom prereq"
        assert rules.launch_template == "Custom launch"
        assert rules.requires_object_interaction("custom action")


class TestStepTemplate:
    """Test StepTemplate dataclass."""

    def test_step_template_creation(self):
        """Test StepTemplate instantiation."""
        template = StepTemplate(
            name="Test Template",
            steps=[{"action": "Do something", "expected": "Something happens"}],
            requires_object=True
        )
        assert template.name == "Test Template"
        assert len(template.steps) == 1
        assert template.requires_object is True

    def test_step_template_defaults(self):
        """Test StepTemplate default values."""
        template = StepTemplate(
            name="Test",
            steps=[]
        )
        assert template.requires_object is False
