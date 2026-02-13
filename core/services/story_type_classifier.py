"""
StoryTypeClassifier: Rule-based story classification.

This module classifies stories into types to gate scenario templates
and prevent cross-story leakage (e.g., tool-state text in fullscreen mode).
"""
from typing import List, Set
from enum import Enum


class StoryType(Enum):
    """Story types for classification."""
    MODE_LAYOUT = "Mode/Layout"
    DIALOG = "Dialog"
    TOOL = "Tool"
    MEASUREMENT = "Measurement"
    FILE_OPS = "File Operations"
    MENU = "Menu"
    PROPERTIES = "Properties"
    HELP_DOCUMENTATION = "Help/Documentation"  # Help menus, manuals, about dialogs
    UNKNOWN = "Unknown"


class StoryTypeClassifier:
    """
    Rule-based story type classifier.

    Classifies stories to gate scenario templates and prevent
    irrelevant test patterns (e.g., tool state patterns in fullscreen mode).
    """

    # Keywords for each story type
    MODE_LAYOUT_KEYWORDS = {
        'fullscreen', 'full screen', 'mode', 'workspace', 'presentation',
        'layout', 'window', 'display', 'view', 'screen'
    }

    DIALOG_KEYWORDS = {
        'dialog', 'modal', 'window', 'create', 'close', 'open',
        'popup', 'form', 'wizard'
    }

    TOOL_KEYWORDS = {
        'tool', 'select tool', 'marker', 'handle', 'rotate', 'mirror',
        'move', 'transform', 'flip', 'scale', 'resize', 'active',
        'remains active', 'tool remains', 'selection tool'
    }

    MEASUREMENT_KEYWORDS = {
        'dimension', 'diameter', 'radius', 'measurement', 'gps',
        'label', 'value', 'unit', 'metric', 'imperial', 'measure'
    }

    FILE_OPS_KEYWORDS = {
        'open', 'save', 'close', 'recent files', 'export', 'import',
        'load', 'file', 'document'
    }

    MENU_KEYWORDS = {
        'menu', 'menu item', 'option', 'command', 'subcategories',
        'view →', 'view menu', 'edit →', 'file →', 'tools →'
    }

    PROPERTIES_KEYWORDS = {
        'properties', 'property', 'panel', 'settings', 'configure',
        'preferences', 'options panel'
    }

    HELP_DOCUMENTATION_KEYWORDS = {
        'help', 'manual', 'user manual', 'documentation', 'guide',
        'about', 'release notes', 'license', 'credits', 'version',
        'readme', 'faq', 'support', 'viewer', 'pdf', 'offline'
    }

    @classmethod
    def classify(cls, story_title: str, ac_bullets: List[str], qa_prep: str = "", description: str = "") -> StoryType:
        """
        Classify story based on title, description, AC, and QA Prep.

        Args:
            story_title: Story title
            ac_bullets: List of acceptance criteria
            qa_prep: QA prep content
            description: Story description text

        Returns:
            StoryType enum
        """
        # Combine all text for analysis (description included for context)
        all_text = story_title.lower()
        if description:
            all_text += " " + description.lower()
        for ac in ac_bullets:
            all_text += " " + ac.lower()
        if qa_prep:
            all_text += " " + qa_prep.lower()

        # Count keyword matches for each story type
        # Note: HELP_DOCUMENTATION is checked FIRST because it's more specific
        # than generic MENU or FILE_OPS types
        scores = {
            StoryType.HELP_DOCUMENTATION: cls._count_keywords(all_text, cls.HELP_DOCUMENTATION_KEYWORDS),
            StoryType.MODE_LAYOUT: cls._count_keywords(all_text, cls.MODE_LAYOUT_KEYWORDS),
            StoryType.DIALOG: cls._count_keywords(all_text, cls.DIALOG_KEYWORDS),
            StoryType.TOOL: cls._count_keywords(all_text, cls.TOOL_KEYWORDS),
            StoryType.MEASUREMENT: cls._count_keywords(all_text, cls.MEASUREMENT_KEYWORDS),
            StoryType.FILE_OPS: cls._count_keywords(all_text, cls.FILE_OPS_KEYWORDS),
            StoryType.MENU: cls._count_keywords(all_text, cls.MENU_KEYWORDS),
            StoryType.PROPERTIES: cls._count_keywords(all_text, cls.PROPERTIES_KEYWORDS),
        }

        # Get story type with highest score
        max_score = max(scores.values())
        if max_score == 0:
            return StoryType.UNKNOWN

        # Return story type with highest score
        for story_type, score in scores.items():
            if score == max_score:
                return story_type

        return StoryType.UNKNOWN

    @staticmethod
    def _count_keywords(text: str, keywords: Set[str]) -> int:
        """Count how many keywords appear in text."""
        count = 0
        for keyword in keywords:
            if keyword in text:
                count += 1
        return count

    @staticmethod
    def get_allowed_scenario_templates(story_type: StoryType) -> Set[str]:
        """
        Get allowed scenario templates for a story type.

        This prevents irrelevant scenarios from being generated
        (e.g., "Tool remains active" for Mode/Layout stories).
        """
        if story_type == StoryType.MODE_LAYOUT:
            return {
                'repeated_toggle_enter_exit',
                'restore_prior_window_state',
                'preserve_active_project',
                'menus_usable_in_mode',
                'resizing_correctness',
                'undo_redo'
            }

        elif story_type == StoryType.DIALOG:
            return {
                'close_without_create',
                'default_values_present',
                'tab_order_focus_trap',
                'invalid_input_formatting',
                'persist_last_used_settings',
                'undo_redo'
            }

        elif story_type == StoryType.TOOL:
            return {
                'tool_remains_active',
                'no_selection_behavior',
                'multi_shape_coverage',
                'angle_wrap_0_360',
                'affects_only_selected_object',
                'undo_redo'
            }

        elif story_type == StoryType.MEASUREMENT:
            return {
                'non_applicable_object_type',
                'show_hide',
                'fixed_placement_rules',
                'unit_change',
                'undo_redo',
                'duplicate_prevention'
            }

        elif story_type == StoryType.FILE_OPS:
            return {
                'recent_file_ordering',
                'file_not_found',
                'save_before_close',
                'unsaved_changes_warning',
                'undo_redo'
            }

        elif story_type == StoryType.MENU:
            return {
                'menu_item_availability',
                'keyboard_navigation',
                'disabled_state_when_not_applicable',
                'undo_redo'
            }

        elif story_type == StoryType.PROPERTIES:
            return {
                'enable_disable_toggle',
                'persist_settings',
                'apply_to_selected_object_only',
                'undo_redo'
            }

        elif story_type == StoryType.HELP_DOCUMENTATION:
            return {
                'menu_item_availability',
                'offline_access',
                'no_external_browser',
                'viewer_close',
                'keyboard_navigation'
            }

        else:
            # Unknown story type - allow common scenarios only
            return {
                'undo_redo',
                'availability'
            }

    @staticmethod
    def get_default_edge_cases(story_type: StoryType) -> List[str]:
        """
        Get default edge cases for a story type.

        These are edge cases that should be tested even if not explicitly
        mentioned in AC/QA Prep, based on the story type.
        """
        if story_type == StoryType.MODE_LAYOUT:
            return [
                'repeated_toggle_enter_exit',
                'restore_prior_state',
                'menus_usable_in_mode',
                'resizing'
            ]

        elif story_type == StoryType.DIALOG:
            return [
                'close_without_action',
                'default_values',
                'tab_order'
            ]

        elif story_type == StoryType.TOOL:
            return [
                'no_selection',
                'multi_object_selection',
                'affects_only_selected'
            ]

        elif story_type == StoryType.MEASUREMENT:
            return [
                'no_selection',
                'wrong_object_type',
                'duplicate_prevention',
                'unit_system'
            ]

        elif story_type == StoryType.FILE_OPS:
            return [
                'file_not_found',
                'recent_files_ordering',
                'unsaved_changes'
            ]

        elif story_type == StoryType.MENU:
            return [
                'keyboard_navigation',
                'disabled_when_not_applicable'
            ]

        elif story_type == StoryType.PROPERTIES:
            return [
                'enable_disable',
                'persist_settings'
            ]

        elif story_type == StoryType.HELP_DOCUMENTATION:
            return [
                'offline_access',
                'no_external_browser',
                'viewer_close'
            ]

        else:
            return []

    @staticmethod
    def should_include_accessibility(story_type: StoryType) -> bool:
        """
        Determine if accessibility tests should be generated for story type.

        Returns True if accessibility is typically tested for this story type.
        """
        # All UI story types should have accessibility tests
        return story_type in {
            StoryType.MODE_LAYOUT,
            StoryType.DIALOG,
            StoryType.MENU,
            StoryType.PROPERTIES,
            StoryType.MEASUREMENT,
            StoryType.HELP_DOCUMENTATION
        }

    @staticmethod
    def should_include_platform_tests(story_type: StoryType) -> bool:
        """
        Determine if platform-specific tests should be generated.

        Returns True if platform tests are relevant for this story type.
        """
        # Most UI interactions should be tested on multiple platforms
        return story_type in {
            StoryType.DIALOG,
            StoryType.TOOL,
            StoryType.MENU,
            StoryType.PROPERTIES,
            StoryType.MEASUREMENT
        }

    @staticmethod
    def get_typical_entry_points(story_type: StoryType) -> List[str]:
        """
        Get typical entry points for a story type.

        This is used as a fallback ONLY if no entry points are found in evidence.
        Should be used with extreme caution.
        """
        if story_type == StoryType.MODE_LAYOUT:
            return ["View Menu"]

        elif story_type == StoryType.DIALOG:
            return ["File Menu", "Create Menu"]

        elif story_type == StoryType.TOOL:
            return ["Tools Menu", "Toolbar"]

        elif story_type == StoryType.MEASUREMENT:
            return ["Dimensions Menu", "Properties – Design Panel"]

        elif story_type == StoryType.FILE_OPS:
            return ["File Menu"]

        elif story_type == StoryType.MENU:
            return ["Menu Bar"]

        elif story_type == StoryType.PROPERTIES:
            return ["Properties Panel"]

        elif story_type == StoryType.HELP_DOCUMENTATION:
            return ["Help Menu"]

        else:
            return []
