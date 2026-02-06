#!/usr/bin/env python3
"""
Expert AC Analyzer - Derives test scenarios like a senior QA engineer.

This module analyzes acceptance criteria to extract:
1. Implicit negative tests from "out of scope", "only X", "not supported"
2. Workflow tests that verify state persistence across operations
3. Modal behavior tests (focus trap, background blocking)
4. Setting dependency tests (verify behavior follows settings)
5. Positive/negative pairs from dual-action ACs
6. Boundary tests from numeric constraints
7. UI verification tests from display requirements

Human QA engineers don't just test what's written - they test:
- What's implied (if modal, test focus trap)
- What's excluded (if landscape out of scope, verify it's not available)
- State persistence (if recent items tracked, create → verify → create again)
- Error states (if commands disabled, verify they're disabled when expected)
"""
from typing import List, Dict, Tuple, Optional
import re
from dataclasses import dataclass, field


@dataclass
class DerivedTestScenario:
    """A test scenario derived from AC analysis."""
    type: str  # 'positive', 'negative', 'workflow', 'boundary', 'state', 'a11y'
    title: str
    objective: str
    source_ac: str
    source_ac_index: int
    steps_description: List[str]
    area: str = "Canvas"
    priority: str = "medium"  # 'high', 'medium', 'low'
    tags: List[str] = field(default_factory=list)


class ExpertACAnalyzer:
    """
    Analyzes acceptance criteria like a senior QA engineer.

    Expert QA approach:
    1. Read each AC carefully for explicit requirements
    2. Derive implicit requirements from context
    3. Identify what's NOT supposed to happen (negative tests)
    4. Plan workflow tests that verify state across operations
    5. Consider edge cases and error states
    """

    # Patterns that indicate negative test opportunities
    NEGATIVE_INDICATORS = [
        (r'\bout[\s-]?of[\s-]?scope\b', 'out_of_scope'),
        (r'\bexcluded\b', 'excluded'),
        (r'\bnot\s+(?:available|supported|included)\b', 'not_available'),
        (r'\bonly\s+(\w+)', 'only_option'),
        (r'\bno\s+(\w+)\s+option\b', 'no_option'),
        (r'\bdisabled\s+(?:when|if|unless)\b', 'conditional_disabled'),
        (r'\benabled\s+only\s+when\b', 'conditional_enabled'),
        (r'\bcannot\b', 'cannot'),
        (r'\bwithout\b', 'without'),
        (r'\bphase\s*\d+\b', 'phased'),  # "Phase 1" implies some features deferred
    ]

    # Patterns that indicate workflow/state test opportunities
    WORKFLOW_INDICATORS = [
        (r'\brecent(?:\s+items?)?\b', 'recent_items'),
        (r'\bhistory\b', 'history'),
        (r'\blast[\s-]?used\b', 'last_used'),
        (r'\bdefault(?:s)?\s+to\b', 'default_value'),
        (r'\bfollows?\s+(?:the\s+)?(?:current\s+)?(\w+)\s+setting\b', 'follows_setting'),
        (r'\bremember(?:s|ed)?\b', 'remembers'),
        (r'\bpersist(?:s|ed)?\b', 'persists'),
        (r'\bsave(?:s|d)?\b.*\bpreset\b', 'save_preset'),
    ]

    # Patterns that indicate modal/dialog behavior tests
    MODAL_INDICATORS = [
        (r'\bmodal\s+(?:dialog|window)\b', 'modal'),
        (r'\bdialog\b', 'dialog'),
        (r'\bpopup\b', 'popup'),
        (r'\boverlay\b', 'overlay'),
    ]

    # Patterns for dual-action ACs (positive and negative in one AC)
    DUAL_ACTION_PATTERNS = [
        (r'"(\w+)"\s+(?:initializes|creates|opens|performs).+;\s*"(\w+)"\s+(?:exits|closes|cancels|discards)', 'create_cancel_pair'),
        (r'(\w+)\s+(?:and|or)\s+(\w+)\s+buttons?\b', 'button_pair'),
    ]

    # Patterns for default values that need verification
    DEFAULT_VALUE_PATTERNS = [
        (r'default(?:\s+preset)?\s*=\s*["\']?([^"\'\.]+)', 'default_preset'),
        (r'defaults?\s+to\s+["\']?([^"\'\.]+)', 'default_value'),
        (r'default\s+(?:size|width|height|unit)\s*(?:is|:)?\s*(\d+(?:\s*[×x]\s*\d+)?)', 'default_dimension'),
    ]

    # Patterns for fields/controls that need UI verification
    FIELDS_PATTERNS = [
        (r'fields?\s+(?:available|displayed|include|shown)\s*:?\s*([^\.]+)', 'fields_list'),
        (r'(?:has|includes?|contains?|shows?)\s+(?:a\s+)?(\w+(?:\s*,\s*\w+)*)\s+(?:field|control|button|dropdown)', 'controls_list'),
    ]

    def __init__(self, feature_name: str, platforms: List[str] = None):
        self.feature_name = feature_name
        self.platforms = platforms or ['Windows 11', 'iPad', 'Android Tablet']

    def analyze(self, acceptance_criteria: List[str]) -> List[DerivedTestScenario]:
        """
        Analyze all ACs and derive comprehensive test scenarios.

        Returns scenarios in priority order: high (core) → medium (workflows) → lower (edge)
        """
        scenarios = []

        for idx, ac in enumerate(acceptance_criteria):
            ac_clean = ac.strip()
            if not ac_clean or self._is_header(ac_clean):
                continue

            # 1. Derive positive test (always)
            positive = self._derive_positive_test(ac_clean, idx)
            if positive:
                scenarios.append(positive)

            # 2. Check for negative test opportunities
            negatives = self._derive_negative_tests(ac_clean, idx)
            scenarios.extend(negatives)

            # 3. Check for workflow/state tests
            workflows = self._derive_workflow_tests(ac_clean, idx, acceptance_criteria)
            scenarios.extend(workflows)

            # 4. Check for modal behavior tests
            modal_tests = self._derive_modal_tests(ac_clean, idx)
            scenarios.extend(modal_tests)

            # 5. Check for dual-action tests
            dual_tests = self._derive_dual_action_tests(ac_clean, idx)
            scenarios.extend(dual_tests)

            # 6. Check for default value verification tests
            default_tests = self._derive_default_value_tests(ac_clean, idx)
            scenarios.extend(default_tests)

            # 7. Check for UI control verification tests
            ui_tests = self._derive_ui_control_tests(ac_clean, idx)
            scenarios.extend(ui_tests)

        # Sort by priority and deduplicate similar scenarios
        scenarios = self._deduplicate_scenarios(scenarios)
        scenarios.sort(key=lambda s: {'high': 0, 'medium': 1, 'low': 2}.get(s.priority, 1))

        return scenarios

    def _is_header(self, text: str) -> bool:
        """Check if text is a header/label, not an AC."""
        headers = ['acceptance criteria', 'ac:', 'requirements:', 'definition of done']
        return text.lower().strip().rstrip(':') in headers

    def _derive_positive_test(self, ac: str, idx: int) -> Optional[DerivedTestScenario]:
        """Derive the primary positive test from an AC."""
        # Skip ACs that are purely negative/exclusion statements
        if self._is_purely_negative(ac):
            return None

        title = self._extract_test_title(ac)
        area = self._determine_area(ac)

        return DerivedTestScenario(
            type='positive',
            title=title,
            objective=f"Verify that {self._humanize_ac(ac)}",
            source_ac=ac,
            source_ac_index=idx,
            steps_description=self._derive_positive_steps(ac),
            area=area,
            priority='high',
            tags=['core', 'positive']
        )

    def _derive_negative_tests(self, ac: str, idx: int) -> List[DerivedTestScenario]:
        """Derive negative tests from exclusion/limitation statements."""
        tests = []
        ac_lower = ac.lower()

        for pattern, indicator_type in self.NEGATIVE_INDICATORS:
            match = re.search(pattern, ac_lower)
            if match:
                if indicator_type == 'out_of_scope':
                    # Extract what's out of scope and create a "verify NOT available" test
                    excluded_feature = self._extract_excluded_feature(ac)
                    if excluded_feature:
                        tests.append(DerivedTestScenario(
                            type='negative',
                            title=f"{excluded_feature} not available (out of scope)",
                            objective=f"Verify that {excluded_feature} option is NOT available in the UI",
                            source_ac=ac,
                            source_ac_index=idx,
                            steps_description=[
                                "Open the relevant dialog/menu",
                                f"Verify that {excluded_feature} option is NOT displayed",
                                f"Confirm no way to access {excluded_feature} functionality"
                            ],
                            area=self._determine_area(ac),
                            priority='medium',
                            tags=['negative', 'out_of_scope']
                        ))

                elif indicator_type == 'only_option':
                    # "Only Portrait" means verify no Landscape
                    only_value = match.group(1) if match.groups() else None
                    if only_value:
                        opposite = self._get_opposite_option(only_value, ac)
                        if opposite:
                            tests.append(DerivedTestScenario(
                                type='negative',
                                title=f"No {opposite} option available ({only_value} only)",
                                objective=f"Verify that {opposite} is NOT available since only {only_value} is supported",
                                source_ac=ac,
                                source_ac_index=idx,
                                steps_description=[
                                    "Open the relevant dialog/panel",
                                    f"Verify {only_value} is shown/selected",
                                    f"Verify no {opposite} option is available"
                                ],
                                area=self._determine_area(ac),
                                priority='medium',
                                tags=['negative', 'only_option']
                            ))

                elif indicator_type == 'conditional_disabled':
                    # "disabled when no selection" → test disabled state
                    condition = self._extract_condition(ac)
                    tests.append(DerivedTestScenario(
                        type='negative',
                        title=f"Commands disabled state ({condition})",
                        objective=f"Verify that commands are disabled when {condition}",
                        source_ac=ac,
                        source_ac_index=idx,
                        steps_description=[
                            f"Setup: Ensure {condition}",
                            "Navigate to the feature commands",
                            "Verify commands are visually disabled/grayed out",
                            "Attempt to click/activate the commands",
                            "Verify no action occurs"
                        ],
                        area=self._determine_area(ac),
                        priority='high',
                        tags=['negative', 'disabled_state']
                    ))

                elif indicator_type == 'conditional_enabled':
                    # "enabled only when selected" → test both enabled AND disabled states
                    condition = self._extract_enable_condition(ac)
                    # Disabled state test
                    tests.append(DerivedTestScenario(
                        type='negative',
                        title=f"Commands disabled without {condition}",
                        objective=f"Verify that commands are disabled when {condition} is NOT met",
                        source_ac=ac,
                        source_ac_index=idx,
                        steps_description=[
                            f"Setup: Ensure {condition} is NOT met",
                            "Navigate to the feature commands",
                            "Verify commands are disabled"
                        ],
                        area=self._determine_area(ac),
                        priority='high',
                        tags=['negative', 'conditional']
                    ))

        return tests

    def _derive_workflow_tests(self, ac: str, idx: int, all_acs: List[str]) -> List[DerivedTestScenario]:
        """Derive workflow tests that verify state persistence."""
        tests = []
        ac_lower = ac.lower()

        for pattern, indicator_type in self.WORKFLOW_INDICATORS:
            match = re.search(pattern, ac_lower)
            if match:
                if indicator_type == 'recent_items':
                    # Test recent items: create → reopen → verify history
                    tests.append(DerivedTestScenario(
                        type='workflow',
                        title="Recent items populated after document creation",
                        objective="Verify that Recent Items shows the most recently used preset after creating a document",
                        source_ac=ac,
                        source_ac_index=idx,
                        steps_description=[
                            "Open the New Document dialog",
                            "Set custom width and height values",
                            "Click Create to create the document",
                            "Open File menu and select New again",
                            "Verify Recent Items section shows the previously used preset"
                        ],
                        area="Dialog Window",
                        priority='medium',
                        tags=['workflow', 'state_persistence']
                    ))
                    # Also test empty state
                    tests.append(DerivedTestScenario(
                        type='workflow',
                        title="Recent items displays without errors when empty",
                        objective="Verify that Recent Items section displays correctly when no history exists",
                        source_ac=ac,
                        source_ac_index=idx,
                        steps_description=[
                            "Fresh install or clear history",
                            "Open the New Document dialog",
                            "Verify Recent Items section is displayed without errors",
                            "Verify no crash or error occurs"
                        ],
                        area="Dialog Window",
                        priority='low',
                        tags=['workflow', 'empty_state']
                    ))

                elif indicator_type == 'follows_setting':
                    setting_name = match.group(1) if match.groups() else 'setting'
                    # Test setting synchronization
                    tests.append(DerivedTestScenario(
                        type='workflow',
                        title=f"Dropdown follows {setting_name} setting (inches)",
                        objective=f"Verify that the dropdown defaults to the current {setting_name} setting when set to inches",
                        source_ac=ac,
                        source_ac_index=idx,
                        steps_description=[
                            f"Open Settings and set {setting_name} to inches",
                            "Open the New Document dialog",
                            "Verify the Units dropdown shows 'in'"
                        ],
                        area="Dialog Window",
                        priority='high',
                        tags=['workflow', 'setting_sync']
                    ))
                    tests.append(DerivedTestScenario(
                        type='workflow',
                        title=f"Dropdown follows {setting_name} setting (centimeters)",
                        objective=f"Verify that the dropdown defaults to the current {setting_name} setting when set to centimeters",
                        source_ac=ac,
                        source_ac_index=idx,
                        steps_description=[
                            f"Open Settings and set {setting_name} to centimeters",
                            "Open the New Document dialog",
                            "Verify the Units dropdown shows 'cm'"
                        ],
                        area="Dialog Window",
                        priority='high',
                        tags=['workflow', 'setting_sync']
                    ))

                elif indicator_type == 'default_value':
                    default = match.group(1) if match.groups() else 'default'
                    tests.append(DerivedTestScenario(
                        type='workflow',
                        title=f"Field defaults to {default}",
                        objective=f"Verify that the field defaults to '{default}' when the dialog opens",
                        source_ac=ac,
                        source_ac_index=idx,
                        steps_description=[
                            "Open the relevant dialog",
                            f"Verify the field shows '{default}' by default",
                            "Do not modify anything",
                            f"Confirm default value is '{default}'"
                        ],
                        area="Dialog Window",
                        priority='medium',
                        tags=['workflow', 'default']
                    ))

        return tests

    def _derive_modal_tests(self, ac: str, idx: int) -> List[DerivedTestScenario]:
        """Derive tests for modal dialog behavior."""
        tests = []
        ac_lower = ac.lower()

        for pattern, indicator_type in self.MODAL_INDICATORS:
            if re.search(pattern, ac_lower):
                if indicator_type == 'modal':
                    # Modal dialogs should block background interaction
                    tests.append(DerivedTestScenario(
                        type='negative',
                        title="Modal blocks interaction with canvas behind",
                        objective="Verify that the modal dialog blocks interaction with the canvas/background",
                        source_ac=ac,
                        source_ac_index=idx,
                        steps_description=[
                            "Have a document open with objects on canvas",
                            "Open the modal dialog",
                            "Attempt to click on the canvas behind the modal",
                            "Verify the click does not affect the canvas",
                            "Verify user cannot interact with canvas until modal is closed"
                        ],
                        area="Modal Window",
                        priority='medium',
                        tags=['modal', 'ui_behavior']
                    ))
                break  # Only add modal tests once per AC

        return tests

    def _derive_dual_action_tests(self, ac: str, idx: int) -> List[DerivedTestScenario]:
        """Derive tests from ACs that describe two actions (e.g., Create/Close)."""
        tests = []
        ac_lower = ac.lower()

        # Look for patterns like: "Create" initializes...; "Close" exits...
        for pattern, pair_type in self.DUAL_ACTION_PATTERNS:
            match = re.search(pattern, ac_lower)
            if match:
                if pair_type == 'create_cancel_pair':
                    action1, action2 = match.groups()
                    # Create/positive test
                    tests.append(DerivedTestScenario(
                        type='positive',
                        title=f"{action1.capitalize()} button creates new canvas",
                        objective=f"Verify that clicking '{action1.capitalize()}' creates a new document with selected settings",
                        source_ac=ac,
                        source_ac_index=idx,
                        steps_description=[
                            "Open the New Document dialog",
                            "Set desired size and units",
                            f"Click '{action1.capitalize()}'",
                            "Verify a new blank canvas is created with the selected settings"
                        ],
                        area="Dialog Window",
                        priority='high',
                        tags=['positive', 'create_action']
                    ))
                    # Cancel/negative test
                    tests.append(DerivedTestScenario(
                        type='negative',
                        title=f"{action2.capitalize()} button cancels without creating",
                        objective=f"Verify that clicking '{action2.capitalize()}' closes dialog without creating new document",
                        source_ac=ac,
                        source_ac_index=idx,
                        steps_description=[
                            "Have an existing document open",
                            "Note the current state",
                            "Open the New Document dialog",
                            "Modify width/height values",
                            f"Click '{action2.capitalize()}'",
                            "Verify dialog closes",
                            "Verify no new document was created",
                            "Verify user is back to the previously open document"
                        ],
                        area="Dialog Window",
                        priority='high',
                        tags=['negative', 'cancel_action']
                    ))

        return tests

    def _derive_default_value_tests(self, ac: str, idx: int) -> List[DerivedTestScenario]:
        """Derive tests for default value verification."""
        tests = []

        for pattern, value_type in self.DEFAULT_VALUE_PATTERNS:
            match = re.search(pattern, ac, re.IGNORECASE)
            if match:
                default_value = match.group(1).strip()
                tests.append(DerivedTestScenario(
                    type='positive',
                    title=f"Default preset shows {default_value}",
                    objective=f"Verify that the default preset is '{default_value}'",
                    source_ac=ac,
                    source_ac_index=idx,
                    steps_description=[
                        "Open the New Document dialog",
                        f"Verify Preset Details shows '{default_value}'",
                        "Verify dimensions match the default preset"
                    ],
                    area="Dialog Window",
                    priority='high',
                    tags=['positive', 'default_value']
                ))
                break  # Only one default value test per AC

        return tests

    def _derive_ui_control_tests(self, ac: str, idx: int) -> List[DerivedTestScenario]:
        """Derive tests for UI control verification."""
        tests = []

        for pattern, control_type in self.FIELDS_PATTERNS:
            match = re.search(pattern, ac, re.IGNORECASE)
            if match:
                fields_str = match.group(1).strip()
                # Parse field list
                fields = [f.strip() for f in re.split(r'[,;]', fields_str) if f.strip()]

                if fields:
                    tests.append(DerivedTestScenario(
                        type='positive',
                        title="Required sections and controls display",
                        objective=f"Verify that all required fields/controls are displayed: {', '.join(fields)}",
                        source_ac=ac,
                        source_ac_index=idx,
                        steps_description=[
                            "Open the relevant dialog",
                            *[f"Verify {field} is displayed" for field in fields[:5]],  # Limit steps
                            "Verify all controls are functional"
                        ],
                        area="Dialog Window",
                        priority='high',
                        tags=['positive', 'ui_verification']
                    ))
                break

        return tests

    # Helper methods

    def _is_purely_negative(self, ac: str) -> bool:
        """Check if AC is purely an exclusion statement (no positive requirement)."""
        ac_lower = ac.lower()
        pure_negative_patterns = [
            r'^(?:no|not|never|excluded)',
            r'^\[?out[\s-]?of[\s-]?scope\]?',
            r'^(?:landscape|feature\s+x)\s+(?:is\s+)?(?:not|out)',
        ]
        return any(re.match(p, ac_lower.strip()) for p in pure_negative_patterns)

    def _extract_test_title(self, ac: str) -> str:
        """Extract a concise test title from AC text."""
        # Remove common prefixes
        text = re.sub(r'^(?:the\s+)?(?:user\s+)?(?:can|should|must|shall)\s+', '', ac, flags=re.IGNORECASE)

        # Extract key action/feature
        if len(text) > 60:
            # Find a natural break point
            breaks = ['. ', '; ', ' - ', ' – ']
            for brk in breaks:
                if brk in text[:60]:
                    text = text[:text.index(brk)]
                    break
            else:
                # Truncate at word boundary
                text = text[:57].rsplit(' ', 1)[0] + '...'

        return text.strip().rstrip('.')

    def _humanize_ac(self, ac: str) -> str:
        """Convert AC to a natural verification statement."""
        text = ac.strip()
        # Remove bullet markers
        text = re.sub(r'^[-•*]\s*', '', text)
        # Lowercase first char if not acronym
        if text and text[0].isupper() and (len(text) < 2 or not text[1].isupper()):
            text = text[0].lower() + text[1:]
        return text

    def _determine_area(self, ac: str) -> str:
        """Determine the UI area from AC text."""
        ac_lower = ac.lower()
        area_mappings = [
            (r'\bfile\s+menu\b', 'File Menu'),
            (r'\bedit\s+menu\b', 'Edit Menu'),
            (r'\btools?\s+menu\b', 'Tools Menu'),
            (r'\bview\s+menu\b', 'View Menu'),
            (r'\bproperties\s+panel\b', 'Properties Panel'),
            (r'\bmodal\b', 'Modal Window'),
            (r'\bdialog\b', 'Dialog Window'),
            (r'\bcanvas\b', 'Canvas'),
            (r'\bsettings?\b', 'Settings'),
        ]
        for pattern, area in area_mappings:
            if re.search(pattern, ac_lower):
                return area
        return 'Canvas'

    def _extract_excluded_feature(self, ac: str) -> Optional[str]:
        """Extract what feature is excluded/out of scope."""
        patterns = [
            r'(\w+(?:\s+\w+)?)\s+(?:is\s+)?out[\s-]?of[\s-]?scope',
            r'(?:no|not)\s+(\w+(?:\s+\w+)?)\s+(?:option|support)',
            r'(\w+)\s*=\s*\w+\s*\([^)]*out[\s-]?of[\s-]?scope',
        ]
        for pattern in patterns:
            match = re.search(pattern, ac, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _get_opposite_option(self, only_value: str, context: str) -> Optional[str]:
        """Get the opposite of an 'only X' value."""
        opposites = {
            'portrait': 'Landscape',
            'landscape': 'Portrait',
            'inches': 'centimeters',
            'centimeters': 'inches',
            'in': 'cm',
            'cm': 'in',
            'enabled': 'disabled',
            'disabled': 'enabled',
            'visible': 'hidden',
            'hidden': 'visible',
        }
        return opposites.get(only_value.lower())

    def _extract_condition(self, ac: str) -> str:
        """Extract the condition from a conditional statement."""
        patterns = [
            r'disabled\s+(?:when|if)\s+([^\.]+)',
            r'when\s+([^,\.]+)',
            r'unless\s+([^,\.]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, ac, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return "condition not met"

    def _extract_enable_condition(self, ac: str) -> str:
        """Extract the enable condition."""
        patterns = [
            r'enabled\s+only\s+when\s+([^\.]+)',
            r'only\s+(?:enabled|available)\s+when\s+([^\.]+)',
            r'when\s+(?:at\s+least\s+)?(\w+(?:\s+\w+)*)\s+(?:is\s+)?selected',
        ]
        for pattern in patterns:
            match = re.search(pattern, ac, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return "required condition"

    def _derive_positive_steps(self, ac: str) -> List[str]:
        """Derive step descriptions for positive test."""
        steps = ["Open the application", "Navigate to the feature"]

        ac_lower = ac.lower()
        if 'select' in ac_lower or 'click' in ac_lower:
            steps.append("Perform the selection/click action")
        if 'verify' in ac_lower or 'confirm' in ac_lower:
            steps.append("Verify the expected result")
        else:
            steps.append("Verify the feature works as described")

        return steps

    def _deduplicate_scenarios(self, scenarios: List[DerivedTestScenario]) -> List[DerivedTestScenario]:
        """Remove duplicate or very similar scenarios."""
        seen_titles = set()
        unique = []
        for s in scenarios:
            # Normalize title for comparison
            title_key = re.sub(r'\s+', ' ', s.title.lower().strip())
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique.append(s)
        return unique


def analyze_acceptance_criteria(
    feature_name: str,
    acceptance_criteria: List[str],
    platforms: List[str] = None
) -> Tuple[List[DerivedTestScenario], Dict[str, int]]:
    """
    Convenience function to analyze ACs and return scenarios with stats.

    Returns:
        Tuple of (scenarios, stats_dict)
    """
    analyzer = ExpertACAnalyzer(feature_name, platforms)
    scenarios = analyzer.analyze(acceptance_criteria)

    stats = {
        'total': len(scenarios),
        'positive': len([s for s in scenarios if s.type == 'positive']),
        'negative': len([s for s in scenarios if s.type == 'negative']),
        'workflow': len([s for s in scenarios if s.type == 'workflow']),
        'boundary': len([s for s in scenarios if s.type == 'boundary']),
    }

    return scenarios, stats
