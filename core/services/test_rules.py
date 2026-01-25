"""
Test Generation Rules Engine

Provides rule-based templates and patterns for generic test case generation.
Designed to work with injected configuration for project-agnostic behavior.
"""
from typing import List, Dict, Optional, Protocol
from dataclasses import dataclass


@dataclass
class StepTemplate:
    """Template for generating test steps."""
    name: str
    steps: List[Dict[str, str]]
    requires_object: bool = False


class IRulesConfig(Protocol):
    """Protocol for rules configuration."""
    @property
    def forbidden_words(self) -> List[str]: ...
    @property
    def forbidden_area_terms(self) -> List[str]: ...
    @property
    def allowed_areas(self) -> List[str]: ...
    @property
    def cancelled_indicators(self) -> List[str]: ...


class IApplicationConfig(Protocol):
    """Protocol for application configuration."""
    @property
    def prereq_template(self) -> str: ...
    @property
    def launch_step(self) -> str: ...
    @property
    def launch_expected(self) -> str: ...
    @property
    def close_step(self) -> str: ...
    def requires_object_interaction(self, text: str) -> bool: ...


class TestRules:
    """Centralized rules for test generation with configurable templates."""

    # Default forbidden words (can be overridden via config)
    DEFAULT_FORBIDDEN_WORDS = [
        'or / OR', 'if available', 'if supported',
        'ambiguous', 'functionality', 'general', 'validation'
    ]

    # Default forbidden scenario terms
    DEFAULT_FORBIDDEN_SCENARIO_TERMS = [
        'Functionality', 'Accessibility', 'Behavior',
        'Validation', 'General', 'System'
    ]

    # Default cancelled indicators
    DEFAULT_CANCELLED_INDICATORS = [
        'cancelled', 'out of scope', 'to be cancelled', 'removed',
        'not implemented', 'deprecated', 'superseded', 'will not be implemented'
    ]

    # Default allowed behavior areas
    DEFAULT_ALLOWED_BEHAVIOR_AREAS = [
        'Tool Availability',
        'Tool Activation',
        'Drawing Behavior',
        'Editing Behavior',
        'WCAG Compliance',
    ]

    def __init__(
        self,
        rules_config: Optional[IRulesConfig] = None,
        app_config: Optional[IApplicationConfig] = None
    ):
        """
        Initialize rules engine with optional configuration.

        Args:
            rules_config: Rules configuration (forbidden words, etc.)
            app_config: Application-specific configuration (templates)
        """
        self._rules_config = rules_config
        self._app_config = app_config

    @property
    def forbidden_words(self) -> List[str]:
        """Get forbidden words list."""
        if self._rules_config:
            return self._rules_config.forbidden_words
        return self.DEFAULT_FORBIDDEN_WORDS

    @property
    def forbidden_scenario_terms(self) -> List[str]:
        """Get forbidden scenario terms."""
        if self._rules_config:
            return self._rules_config.forbidden_area_terms
        return self.DEFAULT_FORBIDDEN_SCENARIO_TERMS

    @property
    def cancelled_indicators(self) -> List[str]:
        """Get cancelled indicators."""
        if self._rules_config:
            return self._rules_config.cancelled_indicators
        return self.DEFAULT_CANCELLED_INDICATORS

    @property
    def allowed_behavior_areas(self) -> List[str]:
        """Get allowed behavior areas."""
        if self._rules_config:
            return self._rules_config.allowed_areas
        return self.DEFAULT_ALLOWED_BEHAVIOR_AREAS

    @property
    def prereq_template(self) -> str:
        """Get prerequisite step template."""
        if self._app_config:
            return self._app_config.prereq_template
        return "Pre-req: Application is installed"

    @property
    def launch_template(self) -> str:
        """Get launch step template."""
        if self._app_config:
            return self._app_config.launch_step
        return "Launch the application."

    @property
    def launch_expected(self) -> str:
        """Get expected result for launch step."""
        if self._app_config:
            return self._app_config.launch_expected
        return "Application opens successfully"

    @property
    def close_template(self) -> str:
        """Get close step template."""
        if self._app_config:
            return self._app_config.close_step
        return "Close the application"

    def get_prereq_step(self) -> Dict[str, str]:
        """Get prerequisite step dict."""
        return {"action": self.prereq_template, "expected": ""}

    def get_launch_step(self) -> Dict[str, str]:
        """Get launch step dict."""
        return {"action": self.launch_template, "expected": self.launch_expected}

    def get_close_step(self) -> Dict[str, str]:
        """Get close step dict."""
        return {"action": self.close_template, "expected": ""}

    def get_object_setup_steps(self) -> List[Dict[str, str]]:
        """Return standard object setup steps."""
        return [
            {"action": "Create a new drawing.", "expected": ""},
            {"action": "Draw a shape (e.g., arrow, circle, triangle, rectangle) on the Canvas.", "expected": ""},
            {"action": "Select the drawn object.", "expected": ""}
        ]

    def get_undo_redo_steps(
        self,
        action_description: str,
        post_state: str,
        pre_state: str
    ) -> List[Dict[str, str]]:
        """
        Generate comprehensive Undo/Redo test steps.

        Args:
            action_description: The action being tested
            post_state: State after action
            pre_state: State before action

        Returns:
            List of step dictionaries
        """
        return [
            {"action": action_description, "expected": ""},
            {"action": f"Verify that {post_state.lower()}.", "expected": post_state},
            {"action": "Trigger Undo (Ctrl+Z or Cmd+Z).", "expected": ""},
            {"action": f"Verify that {pre_state.lower()}.", "expected": pre_state},
            {"action": "Trigger Redo (Ctrl+Y or Cmd+Shift+Z).", "expected": ""},
            {"action": f"Verify that {post_state.lower()}.", "expected": post_state}
        ]

    def get_add_remove_steps(
        self,
        add_action: str,
        added_state: str,
        remove_action: str
    ) -> List[Dict[str, str]]:
        """
        Generate Add/Remove pattern steps.

        Args:
            add_action: Action to add/enable
            added_state: What appears after add
            remove_action: Action to remove/disable

        Returns:
            List of step dictionaries
        """
        return [
            {"action": add_action, "expected": ""},
            {"action": f"Verify that {added_state.lower()}.", "expected": added_state},
            {"action": remove_action, "expected": ""},
            {"action": "Verify that the added element is removed and no stale artifacts remain.",
             "expected": "Element is removed completely"}
        ]

    def get_unit_setting_steps(
        self,
        setting_action: str,
        feature_action: str,
        expected_output: str,
        setting_change: str,
        expected_after_change: str
    ) -> List[Dict[str, str]]:
        """
        Generate unit/setting-driven behavior test steps.

        Args:
            setting_action: Action to set initial setting
            feature_action: Feature action to perform
            expected_output: Expected output with initial setting
            setting_change: Action to change setting
            expected_after_change: Expected after change

        Returns:
            List of step dictionaries
        """
        return [
            {"action": setting_action, "expected": ""},
            {"action": feature_action, "expected": ""},
            {"action": f"Verify that {expected_output.lower()}.", "expected": expected_output},
            {"action": setting_change, "expected": ""},
            {"action": f"Verify that {expected_after_change.lower()}.", "expected": expected_after_change}
        ]

    def should_skip_expected_result(self, action: str) -> bool:
        """
        Determine if an action step should have an empty expected result.

        Args:
            action: The action text

        Returns:
            True if this is a routine step that doesn't need expected result
        """
        routine_keywords = [
            'launch', 'open', 'create a new drawing', 'draw a shape', 'select the',
            'enable', 'disable', 'activate', 'trigger', 'close', 'navigate to', 'click'
        ]
        action_lower = action.lower()
        return any(kw in action_lower for kw in routine_keywords) and 'verify' not in action_lower

    def is_cancelled(self, text: str) -> bool:
        """Check if text indicates the feature/AC is cancelled or out of scope."""
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in self.cancelled_indicators)

    def clean_forbidden_words(self, text: str) -> str:
        """Remove or replace forbidden words from text."""
        for word in self.forbidden_words:
            text = text.replace(word, '').replace(word.lower(), '')
        return text.strip()

    def get_accessibility_device_tool(self, device: str) -> tuple:
        """
        Get accessibility tool and interaction model for device.

        Args:
            device: Target device name

        Returns:
            Tuple of (tool_name, interaction_model, requires_keyboard)
        """
        device_tools = {
            "Windows 11": ("Accessibility Insights for Windows", "keyboard and mouse", True),
            "iPad": ("VoiceOver", "touch", False),
            "Android Tablet": ("Accessibility Scanner and TalkBack", "touch", False),
        }
        return device_tools.get(device, ("assistive technologies", "mixed", True))

    def extract_feature_name(self, story_title: str) -> str:
        """Extract the core feature name from story title."""
        title = story_title.strip()
        prefixes = ['As a', 'As an', 'I want', 'I need', 'User can', 'Users can']

        for prefix in prefixes:
            if title.lower().startswith(prefix.lower()):
                parts = title.split(',')
                if len(parts) > 1:
                    candidate = parts[1].strip()
                    title = candidate if 'so that' not in candidate.lower() else parts[0].replace(prefix, '').strip()
                else:
                    title = title.replace(prefix, '').strip()
                break
        return title

    def requires_object_interaction(self, ac_text: str) -> bool:
        """Determine if AC requires object selection/interaction."""
        if self._app_config:
            return self._app_config.requires_object_interaction(ac_text)

        object_keywords = [
            'rotate', 'move', 'delete', 'select', 'resize', 'modify', 'edit',
            'transform', 'flip', 'mirror', 'duplicate', 'copy', 'scale', 'reposition'
        ]
        return any(kw in ac_text.lower() for kw in object_keywords)
