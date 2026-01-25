"""
Semantic Step Builder - Uses NLP to generate high-quality test steps from AC text.

Parses acceptance criteria semantically to extract specific actions and expected results.
"""
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

# Import hybrid parser if available
try:
    from core.services.nlp import HybridACParser, SPACY_AVAILABLE
except ImportError:
    HybridACParser = None
    SPACY_AVAILABLE = False


@dataclass
class ParsedACComponents:
    """Components extracted from acceptance criteria."""
    action_verb: str
    subject: str
    direct_object: str
    target_location: str
    condition: str
    expected_outcome: str
    ui_elements: List[str]
    values: List[str]


class SemanticStepBuilder:
    """Builds high-quality test steps from AC using semantic parsing."""

    # Action verb mappings to test step verbs
    ACTION_MAPPINGS = {
        # User actions
        "click": "Click",
        "select": "Select",
        "enter": "Enter",
        "type": "Type",
        "input": "Enter",
        "submit": "Click Submit",
        "press": "Press",
        "tap": "Tap",
        "drag": "Drag",
        "drop": "Drop",
        "scroll": "Scroll",
        "swipe": "Swipe",
        # State changes
        "enable": "Enable",
        "disable": "Disable",
        "toggle": "Toggle",
        "show": "View",
        "hide": "Hide",
        "display": "Verify",
        "open": "Open",
        "close": "Close",
        "expand": "Expand",
        "collapse": "Collapse",
        # Data operations
        "save": "Save",
        "load": "Load",
        "create": "Create",
        "delete": "Delete",
        "update": "Update",
        "edit": "Edit",
        "modify": "Modify",
        "add": "Add",
        "remove": "Remove",
        # Transformations
        "rotate": "Rotate",
        "mirror": "Mirror",
        "flip": "Flip",
        "scale": "Scale",
        "resize": "Resize",
        "move": "Move",
        "copy": "Copy",
        "paste": "Paste",
    }

    # UI element patterns
    UI_ELEMENT_PATTERNS = [
        r'\b(button|btn)\b',
        r'\b(menu|submenu)\b',
        r'\b(panel|sidebar|pane)\b',
        r'\b(dialog|modal|popup)\b',
        r'\b(field|input|textbox|textarea)\b',
        r'\b(dropdown|select|combobox)\b',
        r'\b(checkbox|radio|switch|toggle)\b',
        r'\b(tab|tabs)\b',
        r'\b(link|anchor)\b',
        r'\b(icon|image)\b',
        r'\b(list|table|grid)\b',
        r'\b(option|item)\b',
        r'\b(label|text)\b',
        r'\b(toolbar|ribbon)\b',
        r'\b(canvas|workspace|area)\b',
    ]

    # Location patterns
    LOCATION_PATTERNS = [
        r'\b(?:in|from|on|within)\s+(?:the\s+)?(\w+\s+(?:panel|menu|toolbar|dialog|section|area))',
        r'\b(\w+\s+panel)\b',
        r'\b(\w+\s+menu)\b',
        r'\b(Tools\s+menu|File\s+menu|Edit\s+menu|View\s+menu)',
        r'\b(Properties\s+panel|Dimensions\s+panel)',
    ]

    # Expected outcome patterns
    OUTCOME_PATTERNS = {
        "is_displayed": ["is displayed", "appears", "is shown", "is visible", "shows"],
        "is_enabled": ["is enabled", "becomes active", "is activated"],
        "is_disabled": ["is disabled", "is grayed out", "becomes inactive"],
        "is_selected": ["is selected", "is highlighted", "is checked"],
        "is_applied": ["is applied", "takes effect", "is saved"],
        "is_opened": ["opens", "is opened", "dialog appears"],
        "is_closed": ["closes", "is closed", "dialog closes"],
        "is_updated": ["is updated", "changes", "reflects", "shows updated"],
        "is_removed": ["is removed", "is deleted", "disappears"],
        "is_created": ["is created", "is added", "appears in"],
    }

    def __init__(self):
        """Initialize semantic step builder."""
        self._hybrid_parser = None
        if HybridACParser:
            try:
                self._hybrid_parser = HybridACParser()
            except Exception:
                pass

        # Compile patterns
        self._ui_patterns = [re.compile(p, re.IGNORECASE) for p in self.UI_ELEMENT_PATTERNS]
        self._location_patterns = [re.compile(p, re.IGNORECASE) for p in self.LOCATION_PATTERNS]

    def build_steps_from_ac(
        self,
        ac_text: str,
        feature_name: str,
        entry_point: str = "Menu"
    ) -> List[Dict[str, str]]:
        """
        Build test steps from acceptance criteria text.

        Args:
            ac_text: Acceptance criteria text
            feature_name: Name of the feature being tested
            entry_point: UI location to access the feature

        Returns:
            List of step dictionaries with action and expected keys
        """
        # Parse AC components
        components = self._parse_ac(ac_text)

        steps = []

        # Build main action step
        action_step = self._build_action_step(components, feature_name, entry_point)
        if action_step['action']:
            steps.append(action_step)

        # Build verification step if outcome detected
        verification_step = self._build_verification_step(components, feature_name)
        if verification_step['action']:
            steps.append(verification_step)

        return steps

    def enhance_generic_step(
        self,
        action: str,
        expected: str,
        feature_name: str,
        ac_text: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Enhance a generic step to be more specific.

        Args:
            action: Original action text
            expected: Original expected result
            feature_name: Feature name for context
            ac_text: Optional original AC text for context

        Returns:
            Enhanced step dictionary
        """
        # Check if step needs enhancement
        if not self._is_generic_step(action, expected):
            return {"action": action, "expected": expected}

        # Try to parse context from AC text
        if ac_text:
            components = self._parse_ac(ac_text)
        else:
            components = self._parse_ac(action)

        # Enhance action
        enhanced_action = self._enhance_action(action, components, feature_name)

        # Enhance expected result
        enhanced_expected = self._enhance_expected(expected, components, feature_name)

        return {
            "action": enhanced_action,
            "expected": enhanced_expected
        }

    def extract_specific_expected_result(
        self,
        ac_text: str,
        feature_name: str
    ) -> str:
        """
        Extract a specific expected result from AC text.

        Args:
            ac_text: Acceptance criteria text
            feature_name: Feature name for context

        Returns:
            Specific expected result string
        """
        components = self._parse_ac(ac_text)

        # Don't use direct_object if it's too long (likely the whole AC)
        obj = "selected object(s)"
        if components.direct_object and len(components.direct_object) < 30:
            obj = components.direct_object
            obj = re.sub(r'^the\s+', '', obj, flags=re.IGNORECASE)

        # Clean feature name
        clean_feature = feature_name.split('(')[0].strip()
        verb = components.action_verb.lower()

        # Map action to expected outcome
        outcome_map = {
            "display": f"{clean_feature} is displayed",
            "show": f"{clean_feature} is visible",
            "hide": f"{clean_feature} is hidden",
            "enable": f"{clean_feature} is enabled",
            "disable": f"{clean_feature} is disabled",
            "open": f"{clean_feature} dialog opens",
            "close": f"{clean_feature} closes",
            "save": f"Changes are saved successfully",
            "delete": f"{obj} is removed",
            "create": f"{obj} is created",
            "rotate": f"{obj} is rotated according to the system rotation logic",
            "mirror": f"{obj} is mirrored across the axis",
            "flip": f"{obj} is flipped",
            "select": f"{obj} is selected",
            "transform": f"{obj} transformation is applied",
        }

        if verb in outcome_map:
            return outcome_map[verb]

        # Default specific outcome based on feature
        if 'rotate' in feature_name.lower():
            return f"{obj} is rotated"
        if 'mirror' in feature_name.lower():
            return f"{obj} is mirrored"
        if 'flip' in feature_name.lower():
            return f"{obj} is flipped"

        return f"{clean_feature} is applied to {obj}"

    def _parse_ac(self, ac_text: str) -> ParsedACComponents:
        """Parse acceptance criteria into components."""
        components = ParsedACComponents(
            action_verb="",
            subject="",
            direct_object="",
            target_location="",
            condition="",
            expected_outcome="",
            ui_elements=[],
            values=[]
        )

        # Use hybrid parser if available
        if self._hybrid_parser:
            try:
                semantics = self._hybrid_parser.parse(ac_text)
                components.action_verb = semantics.action or ""
                components.subject = semantics.actor or "user"
                components.direct_object = semantics.target or ""
                components.expected_outcome = semantics.outcome or ""
            except Exception:
                pass

        # Extract UI elements
        for pattern in self._ui_patterns:
            matches = pattern.findall(ac_text)
            components.ui_elements.extend(matches)

        # Extract location
        for pattern in self._location_patterns:
            match = pattern.search(ac_text)
            if match:
                components.target_location = match.group(1)
                break

        # Extract values (numbers, quoted strings)
        value_matches = re.findall(r'(?:"([^"]+)"|\b(\d+(?:\.\d+)?)\b)', ac_text)
        for match in value_matches:
            value = match[0] or match[1]
            if value:
                components.values.append(value)

        # Extract condition (if/when clauses)
        condition_match = re.search(r'(?:if|when|while|after|before)\s+([^,\.]+)', ac_text, re.IGNORECASE)
        if condition_match:
            components.condition = condition_match.group(1).strip()

        # Fallback: extract action verb from text
        if not components.action_verb:
            for verb in self.ACTION_MAPPINGS:
                if re.search(rf'\b{verb}\b', ac_text, re.IGNORECASE):
                    components.action_verb = verb
                    break

        # Fallback: extract object after verb
        if not components.direct_object and components.action_verb:
            verb_pattern = rf'\b{components.action_verb}\s+(?:the\s+)?([^,\.]+)'
            match = re.search(verb_pattern, ac_text, re.IGNORECASE)
            if match:
                components.direct_object = match.group(1).strip()

        return components

    def _build_action_step(
        self,
        components: ParsedACComponents,
        feature_name: str,
        entry_point: str
    ) -> Dict[str, str]:
        """Build the main action step."""
        action_parts = []

        # Get mapped action verb
        verb = components.action_verb.lower()
        action_word = self.ACTION_MAPPINGS.get(verb, verb.capitalize() if verb else "Perform")

        # Build action with object
        if components.direct_object:
            obj = components.direct_object
            # Clean up object text
            obj = re.sub(r'^the\s+', '', obj, flags=re.IGNORECASE)
            action_parts.append(f"{action_word} the {obj}")
        elif components.ui_elements:
            action_parts.append(f"{action_word} the {components.ui_elements[0]}")
        else:
            action_parts.append(f"{action_word} the {feature_name}")

        # Add location context
        if components.target_location:
            action_parts.append(f"from the {components.target_location}")
        elif entry_point:
            action_parts.append(f"from the {entry_point}")

        # Add values if present
        if components.values:
            action_parts.append(f"with value {components.values[0]}")

        action = " ".join(action_parts) + "."

        # Expected result for action steps (often empty for intermediate steps)
        expected = ""

        return {"action": action, "expected": expected}

    def _build_verification_step(
        self,
        components: ParsedACComponents,
        feature_name: str
    ) -> Dict[str, str]:
        """Build the verification step."""
        # Determine what to verify
        if components.expected_outcome:
            expected = components.expected_outcome
            if not expected.endswith('.'):
                expected += '.'
        elif components.direct_object:
            obj = components.direct_object
            verb = components.action_verb.lower()

            # Generate specific expected based on action
            expected = self._generate_expected_for_action(verb, obj, feature_name)
        else:
            expected = f"{feature_name} is applied successfully."

        # Build verify action
        action = f"Verify the {feature_name} action result."

        # Make expected more specific if still generic
        if "as expected" in expected.lower() or "successfully" in expected.lower():
            expected = self._make_expected_specific(expected, components, feature_name)

        return {"action": action, "expected": expected}

    def _generate_expected_for_action(
        self,
        verb: str,
        obj: str,
        feature_name: str
    ) -> str:
        """Generate expected result based on action verb."""
        # Clean object
        obj_clean = re.sub(r'^the\s+', '', obj, flags=re.IGNORECASE)

        # Map verbs to observable outcomes
        verb_outcomes = {
            "display": f"{obj_clean} is displayed",
            "show": f"{obj_clean} is visible",
            "hide": f"{obj_clean} is hidden",
            "enable": f"{obj_clean} is enabled",
            "disable": f"{obj_clean} is disabled",
            "open": f"{obj_clean} opens",
            "close": f"{obj_clean} closes",
            "save": f"{obj_clean} is saved without errors",
            "delete": f"{obj_clean} is removed from the workspace",
            "create": f"{obj_clean} is created and visible",
            "rotate": f"Selected {obj_clean} is rotated",
            "mirror": f"Selected {obj_clean} is mirrored",
            "flip": f"Selected {obj_clean} is flipped",
            "select": f"{obj_clean} is highlighted/selected",
            "apply": f"{obj_clean} is applied to the selection",
            "transform": f"Selected {obj_clean} transformation is applied",
        }

        if verb in verb_outcomes:
            return verb_outcomes[verb] + "."

        # Default
        return f"{feature_name} {verb} action is completed."

    def _enhance_action(
        self,
        action: str,
        components: ParsedACComponents,
        feature_name: str
    ) -> str:
        """Enhance a generic action to be specific."""
        # Remove generic patterns
        enhanced = action
        generic_patterns = [
            r'Perform the action described:?\s*',
            r'Perform action:?\s*',
            r'Execute the following:?\s*',
        ]
        for pattern in generic_patterns:
            enhanced = re.sub(pattern, '', enhanced, flags=re.IGNORECASE)

        # Clean the remaining text
        enhanced = enhanced.strip()

        # If text is just a tool name or very short, expand it
        if enhanced and len(enhanced) < 25:
            # Check if it's a tool/feature name
            tool_name = enhanced.rstrip('.')

            # Map tool names to specific actions
            tool_action_map = {
                'rotate tool': 'Select the Rotate tool from the Tools menu and apply rotation to the selected object',
                'rotate': 'Select the Rotate tool and apply rotation to the selected object',
                'mirror horizontally': 'Select Mirror Horizontally from the Tools menu to flip the object across the vertical axis',
                'mirror vertically': 'Select Mirror Vertically from the Tools menu to flip the object across the horizontal axis',
                'mirror': 'Select the Mirror option from the Tools menu to flip the selected object',
                'flip': 'Select the Flip option from the Tools menu',
            }

            tool_name_lower = tool_name.lower()
            for tool, specific_action in tool_action_map.items():
                if tool in tool_name_lower or tool_name_lower in tool:
                    return specific_action + "."

            # If still short, build from feature name
            return f"Select the {tool_name} option from the menu."

        # If still looks generic or empty, rebuild from components
        if not enhanced or len(enhanced) < 10:
            clean_feature = feature_name.split('(')[0].strip()
            if components.action_verb:
                verb = self.ACTION_MAPPINGS.get(
                    components.action_verb.lower(),
                    components.action_verb.capitalize()
                )
                return f"{verb} the {clean_feature} to the selected object."
            return f"Apply the {clean_feature} action to the selected object."

        return enhanced if enhanced.endswith('.') else enhanced + "."

    def _enhance_expected(
        self,
        expected: str,
        components: ParsedACComponents,
        feature_name: str
    ) -> str:
        """Enhance a generic expected result to be observable."""
        # Check for generic phrases
        generic_checks = [
            "works as expected",
            "works correctly",
            "is completed successfully",
            "as expected",
            "should work",
        ]

        is_generic = any(phrase in expected.lower() for phrase in generic_checks)

        if is_generic:
            # Clean feature name
            clean_feature = feature_name.split('(')[0].strip()

            # Feature-specific observable outcomes
            feature_outcomes = {
                'rotate': 'Selected object is rotated according to system logic.',
                'mirror': 'Selected object is mirrored across the axis.',
                'flip': 'Selected object is flipped.',
                'transform': 'Object transformation is applied and visible on canvas.',
            }

            for feature_word, outcome in feature_outcomes.items():
                if feature_word in feature_name.lower():
                    return outcome

            # Generate from components if available
            if components.action_verb:
                verb = components.action_verb.lower()
                obj = "selected object(s)"
                if components.direct_object and len(components.direct_object) < 30:
                    obj = components.direct_object
                return self._generate_expected_for_action(verb, obj, clean_feature)

            return f"{clean_feature} is applied to the selected object."

        return expected

    def _make_expected_specific(
        self,
        expected: str,
        components: ParsedACComponents,
        feature_name: str
    ) -> str:
        """Make expected result more specific."""
        if components.direct_object:
            obj = components.direct_object
            verb = components.action_verb.lower()

            # Replace generic with specific
            replacements = {
                "successfully": f"and {obj} is updated",
                "as expected": f"and {obj} reflects the change",
                "works correctly": f"is applied to {obj}",
            }

            result = expected
            for generic, specific in replacements.items():
                if generic in result.lower():
                    result = re.sub(generic, specific, result, flags=re.IGNORECASE)
                    break

            return result

        return expected

    def _is_generic_step(self, action: str, expected: str) -> bool:
        """Check if a step contains generic phrases."""
        combined = (action + " " + expected).lower()
        generic_phrases = [
            "works as expected",
            "perform the action described",
            "perform action",
            "as expected",
            "works correctly",
            "is completed successfully",
        ]
        return any(phrase in combined for phrase in generic_phrases)


def get_semantic_step_builder() -> SemanticStepBuilder:
    """Get singleton semantic step builder instance."""
    if not hasattr(get_semantic_step_builder, '_instance'):
        get_semantic_step_builder._instance = SemanticStepBuilder()
    return get_semantic_step_builder._instance
