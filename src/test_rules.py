"""
Test Generation Rules Engine
Defines all rule-based templates and patterns for generic test case generation.
"""
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class StepTemplate:
    """Template for generating test steps."""
    name: str
    steps: List[Dict[str, str]]
    requires_object: bool = False


class TestRules:
    """Centralized rules for test generation."""

    # Forbidden words that must not appear in any test output
    FORBIDDEN_WORDS = ['or / OR', 'if available', 'if supported', 'ambiguous', 'functionality', 'general', 'validation']

    # Generic area terms that should not be used as scenarios
    FORBIDDEN_SCENARIO_TERMS = ['Functionality', 'Accessibility', 'Behavior', 'Validation', 'General', 'System']

    # Standardized step templates (based on approved 270479 patterns)
    STANDARD_PREREQ = "Pre-req: The ENV QuickDraw App is installed"
    STANDARD_LAUNCH = "Launch the ENV QuickDraw application."
    STANDARD_LAUNCH_EXPECTED = "Model space(Gray) and Canvas(white) space should be displayed"
    STANDARD_CLOSE = "Close the ENV QuickDraw App"

    # Allowed behavior-based area terms
    ALLOWED_BEHAVIOR_AREAS = [
        'Tool Availability',
        'Tool Activation',
        'Drawing Behavior',
        'Editing Behavior',
        'WCAG Compliance',
    ]

    # Cancelled/out-of-scope indicators
    CANCELLED_INDICATORS = [
        'cancelled', 'out of scope', 'to be cancelled', 'removed', 'not implemented',
        'deprecated', 'superseded', 'will not be implemented'
    ]

    # Step templates for common test patterns
    @staticmethod
    def get_object_setup_steps() -> List[Dict[str, str]]:
        """Return standard object setup steps (used when object interaction is needed)."""
        return [
            {"action": "Create a new drawing.", "expected": ""},
            {"action": "Draw a shape (e.g., arrow, circle, triangle, rectangle) on the Canvas.", "expected": ""},
            {"action": "Select the drawn object.", "expected": ""}
        ]

    @staticmethod
    def get_undo_redo_steps(action_description: str, post_state: str, pre_state: str) -> List[Dict[str, str]]:
        """
        Generate comprehensive Undo/Redo test steps.

        Args:
            action_description: The action being tested (e.g., "Move the object", "Rotate the object 45°")
            post_state: State after action (e.g., "Object is moved", "Object is rotated 45°")
            pre_state: State before action (e.g., "Object is at original position", "Object is at original rotation")
        """
        return [
            {"action": action_description, "expected": ""},
            {"action": f"Verify that {post_state.lower()}.", "expected": post_state},
            {"action": "Trigger Undo (Ctrl+Z or Cmd+Z).", "expected": ""},
            {"action": f"Verify that {pre_state.lower()}.", "expected": pre_state},
            {"action": "Trigger Redo (Ctrl+Y or Cmd+Shift+Z).", "expected": ""},
            {"action": f"Verify that {post_state.lower()}.", "expected": post_state}
        ]

    @staticmethod
    def get_add_remove_steps(add_action: str, added_state: str, remove_action: str) -> List[Dict[str, str]]:
        """
        Generate Add/Remove pattern steps.

        Args:
            add_action: Action to add/enable (e.g., "Enable measurement from Properties Panel")
            added_state: What appears after add (e.g., "Measurement line appears on the object")
            remove_action: Action to remove/disable (e.g., "Disable measurement from Properties Panel")
        """
        return [
            {"action": add_action, "expected": ""},
            {"action": f"Verify that {added_state.lower()}.", "expected": added_state},
            {"action": remove_action, "expected": ""},
            {"action": "Verify that the added element is removed and no stale artifacts remain.", "expected": "Element is removed completely"}
        ]

    @staticmethod
    def get_unit_setting_steps(setting_action: str, feature_action: str, expected_output: str,
                                setting_change: str, expected_after_change: str) -> List[Dict[str, str]]:
        """
        Generate unit/setting-driven behavior test steps.

        Args:
            setting_action: Action to set initial setting (e.g., "Set units to Imperial")
            feature_action: Feature action to perform (e.g., "Create a measurement")
            expected_output: Expected output with initial setting (e.g., "Measurement displays in inches")
            setting_change: Action to change setting (e.g., "Change units to Metric")
            expected_after_change: Expected after change (e.g., "Measurement updates to centimeters")
        """
        return [
            {"action": setting_action, "expected": ""},
            {"action": feature_action, "expected": ""},
            {"action": f"Verify that {expected_output.lower()}.", "expected": expected_output},
            {"action": setting_change, "expected": ""},
            {"action": f"Verify that {expected_after_change.lower()}.", "expected": expected_after_change}
        ]

    @staticmethod
    def should_skip_expected_result(action: str) -> bool:
        """
        Determine if an action step should have an empty expected result.
        Routine steps don't need expected results.
        """
        routine_keywords = [
            'launch', 'open', 'create a new drawing', 'draw a shape', 'select the',
            'enable', 'disable', 'activate', 'trigger', 'close', 'navigate to', 'click'
        ]
        action_lower = action.lower()
        return any(keyword in action_lower for keyword in routine_keywords) and 'verify' not in action_lower

    @staticmethod
    def is_cancelled(text: str) -> bool:
        """Check if text indicates the feature/AC is cancelled or out of scope."""
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in TestRules.CANCELLED_INDICATORS)

    @staticmethod
    def clean_forbidden_words(text: str) -> str:
        """Remove or replace forbidden words from text."""
        for word in TestRules.FORBIDDEN_WORDS:
            text = text.replace(word, '').replace(word.lower(), '')
        return text.strip()

    @staticmethod
    def get_accessibility_device_tool(device: str) -> tuple:
        """
        Get accessibility tool and interaction model for device.

        Returns:
            (tool_name, interaction_model, requires_keyboard)
        """
        if device == "Windows 11":
            return ("Accessibility Insights for Windows", "keyboard and mouse", True)
        elif device == "iPad":
            return ("VoiceOver", "touch", False)
        elif device == "Android Tablet":
            return ("Accessibility Scanner and TalkBack", "touch", False)
        else:
            return ("assistive technologies", "mixed", True)

    @staticmethod
    def extract_feature_name(story_title: str) -> str:
        """Extract the core feature name from story title."""
        title = story_title.strip()
        # Remove user story prefixes
        for prefix in ['As a', 'As an', 'I want', 'I need', 'User can', 'Users can']:
            if title.lower().startswith(prefix.lower()):
                parts = title.split(',')
                if len(parts) > 1:
                    title = parts[1].strip() if 'so that' not in parts[1].lower() else parts[0].replace(prefix, '').strip()
                else:
                    title = title.replace(prefix, '').strip()
                break
        return title

    @staticmethod
    def requires_object_interaction(ac_text: str) -> bool:
        """Determine if AC requires object selection/interaction."""
        object_keywords = [
            'rotate', 'move', 'delete', 'select', 'resize', 'modify', 'edit',
            'transform', 'flip', 'mirror', 'duplicate', 'copy', 'scale', 'reposition'
        ]
        ac_lower = ac_text.lower()
        return any(keyword in ac_lower for keyword in object_keywords)
