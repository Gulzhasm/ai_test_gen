"""
ActionChainBuilder: Reusable action sequences for comprehensive test steps.

This module provides deterministic action chains that can be composed
to create comprehensive test steps without needing LLM inference.
"""
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class ActionChain:
    """Represents a reusable action sequence."""
    name: str
    steps: List[Dict[str, str]]
    requires_object: bool = False


class ActionChainBuilder:
    """
    Builder for reusable action chains.

    Action chains are deterministic sequences that can be composed
    to create comprehensive test steps. For example, an Undo/Redo test
    should perform: create → move → rotate → undo → redo.
    """

    @staticmethod
    def chain_create_shape(shape_type: str = "shape") -> ActionChain:
        """Create a shape on canvas."""
        shape_desc = f"a {shape_type}" if shape_type != "shape" else "a shape (e.g., arrow, circle, triangle, rectangle)"
        return ActionChain(
            name="create_shape",
            steps=[
                {"action": f"Draw {shape_desc} on the Canvas.", "expected": ""}
            ],
            requires_object=False
        )

    @staticmethod
    def chain_select_object(object_desc: str = "the drawn object") -> ActionChain:
        """Select an object on canvas."""
        return ActionChain(
            name="select_object",
            steps=[
                {"action": f"Select {object_desc} on the Canvas.", "expected": ""}
            ],
            requires_object=False
        )

    @staticmethod
    def chain_move_object(distance: str = "to a new position") -> ActionChain:
        """Move an object."""
        return ActionChain(
            name="move_object",
            steps=[
                {"action": f"Move the selected object {distance} on the Canvas.", "expected": ""}
            ],
            requires_object=True
        )

    @staticmethod
    def chain_rotate_object(angle: str = "45°") -> ActionChain:
        """Rotate an object."""
        return ActionChain(
            name="rotate_object",
            steps=[
                {"action": f"Rotate the selected object by {angle}.", "expected": ""}
            ],
            requires_object=True
        )

    @staticmethod
    def chain_scale_object(scale_factor: str = "150%") -> ActionChain:
        """Scale an object."""
        return ActionChain(
            name="scale_object",
            steps=[
                {"action": f"Scale the selected object to {scale_factor}.", "expected": ""}
            ],
            requires_object=True
        )

    @staticmethod
    def chain_delete_object() -> ActionChain:
        """Delete an object."""
        return ActionChain(
            name="delete_object",
            steps=[
                {"action": "Delete the selected object.", "expected": ""}
            ],
            requires_object=True
        )

    @staticmethod
    def chain_flip_horizontal() -> ActionChain:
        """Flip an object horizontally."""
        return ActionChain(
            name="flip_horizontal",
            steps=[
                {"action": "Flip the selected object horizontally.", "expected": ""}
            ],
            requires_object=True
        )

    @staticmethod
    def chain_flip_vertical() -> ActionChain:
        """Flip an object vertically."""
        return ActionChain(
            name="flip_vertical",
            steps=[
                {"action": "Flip the selected object vertically.", "expected": ""}
            ],
            requires_object=True
        )

    @staticmethod
    def chain_undo() -> ActionChain:
        """Trigger undo."""
        return ActionChain(
            name="undo",
            steps=[
                {"action": "Trigger Undo (Ctrl+Z or Cmd+Z).", "expected": ""}
            ],
            requires_object=False
        )

    @staticmethod
    def chain_redo() -> ActionChain:
        """Trigger redo."""
        return ActionChain(
            name="redo",
            steps=[
                {"action": "Trigger Redo (Ctrl+Y or Cmd+Shift+Z).", "expected": ""}
            ],
            requires_object=False
        )

    @staticmethod
    def chain_verify_state(state_description: str, expected_result: str) -> ActionChain:
        """Verify a state."""
        return ActionChain(
            name="verify_state",
            steps=[
                {"action": f"Verify that {state_description}.", "expected": expected_result}
            ],
            requires_object=False
        )

    @staticmethod
    def chain_create_measurement(measurement_type: str, entry_point: str = "Dimensions menu") -> ActionChain:
        """Create a measurement (diameter, radius, etc.)."""
        steps = []

        # Determine how to access based on entry point
        if "Properties" in entry_point:
            steps = [
                {"action": f"Open the {entry_point}.", "expected": ""},
                {"action": f"Enable the {measurement_type} measurement toggle.", "expected": ""}
            ]
        else:
            steps = [
                {"action": f"Open the {entry_point}.", "expected": ""},
                {"action": f"Select {measurement_type}.", "expected": ""}
            ]

        return ActionChain(
            name="create_measurement",
            steps=steps,
            requires_object=False
        )

    @staticmethod
    def chain_toggle_visibility(control_name: str, action: str = "Disable") -> ActionChain:
        """Toggle visibility control."""
        return ActionChain(
            name="toggle_visibility",
            steps=[
                {"action": f"{action} the {control_name} visibility control.", "expected": ""}
            ],
            requires_object=False
        )

    @staticmethod
    def chain_open_menu(menu_name: str) -> ActionChain:
        """Open a menu."""
        return ActionChain(
            name="open_menu",
            steps=[
                {"action": f"Open the {menu_name}.", "expected": ""}
            ],
            requires_object=False
        )

    @staticmethod
    def chain_navigate_to(path: str) -> ActionChain:
        """Navigate to a menu path (e.g., View → Full Screen Mode)."""
        parts = path.split('→')
        if len(parts) == 2:
            menu = parts[0].strip()
            option = parts[1].strip()
            return ActionChain(
                name="navigate_to",
                steps=[
                    {"action": f"Open the {menu} menu.", "expected": ""},
                    {"action": f"Select {option}.", "expected": ""}
                ],
                requires_object=False
            )
        else:
            return ActionChain(
                name="navigate_to",
                steps=[
                    {"action": f"Navigate to {path}.", "expected": ""}
                ],
                requires_object=False
            )

    @staticmethod
    def chain_comprehensive_undo_redo(
        action_chains: List[ActionChain],
        pre_state: str,
        post_state: str
    ) -> ActionChain:
        """
        Build comprehensive undo/redo test with multiple actions.

        Args:
            action_chains: List of action chains to perform before undo/redo
            pre_state: Initial state description
            post_state: State after all actions
        """
        steps = []

        # Perform all actions
        for chain in action_chains:
            steps.extend(chain.steps)

        # Verify post-state
        steps.append({
            "action": f"Verify that {post_state.lower()}.",
            "expected": post_state
        })

        # Undo all actions (one undo per action)
        for i in range(len(action_chains)):
            steps.append({"action": "Trigger Undo (Ctrl+Z or Cmd+Z).", "expected": ""})

        # Verify pre-state restored
        steps.append({
            "action": f"Verify that {pre_state.lower()}.",
            "expected": pre_state
        })

        # Redo all actions (one redo per action)
        for i in range(len(action_chains)):
            steps.append({"action": "Trigger Redo (Ctrl+Y or Cmd+Shift+Z).", "expected": ""})

        # Verify post-state restored
        steps.append({
            "action": f"Verify that {post_state.lower()}.",
            "expected": post_state
        })

        return ActionChain(
            name="comprehensive_undo_redo",
            steps=steps,
            requires_object=any(chain.requires_object for chain in action_chains)
        )

    @staticmethod
    def chain_accessibility_keyboard_navigation(
        entry_point: str,
        control_name: str,
        device: str = "Windows 11"
    ) -> ActionChain:
        """Build accessibility keyboard navigation test."""
        steps = [
            {"action": f"Open the {entry_point} and navigate to {control_name} using keyboard (Tab/Arrow keys).", "expected": ""},
            {"action": f"Verify the {control_name} control is reachable by keyboard and focus is clearly visible.",
             "expected": f"Keyboard focus moves to the {control_name} control with a visible focus indicator."}
        ]

        return ActionChain(
            name="accessibility_keyboard_navigation",
            steps=steps,
            requires_object=False
        )

    @staticmethod
    def chain_accessibility_screen_reader(
        entry_point: str,
        control_name: str,
        device: str = "iPad"
    ) -> ActionChain:
        """Build accessibility screen reader test."""
        if device == "iPad":
            tool = "VoiceOver"
            navigation = "VoiceOver swipe navigation"
        elif device == "Android Tablet":
            tool = "TalkBack"
            navigation = "TalkBack swipe navigation"
        else:
            tool = "screen reader"
            navigation = "screen reader navigation"

        steps = [
            {"action": f"Enable {tool}.", "expected": ""},
            {"action": f"Open the {entry_point} and move through items using {navigation}.", "expected": ""},
            {"action": f"Verify the {control_name} control is announced with a meaningful label and correct role.",
             "expected": f"{tool} announces the {control_name} control with a meaningful label and role."}
        ]

        return ActionChain(
            name="accessibility_screen_reader",
            steps=steps,
            requires_object=False
        )

    @staticmethod
    def chain_negative_no_selection(feature_name: str, entry_point: str) -> ActionChain:
        """Build negative test for no selection."""
        steps = [
            {"action": f"Open the {entry_point}.", "expected": ""},
            {"action": f"Select {feature_name}.", "expected": ""},
            {"action": f"Verify no {feature_name.lower()} is created on the Canvas and the app provides clear feedback.",
             "expected": f"No {feature_name.lower()} is created when no object is selected, and appropriate feedback is provided."}
        ]

        return ActionChain(
            name="negative_no_selection",
            steps=steps,
            requires_object=False
        )

    @staticmethod
    def chain_negative_wrong_object_type(
        feature_name: str,
        entry_point: str,
        wrong_object_type: str = "rectangle",
        required_object_type: str = "ellipse"
    ) -> ActionChain:
        """Build negative test for wrong object type."""
        steps = [
            {"action": f"Draw a {wrong_object_type} on the Canvas.", "expected": ""},
            {"action": f"Select the drawn {wrong_object_type} on the Canvas.", "expected": ""},
            {"action": f"Open the {entry_point}.", "expected": ""},
            {"action": f"Select {feature_name}.", "expected": ""},
            {"action": f"Verify no {feature_name.lower()} is created for the non-{required_object_type} selection and the app provides clear feedback.",
             "expected": f"No {feature_name.lower()} is created for a non-{required_object_type} object, and appropriate feedback is provided."}
        ]

        return ActionChain(
            name="negative_wrong_object_type",
            steps=steps,
            requires_object=False
        )

    @staticmethod
    def chain_unit_system_test(
        feature_name: str,
        entry_point: str,
        object_type: str = "ellipse"
    ) -> ActionChain:
        """Build unit system test (Imperial/Metric)."""
        steps = [
            {"action": "Set Unit of Measure to Imperial in application settings.", "expected": ""},
            {"action": f"Draw an {object_type} on the Canvas.", "expected": ""},
            {"action": f"Select the drawn {object_type} on the Canvas.", "expected": ""},
            {"action": f"Open the {entry_point}.", "expected": ""},
            {"action": f"Select {feature_name}.", "expected": ""},
            {"action": f"Verify the {feature_name.lower()} label displays the measurement using Imperial units.",
             "expected": f"{feature_name} label uses Imperial units."},
            {"action": "Set Unit of Measure to Metric in application settings.", "expected": ""},
            {"action": f"Verify the {feature_name.lower()} label updates to display the measurement using Metric units.",
             "expected": f"{feature_name} label uses Metric units."}
        ]

        return ActionChain(
            name="unit_system_test",
            steps=steps,
            requires_object=False
        )

    @staticmethod
    def chain_duplicate_prevention(
        feature_name: str,
        entry_point: str,
        object_type: str = "ellipse"
    ) -> ActionChain:
        """Build duplicate prevention test."""
        steps = [
            {"action": f"Draw an {object_type} on the Canvas.", "expected": ""},
            {"action": f"Select the drawn {object_type} on the Canvas.", "expected": ""},
            {"action": f"Open the {entry_point}.", "expected": ""},
            {"action": f"Select {feature_name}.", "expected": ""},
            {"action": f"Verify one {feature_name.lower()} line and one {feature_name.lower()} label are displayed.",
             "expected": f"A single {feature_name.lower()} line and label are displayed."},
            {"action": f"Open the {entry_point}.", "expected": ""},
            {"action": f"Select {feature_name}.", "expected": ""},
            {"action": f"Verify the {object_type} still shows a single {feature_name.lower()} line and label with no duplicates.",
             "expected": f"No duplicate {feature_name.lower()} lines and labels are created."}
        ]

        return ActionChain(
            name="duplicate_prevention",
            steps=steps,
            requires_object=False
        )

    @staticmethod
    def compose_chains(chains: List[ActionChain]) -> List[Dict[str, str]]:
        """Compose multiple action chains into a single step list."""
        steps = []
        for chain in chains:
            steps.extend(chain.steps)
        return steps

    @staticmethod
    def chain_enter_fullscreen_mode(entry_point: str = "View Menu", feature_name: str = "Full Screen Mode") -> ActionChain:
        """Enter fullscreen mode with comprehensive verification."""
        menu_name = entry_point.replace(" Menu", "")

        return ActionChain(
            name="enter_fullscreen",
            steps=[
                {"action": f"Open the {menu_name} menu.", "expected": ""},
                {"action": f"Select {feature_name}.", "expected": ""},
                {"action": "Verify the application enters fullscreen mode.", "expected": "Application is in fullscreen mode."},
                {"action": "Verify OS-level UI is hidden (taskbar, window borders, title bar).", "expected": "OS-level UI is hidden."},
                {"action": "Verify QuickDraw UI remains fully visible (menus, toolbars, panels).", "expected": "QuickDraw UI is fully visible."}
            ],
            requires_object=False
        )

    @staticmethod
    def chain_exit_fullscreen_mode(feature_name: str = "fullscreen mode") -> ActionChain:
        """Exit fullscreen mode and verify restoration."""
        return ActionChain(
            name="exit_fullscreen",
            steps=[
                {"action": "Press ESC key.", "expected": ""},
                {"action": f"Verify the application exits {feature_name}.", "expected": f"Application exits {feature_name}."},
                {"action": "Verify normal windowed mode is restored.", "expected": "Normal windowed mode is restored."}
            ],
            requires_object=False
        )

    @staticmethod
    def chain_verify_fullscreen_resize() -> ActionChain:
        """Verify fullscreen resize behavior."""
        return ActionChain(
            name="verify_fullscreen_resize",
            steps=[
                {"action": "Verify canvas fills the fullscreen container completely.", "expected": "Canvas fills fullscreen container."},
                {"action": "Verify interface resizes correctly without distortion or clipping.", "expected": "Interface resizes correctly without distortion."},
                {"action": "Verify no UI overlap or layout issues occur.", "expected": "No UI overlap or layout issues."}
            ],
            requires_object=False
        )

    @staticmethod
    def chain_verify_ui_visibility(os_ui_expected: str = "hidden", app_ui_expected: str = "visible") -> ActionChain:
        """Verify UI visibility in fullscreen."""
        return ActionChain(
            name="verify_ui_visibility",
            steps=[
                {"action": f"Verify OS-level UI is {os_ui_expected}.", "expected": f"OS-level UI is {os_ui_expected}."},
                {"action": f"Verify QuickDraw UI is {app_ui_expected}.", "expected": f"QuickDraw UI is {app_ui_expected}."}
            ],
            requires_object=False
        )

    @staticmethod
    def get_comprehensive_undo_redo_actions(story_type: str) -> List[ActionChain]:
        """
        Get appropriate action chains for undo/redo based on story type.

        Args:
            story_type: Type of story (Tool, Dialog, Mode, Measurement, etc.)

        Returns:
            List of action chains appropriate for the story type
        """
        # Tool story: move + rotate + scale
        if story_type == "Tool":
            return [
                ActionChainBuilder.chain_move_object("10px right"),
                ActionChainBuilder.chain_rotate_object("45°"),
                ActionChainBuilder.chain_scale_object("150%")
            ]

        # Measurement story: create + visibility toggle
        elif story_type == "Measurement":
            return [
                ActionChainBuilder.chain_create_measurement("Diameter", "Dimensions menu"),
                ActionChainBuilder.chain_toggle_visibility("Show Diameter", "Disable")
            ]

        # Dialog story: create + close
        elif story_type == "Dialog":
            return []  # Dialog-specific actions would be defined here

        # Default: move + rotate
        else:
            return [
                ActionChainBuilder.chain_move_object("10px right"),
                ActionChainBuilder.chain_rotate_object("45°")
            ]
