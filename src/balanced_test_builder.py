"""
Balanced Test Builder - Generates properly balanced, comprehensive test cases.

Follows strict rules:
- Balanced titles: Feature / Concrete Area / Specific Scenario
- Comprehensive steps with proper Expected results
- No dry/generic language
- Device-specific accessibility tests
"""

from typing import Dict, List, Tuple
import re


class BalancedTestBuilder:
    """Builds balanced, comprehensive test cases from AC analysis."""

    def __init__(self, story_id: int, feature_name: str):
        self.story_id = story_id
        self.feature_name = feature_name
        self.test_counter = 5  # Start at 005 after AC1

    def build_ac1_availability(self, entry_point: str, submenu_items: List[str]) -> Dict:
        """Build AC1 availability test - verifies submenu/actions are accessible."""
        test_id = f"{self.story_id}-AC1"

        # Balanced title: Feature / Entry Point / Submenu Available
        title = f"{test_id}: {self.feature_name} / {entry_point} / Submenu Actions Available"

        steps = [
            {
                "action": "PRE-REQ: ENV QuickDraw application is installed",
                "expected": ""
            },
            {
                "action": "Launch the ENV QuickDraw application.",
                "expected": ""
            },
            {
                "action": f"Navigate to {entry_point}.",
                "expected": ""
            },
            {
                "action": f"Verify all {self.feature_name} actions are visible and enabled.",
                "expected": f"{', '.join(submenu_items) if submenu_items else self.feature_name + ' actions'} are visible and enabled in the submenu."
            },
            {
                "action": "Close/Exit the QuickDraw application",
                "expected": ""
            }
        ]

        objective = f"the {self.feature_name} submenu actions are available and accessible from {entry_point}"

        return {
            'id': test_id,
            'title': title,
            'steps': steps,
            'objective': objective,
            'ac_index': 1
        }

    def build_primary_ac_test(self, ac_bullet: str, area: str, ac_index: int) -> Dict:
        """Build primary AC test with balanced title and comprehensive steps."""
        test_id = f"{self.story_id}-{self.test_counter:03d}"
        self.test_counter += 5

        # Parse AC to extract scenario
        scenario = self._extract_balanced_scenario(ac_bullet)

        # Build balanced title
        title = f"{test_id}: {self.feature_name} / {area} / {scenario}"

        # Build comprehensive steps
        steps = self._build_comprehensive_steps(ac_bullet, area)

        # Build objective
        objective = self._build_objective(ac_bullet)

        return {
            'id': test_id,
            'title': title,
            'steps': steps,
            'objective': objective,
            'ac_index': ac_index
        }

    def build_boundary_test(self, base_ac: str, boundary_type: str, area: str) -> Dict:
        """Build boundary/edge case test."""
        test_id = f"{self.story_id}-{self.test_counter:03d}"
        self.test_counter += 5

        # Generate boundary scenario
        scenario = self._generate_boundary_scenario(base_ac, boundary_type)

        title = f"{test_id}: {self.feature_name} / {area} / {scenario}"

        steps = self._build_boundary_steps(base_ac, boundary_type, area)

        objective = self._build_boundary_objective(base_ac, boundary_type)

        return {
            'id': test_id,
            'title': title,
            'steps': steps,
            'objective': objective,
            'ac_index': None  # Boundary test
        }

    def build_qa_test(self, qa_type: str, area: str, context: Dict) -> Dict:
        """Build QA support test (undo/redo, persistence, multi-select, etc.)."""
        test_id = f"{self.story_id}-{self.test_counter:03d}"
        self.test_counter += 5

        scenario = self._get_qa_scenario(qa_type)
        title = f"{test_id}: {self.feature_name} / {area} / {scenario}"

        steps = self._build_qa_steps(qa_type, area, context)

        objective = self._build_qa_objective(qa_type)

        return {
            'id': test_id,
            'title': title,
            'steps': steps,
            'objective': objective,
            'ac_index': None  # QA test
        }

    def build_accessibility_test(self, device: str, area: str) -> Dict:
        """Build device-specific accessibility test."""
        test_id = f"{self.story_id}-{self.test_counter:03d}"
        self.test_counter += 5

        # Device must appear in title
        scenario = f"Accessibility Validation ({device})"
        title = f"{test_id}: {self.feature_name} / {area} / {scenario}"

        steps = self._build_accessibility_steps(device, area)

        objective = f"{self.feature_name} controls are accessible via keyboard and screen reader on {device}"

        return {
            'id': test_id,
            'title': title,
            'steps': steps,
            'objective': objective,
            'ac_index': None  # Accessibility test
        }

    def _extract_balanced_scenario(self, ac_bullet: str) -> str:
        """Extract balanced scenario from AC bullet.

        Format: Action + Target + Outcome
        Example: "Change Line Color Using Color Picker"
        """
        # Remove common prefixes
        ac_lower = ac_bullet.lower().strip()
        ac_lower = re.sub(r'^(user can|user should|system must|the system|expected behavior)', '', ac_lower).strip()

        # Remove trailing periods/punctuation
        ac_lower = ac_lower.rstrip('.!,;')

        # Capitalize key words (max 10 words for readability)
        words = ac_lower.split()[:10]
        return ' '.join(w.capitalize() for w in words)

    def _build_comprehensive_steps(self, ac_bullet: str, area: str) -> List[Dict]:
        """Build comprehensive test steps with proper Expected results."""
        steps = []

        # Step 1: PRE-REQ
        steps.append({
            "action": "PRE-REQ: ENV QuickDraw application is installed",
            "expected": ""
        })

        # Step 2: Launch
        steps.append({
            "action": "Launch the ENV QuickDraw application.",
            "expected": ""
        })

        # Step 3-N: Setup + Action + Verification based on AC content
        ac_lower = ac_bullet.lower()

        # Pattern detection for specific scenarios
        if ('line' in ac_lower and 'color' in ac_lower) or 'color picker' in ac_lower:
            # Line color scenario
            steps.append({"action": "Draw a line on the Canvas.", "expected": ""})
            steps.append({"action": "Select the line.", "expected": ""})
            steps.append({"action": "Open the Properties Panel (line style controls).", "expected": ""})
            steps.append({"action": "Click the color picker control.", "expected": ""})
            steps.append({"action": "Select a different color (e.g., red).", "expected": ""})
            steps.append({
                "action": "Verify the line color updates immediately on the Canvas.",
                "expected": "Line displays in the newly selected color."
            })

        elif ('line' in ac_lower and 'thickness' in ac_lower) or 'numeric input' in ac_lower or 'dropdown' in ac_lower:
            # Line thickness scenario
            steps.append({"action": "Draw a line on the Canvas.", "expected": ""})
            steps.append({"action": "Select the line.", "expected": ""})
            steps.append({"action": "Open the Properties Panel (line style controls).", "expected": ""})
            steps.append({"action": "Change the line thickness value (via numeric input / dropdown).", "expected": ""})
            steps.append({
                "action": "Verify the line thickness updates immediately on the Canvas.",
                "expected": "Line displays with the new thickness value."
            })

        elif ('line type' in ac_lower) or ('solid' in ac_lower and 'dashed' in ac_lower) or 'dotted' in ac_lower:
            # Line type (solid/dashed/dotted) scenario
            steps.append({"action": "Draw a line on the Canvas.", "expected": ""})
            steps.append({"action": "Select the line.", "expected": ""})
            steps.append({"action": "Open the Properties Panel (line style controls).", "expected": ""})
            steps.append({"action": "Select a different line type (e.g., Dashed).", "expected": ""})
            steps.append({
                "action": "Verify the line type updates immediately on the Canvas.",
                "expected": "Line displays with the selected line type (dashed pattern visible)."
            })

        elif 'visual update' in ac_lower and 'immediately' in ac_lower:
            # Immediate visual update scenario
            steps.append({"action": "Draw a shape on the Canvas.", "expected": ""})
            steps.append({"action": "Select the shape and change a property (color, size, style).", "expected": ""})
            steps.append({
                "action": "Verify the change applies immediately without delay / refresh.",
                "expected": "Visual change is applied instantly on the Canvas with no lag."
            })

        elif 'accessibility' in ac_lower and 'compliance' in ac_lower:
            # Accessibility compliance scenario
            steps.append({"action": "Open the feature controls (Properties Panel / menu).", "expected": ""})
            steps.append({"action": "Navigate using keyboard only (Tab, Arrow keys, Enter).", "expected": ""})
            steps.append({
                "action": "Verify all controls are keyboard-accessible with visible focus indicators.",
                "expected": "All controls can be reached via keyboard; focus indicators are visible."
            })
            steps.append({"action": "Run accessibility validation tool (e.g., Accessibility Insights).", "expected": ""})
            steps.append({
                "action": "Verify no critical accessibility issues are reported.",
                "expected": "Scan passes; controls have correct roles, labels, and keyboard support."
            })

        elif 'bring' in ac_lower or 'send' in ac_lower or 'z-order' in ac_lower or 'stacking' in ac_lower:
            # Z-order/stacking scenario
            steps.append({
                "action": "Draw three overlapping shapes on the Canvas (circle, rectangle, triangle).",
                "expected": ""
            })
            steps.append({
                "action": "Select the middle shape (rectangle).",
                "expected": ""
            })
            steps.append({
                "action": "Navigate to Tools Menu → Draw Order.",
                "expected": ""
            })

            if 'front' in ac_lower:
                steps.append({
                    "action": "Click 'Bring to Front'.",
                    "expected": ""
                })
                steps.append({
                    "action": "Verify the selected rectangle is now the top-most object on the Canvas.",
                    "expected": "Rectangle appears above all other shapes and occludes them when overlapping."
                })
            elif 'back' in ac_lower:
                steps.append({
                    "action": "Click 'Send to Back'.",
                    "expected": ""
                })
                steps.append({
                    "action": "Verify the selected rectangle is now the bottom-most object on the Canvas.",
                    "expected": "Rectangle appears below all other shapes and is occluded by them when overlapping."
                })
            elif 'above' in ac_lower:
                steps.append({
                    "action": "Click 'Bring Above Objects'.",
                    "expected": ""
                })
                steps.append({
                    "action": "Verify the selected rectangle moved one level higher in stacking order.",
                    "expected": "Rectangle is now above the shape it was previously below, but still below any shapes that were already above it."
                })
            elif 'under' in ac_lower:
                steps.append({
                    "action": "Click 'Send Under Objects'.",
                    "expected": ""
                })
                steps.append({
                    "action": "Verify the selected rectangle moved one level lower in stacking order.",
                    "expected": "Rectangle is now below the shape it was previously above, but still above any shapes that were already below it."
                })

        elif 'diameter' in ac_lower:
            # Diameter measurement scenario
            if 'ellipse' in ac_lower and 'shows' in ac_lower:
                steps.append({
                    "action": "Draw an ellipse on the Canvas.",
                    "expected": ""
                })
                steps.append({
                    "action": "Select the ellipse.",
                    "expected": ""
                })
                steps.append({
                    "action": "Open the Dimensions Panel.",
                    "expected": ""
                })
                steps.append({
                    "action": "Verify the Diameter measurement is visible and displays the ellipse's diameter value.",
                    "expected": "Diameter field shows in the Dimensions Panel with the correct numeric value."
                })
            else:
                steps.append({
                    "action": "Draw a rectangle on the Canvas.",
                    "expected": ""
                })
                steps.append({
                    "action": "Select the rectangle.",
                    "expected": ""
                })
                steps.append({
                    "action": "Open the Dimensions Panel.",
                    "expected": ""
                })
                steps.append({
                    "action": "Verify the Diameter measurement is not displayed.",
                    "expected": "Diameter field is hidden or not present in the Dimensions Panel for non-ellipse shapes."
                })

        else:
            # Generic scenario - build from AC text
            steps.append({
                "action": f"Perform action as described in AC: {ac_bullet[:60]}...",
                "expected": ""
            })
            steps.append({
                "action": "Verify the expected outcome occurs.",
                "expected": "Behavior matches the acceptance criteria."
            })

        # Final step: Close
        steps.append({
            "action": "Close/Exit the QuickDraw application",
            "expected": ""
        })

        return steps

    def _build_objective(self, ac_bullet: str) -> str:
        """Build objective from AC bullet."""
        # Clean up AC text
        ac_lower = ac_bullet.lower().strip()
        ac_lower = re.sub(r'^(user can|user should|system must|the system)', '', ac_lower).strip()

        return ac_lower

    def _generate_boundary_scenario(self, base_ac: str, boundary_type: str) -> str:
        """Generate boundary test scenario name."""
        if boundary_type == 'at_top':
            return "No Change When Object Already At Top"
        elif boundary_type == 'at_bottom':
            return "No Change When Object Already At Bottom"
        elif boundary_type == 'no_selection':
            return "Action Disabled Without Selection"
        elif boundary_type == 'wrong_type':
            return "Action Disabled For Unsupported Object Type"
        else:
            return f"Boundary Case {boundary_type}"

    def _build_boundary_steps(self, base_ac: str, boundary_type: str, area: str) -> List[Dict]:
        """Build boundary test steps."""
        steps = []

        steps.append({"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""})
        steps.append({"action": "Launch the ENV QuickDraw application.", "expected": ""})

        if boundary_type == 'at_top':
            steps.append({"action": "Draw three overlapping shapes on the Canvas.", "expected": ""})
            steps.append({"action": "Select the top-most shape.", "expected": ""})
            steps.append({"action": "Navigate to Tools Menu → Draw Order → Bring to Front.", "expected": ""})
            steps.append({
                "action": "Verify the shape remains at the top with no change in stacking order.",
                "expected": "Shape stays at the top; no visual change occurs because it is already the highest object."
            })
        elif boundary_type == 'at_bottom':
            steps.append({"action": "Draw three overlapping shapes on the Canvas.", "expected": ""})
            steps.append({"action": "Select the bottom-most shape.", "expected": ""})
            steps.append({"action": "Navigate to Tools Menu → Draw Order → Send to Back.", "expected": ""})
            steps.append({
                "action": "Verify the shape remains at the bottom with no change in stacking order.",
                "expected": "Shape stays at the bottom; no visual change occurs because it is already the lowest object."
            })
        elif boundary_type == 'no_selection':
            steps.append({"action": "Draw a shape on the Canvas but do not select it.", "expected": ""})
            steps.append({"action": "Navigate to Tools Menu → Draw Order.", "expected": ""})
            steps.append({
                "action": "Verify all Draw Order actions are disabled or inactive.",
                "expected": "All actions (Bring to Front, Send to Back, etc.) are grayed out or non-clickable."
            })

        steps.append({"action": "Close/Exit the QuickDraw application", "expected": ""})

        return steps

    def _build_boundary_objective(self, base_ac: str, boundary_type: str) -> str:
        """Build boundary test objective."""
        if boundary_type == 'at_top':
            return "actions have no effect when the object is already at the highest z-order"
        elif boundary_type == 'at_bottom':
            return "actions have no effect when the object is already at the lowest z-order"
        elif boundary_type == 'no_selection':
            return "actions are disabled when no object is selected"
        else:
            return f"boundary condition '{boundary_type}' is handled correctly"

    def _get_qa_scenario(self, qa_type: str) -> str:
        """Get QA test scenario name."""
        scenarios = {
            'multi_select': "Multi Selection Preserves Relative Order",
            'mixed_types': "Mixed Object Types Handled Correctly",
            'undo_redo': "Undo Redo Reverses And Reapplies Changes",
            'persistence': "Changes Persist After Save And Reopen",
            'repeated': "Repeated Actions Remain Stable",
            'immediate': "Changes Apply Immediately Without Side Effects"
        }
        return scenarios.get(qa_type, qa_type.replace('_', ' ').title())

    def _build_qa_steps(self, qa_type: str, area: str, context: Dict) -> List[Dict]:
        """Build QA test steps - feature-agnostic."""
        steps = []

        steps.append({"action": "PRE-REQ: ENV QuickDraw application is installed", "expected": ""})
        steps.append({"action": "Launch the ENV QuickDraw application.", "expected": ""})

        if qa_type == 'undo_redo':
            steps.append({"action": "Draw a shape on the Canvas.", "expected": ""})
            steps.append({"action": f"Apply a {self.feature_name} action (e.g., change color / thickness / style).", "expected": ""})
            steps.append({"action": "Press Ctrl+Z (or Edit → Undo).", "expected": ""})
            steps.append({
                "action": "Verify the change is undone and the shape returns to its previous state.",
                "expected": "Shape reverts to its original appearance before the change."
            })
            steps.append({"action": "Press Ctrl+Y (or Edit → Redo).", "expected": ""})
            steps.append({
                "action": f"Verify the {self.feature_name} action is reapplied.",
                "expected": "Shape displays with the reapplied change."
            })
        elif qa_type == 'persistence':
            steps.append({"action": "Draw a shape on the Canvas.", "expected": ""})
            steps.append({"action": f"Apply a {self.feature_name} action (e.g., change color / thickness / style).", "expected": ""})
            steps.append({"action": "Save the document (File → Save).", "expected": ""})
            steps.append({"action": "Close the application.", "expected": ""})
            steps.append({"action": "Reopen the saved document.", "expected": ""})
            steps.append({
                "action": f"Verify the {self.feature_name} changes are preserved.",
                "expected": "Shape retains all applied changes after reopening."
            })
        elif qa_type == 'multi_select':
            steps.append({"action": "Draw multiple shapes on the Canvas.", "expected": ""})
            steps.append({"action": "Multi-select two shapes (Ctrl+Click / Shift+Click).", "expected": ""})
            steps.append({"action": f"Apply a {self.feature_name} action to the selection.", "expected": ""})
            steps.append({
                "action": "Verify the action applies to all selected shapes.",
                "expected": "All selected shapes reflect the applied change."
            })
        else:
            steps.append({"action": f"Perform {qa_type.replace('_', ' ')} test scenario for {self.feature_name}.", "expected": ""})
            steps.append({"action": "Verify expected outcome.", "expected": "Behavior is correct."})

        steps.append({"action": "Close/Exit the QuickDraw application", "expected": ""})

        return steps

    def _build_qa_objective(self, qa_type: str) -> str:
        """Build QA test objective."""
        objectives = {
            'undo_redo': "undo and redo operations correctly reverse and reapply z-order changes",
            'persistence': "z-order changes persist after saving and reopening the document",
            'multi_select': "multi-selected objects maintain their relative order when reordered together",
            'mixed_types': "z-order operations work across different object types",
            'repeated': "repeated z-order operations remain stable without degradation",
            'immediate': "z-order changes apply immediately without unintended side effects"
        }
        return objectives.get(qa_type, f"{qa_type.replace('_', ' ')} functions correctly")

    def _build_accessibility_steps(self, device: str, area: str) -> List[Dict]:
        """Build device-specific accessibility test steps."""
        steps = []

        # Device-specific PRE-REQ
        if device == "Windows 11":
            steps.append({"action": "PRE-REQ: Accessibility Insights for Windows tool is installed", "expected": ""})
        elif device == "iPad":
            steps.append({"action": "PRE-REQ: Apple built-in accessibility tools are available and enabled (e.g., VoiceOver)", "expected": ""})
        elif device == "Android Tablet":
            steps.append({"action": "PRE-REQ: Accessibility Scanner (Google) Free tool is installed", "expected": ""})

        steps.append({"action": "Launch the ENV QuickDraw application.", "expected": ""})
        steps.append({"action": f"Navigate to the {self.feature_name} controls using keyboard only (Tab/Arrow keys).", "expected": ""})
        steps.append({
            "action": "Verify all controls are reachable and have visible focus indicators.",
            "expected": "Focus indicator is visible on each control; tab order is logical."
        })

        if device == "Windows 11":
            steps.append({"action": "Run Accessibility Insights automated scan.", "expected": ""})
            steps.append({
                "action": "Verify no critical accessibility issues are reported.",
                "expected": "Scan passes with no blocking issues; controls have correct roles and accessible names."
            })
        elif device in ["iPad", "Android Tablet"]:
            tool_name = "VoiceOver" if device == "iPad" else "TalkBack/Accessibility Scanner"
            steps.append({"action": f"Enable {tool_name}.", "expected": ""})
            steps.append({
                "action": f"Navigate through {self.feature_name} controls using gestures.",
                "expected": f"{tool_name} announces each control with a meaningful label and correct role."
            })

        steps.append({"action": "Close/Exit the QuickDraw application", "expected": ""})

        return steps
