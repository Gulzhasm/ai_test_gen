"""
Rule-Driven Test Case Builders.

Each builder maps to a specific rule section and generates test cases
based only on Ruleset signals, never from raw text or heuristics.
"""
from typing import List, Dict, Optional, Tuple
from core.domain.ruleset import Ruleset, EvidenceBullet
import re
import config


class BaseBuilder:
    """Base class for all test builders."""
    
    def __init__(self, ruleset: Ruleset, story_id: int, feature_name: str):
        self.ruleset = ruleset
        self.story_id = story_id
        self.feature_name = feature_name
        self.test_id_counter = 5  # Start at 005 after AC1
    
    def get_next_test_id(self) -> str:
        """Get next test ID in sequence."""
        test_id = f"{self.story_id}-{self.test_id_counter:03d}"
        self.test_id_counter += 5
        return test_id
    
    def _add_mandatory_steps(self, steps: List[Dict]) -> List[Dict]:
        """Add mandatory PRE-REQ and Close steps."""
        # Check if PRE-REQ already exists
        has_prereq = any('PRE-REQ' in step.get('action', '').upper() for step in steps)
        if not has_prereq:
            steps.insert(0, {
                "action": "PRE-REQ: ENV QuickDraw application is installed.",
                "expected": ""
            })
        
        # Check if Close already exists
        has_close = any('close' in step.get('action', '').lower() or 'exit' in step.get('action', '').lower() for step in steps)
        if not has_close:
            steps.append({
                "action": "Close/Exit the QuickDraw application.",
                "expected": ""
            })
        
        return steps
    
    def _clean_forbidden_words(self, text: str) -> str:
        """Remove forbidden words from text."""
        if not text:
            return text
        
        cleaned = text
        for forbidden in config.FORBIDDEN_WORDS:
            pattern = re.compile(re.escape(forbidden), re.IGNORECASE)
            cleaned = pattern.sub('', cleaned)
        
        # Remove "or" phrases
        cleaned = re.sub(r'\s+or\s+\w+', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\b(or)\b', '', cleaned, flags=re.IGNORECASE)
        
        # Clean up extra spaces
        cleaned = ' '.join(cleaned.split())
        return cleaned.strip()


class AvailabilityBuilder(BaseBuilder):
    """Builder for AC1 availability/entry point tests."""
    
    def build(self, ac_bullet: EvidenceBullet) -> Optional[Dict]:
        """
        Build availability test case.
        Only generates if ruleset.has_signal('availability') is True.
        """
        if not self.ruleset.has_signal('availability'):
            return None
        
        test_id = f"{self.story_id}-AC1"
        
        # Extract entry point from AC
        entry_point = None
        if self.ruleset.entry_points:
            entry_point = list(self.ruleset.entry_points)[0]
        else:
            # Try to extract from AC text
            match = re.search(r'from (?:the )?([A-Z][a-z]+ (?:menu|panel|toolbar))', ac_bullet.text, re.IGNORECASE)
            if match:
                entry_point = match.group(1)
        
        # Generate title
        if entry_point:
            title = f"{self.feature_name} / {entry_point} / Available and Accessible"
        else:
            title = f"{self.feature_name} / Toolbar and Edit Menu / Available and Accessible"
        
        # Generate steps
        steps = []
        
        # Launch step
        steps.append({
            "action": "Launch ENV QuickDraw application.",
            "expected": ""
        })
        
        # Navigate to entry point
        if entry_point:
            if 'menu' in entry_point.lower():
                steps.append({
                    "action": f"Open {entry_point}.",
                    "expected": ""
                })
            elif 'panel' in entry_point.lower():
                steps.append({
                    "action": f"Open {entry_point}.",
                    "expected": ""
                })
        else:
            steps.append({
                "action": "Open Edit menu.",
                "expected": ""
            })
        
        # Verify availability
        verify_action = f"Verify that {self.feature_name} is available and can be activated"
        if entry_point:
            verify_action += f" from {entry_point}."
        else:
            verify_action += " from the Edit menu."
        
        steps.append({
            "action": verify_action,
            "expected": f"{self.feature_name} is visible and can be activated."
        })
        
        # Add mandatory steps
        steps = self._add_mandatory_steps(steps)
        
        # Generate objective
        objective = f"Objective: Verify that {self.feature_name} is available and accessible"
        if entry_point:
            objective += f" from {entry_point}."
        else:
            objective += " from the Edit menu."
        
        return {
            'id': test_id,
            'title': f"{test_id}: {title}",
            'steps': steps,
            'objective': objective,
            'source_ac_id': ac_bullet.id,
            'evidence_refs': self.ruleset.get_evidence_refs('availability')
        }


class ActionBuilder(BaseBuilder):
    """Builder for action-based tests (add, remove, enable, disable, etc.)."""
    
    def build(self, ac_bullet: EvidenceBullet) -> Optional[Dict]:
        """
        Build action test case.
        Only generates if ruleset.has_signal('action') is True.
        """
        if not self.ruleset.has_signal('action'):
            return None
        
        test_id = self.get_next_test_id()
        
        # Extract action type
        action_type = self._extract_action_type(ac_bullet.text)
        
        # Generate title
        title = self._generate_title(ac_bullet.text, action_type)
        
        # Generate steps
        steps = []
        
        # Launch
        steps.append({
            "action": "Launch ENV QuickDraw application.",
            "expected": ""
        })
        
        # Object setup if required
        if self.ruleset.requires_selection:
            steps.append({
                "action": "Draw a shape (e.g., rectangle, triangle, circle, polygon) on the Canvas.",
                "expected": ""
            })
            steps.append({
                "action": "Select the drawn object.",
                "expected": ""
            })
        
        # Perform action
        action_step = self._generate_action_step(ac_bullet.text, action_type)
        if action_step:
            steps.append(action_step)
        
        # Verify result
        verify_step = self._generate_verify_step(ac_bullet.text, action_type)
        if verify_step:
            steps.append(verify_step)
        
        # Add mandatory steps
        steps = self._add_mandatory_steps(steps)
        
        # Generate objective
        objective = self._generate_objective(ac_bullet.text, action_type)
        
        return {
            'id': test_id,
            'title': f"{test_id}: {title}",
            'steps': steps,
            'objective': objective,
            'source_ac_id': ac_bullet.id,
            'evidence_refs': self.ruleset.get_evidence_refs('action')
        }
    
    def _extract_action_type(self, text: str) -> str:
        """Extract action type from AC text."""
        text_lower = text.lower()
        if 'add' in text_lower:
            return 'add'
        elif 'remove' in text_lower:
            return 'remove'
        elif 'enable' in text_lower:
            return 'enable'
        elif 'disable' in text_lower:
            return 'disable'
        elif 'toggle' in text_lower:
            return 'toggle'
        elif 'activate' in text_lower:
            return 'activate'
        else:
            return 'action'
    
    def _generate_title(self, text: str, action_type: str) -> str:
        """Generate test case title."""
        # Extract area/scenario from text
        area = self._extract_area(text)
        scenario = self._extract_scenario(text, action_type)
        
        return f"{self.feature_name} / {area} / {scenario}"
    
    def _extract_area(self, text: str) -> str:
        """Extract UI area from text."""
        # Try to find area mentions
        area_patterns = [
            r'in (?:the )?([A-Z][a-z]+ (?:menu|panel|toolbar))',
            r'from (?:the )?([A-Z][a-z]+ (?:menu|panel|toolbar))',
        ]
        for pattern in area_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return "Toolbar"
    
    def _extract_scenario(self, text: str, action_type: str) -> str:
        """Extract scenario from text."""
        # Simplified scenario extraction
        if 'measurement' in text.lower():
            return f"{action_type.capitalize()} Measurement"
        elif 'dimension' in text.lower():
            return f"{action_type.capitalize()} Dimension"
        else:
            return f"{action_type.capitalize()} Feature"
    
    def _generate_action_step(self, text: str, action_type: str) -> Dict:
        """Generate action step."""
        # Extract what to act on
        if 'dimension' in text.lower():
            feature = "Dimensions – Diameter"
        elif 'measurement' in text.lower():
            feature = "Measurement"
        else:
            feature = self.feature_name
        
        action_text = f"{action_type.capitalize()} {feature}."
        
        return {
            "action": action_text,
            "expected": ""
        }
    
    def _generate_verify_step(self, text: str, action_type: str) -> Dict:
        """Generate verification step."""
        verify_text = f"Verify that {self.feature_name} is {action_type}d successfully."
        
        return {
            "action": verify_text,
            "expected": f"{self.feature_name} is {action_type}d and behaves as expected."
        }
    
    def _generate_objective(self, text: str, action_type: str) -> str:
        """Generate objective."""
        return f"Objective: Verify that {self.feature_name} can be {action_type}d correctly."


class UndoRedoBuilder(BaseBuilder):
    """Builder for undo/redo tests."""
    
    def build(self, ac_bullet: EvidenceBullet) -> Optional[Dict]:
        """
        Build undo/redo test case.
        Only generates if ruleset.has_signal('undo_redo') is True.
        """
        if not self.ruleset.has_signal('undo_redo'):
            return None
        
        test_id = self.get_next_test_id()
        
        # Generate title
        title = f"{self.feature_name} / Undo Redo / Undo Redo Functionality"
        
        # Generate steps
        steps = []
        
        # Launch
        steps.append({
            "action": "Launch ENV QuickDraw application.",
            "expected": ""
        })
        
        # Object setup
        if self.ruleset.requires_selection:
            steps.append({
                "action": "Draw a shape (e.g., rectangle, triangle, circle, polygon) on the Canvas.",
                "expected": ""
            })
            steps.append({
                "action": "Select the drawn object.",
                "expected": ""
            })
        
        # Perform action (extract from AC)
        action_step = self._extract_action_from_ac(ac_bullet.text)
        if action_step:
            steps.append(action_step)
        
        # Verify post-action
        steps.append({
            "action": f"Verify that {self.feature_name} action is applied.",
            "expected": f"{self.feature_name} action is applied correctly."
        })
        
        # Undo
        steps.append({
            "action": "Execute Undo command from Edit menu or toolbar.",
            "expected": "Previous state is restored."
        })
        
        # Verify undo
        steps.append({
            "action": f"Verify that {self.feature_name} action is undone.",
            "expected": f"{self.feature_name} action is undone and previous state is restored."
        })
        
        # Redo
        steps.append({
            "action": "Execute Redo command from Edit menu or toolbar.",
            "expected": "Action is reapplied."
        })
        
        # Verify redo
        steps.append({
            "action": f"Verify that {self.feature_name} action is redone.",
            "expected": f"{self.feature_name} action is redone and state matches post-action."
        })
        
        # Add mandatory steps
        steps = self._add_mandatory_steps(steps)
        
        # Generate objective
        objective = f"Objective: Verify that {self.feature_name} actions can be undone and redone correctly."
        
        return {
            'id': test_id,
            'title': f"{test_id}: {title}",
            'steps': steps,
            'objective': objective,
            'source_ac_id': ac_bullet.id,
            'evidence_refs': self.ruleset.get_evidence_refs('undo_redo')
        }
    
    def _extract_action_from_ac(self, text: str) -> Optional[Dict]:
        """Extract the action to undo/redo from AC text."""
        # Simplified extraction - in real implementation, this would be more sophisticated
        if 'move' in text.lower():
            return {
                "action": "Move the selected object using drag operation.",
                "expected": ""
            }
        elif 'rotate' in text.lower():
            return {
                "action": "Rotate the selected object using rotation handle.",
                "expected": ""
            }
        else:
            return {
                "action": f"Perform {self.feature_name} action on the selected object.",
                "expected": ""
            }


class AccessibilityBuilder(BaseBuilder):
    """Builder for accessibility tests."""
    
    def build(self, ac_bullet: EvidenceBullet) -> List[Dict]:
        """
        Build accessibility test cases.
        Only generates if ruleset.has_signal('accessibility') is True.
        Returns list because we may need platform-specific tests.
        """
        if not self.ruleset.has_signal('accessibility'):
            return []
        
        test_cases = []
        
        # Determine platforms
        platforms = list(self.ruleset.platforms) if self.ruleset.platforms else ['Windows 11']
        
        for platform in platforms:
            test_id = self.get_next_test_id()
            
            # Generate title
            title = self._generate_title(platform)
            
            # Generate steps
            steps = self._generate_steps(platform, ac_bullet.text)
            
            # Add mandatory steps
            steps = self._add_mandatory_steps(steps)
            
            # Generate objective
            objective = self._generate_objective(platform)
            
            test_cases.append({
                'id': test_id,
                'title': f"{test_id}: {title}",
                'steps': steps,
                'objective': objective,
                'source_ac_id': ac_bullet.id,
                'evidence_refs': self.ruleset.get_evidence_refs('accessibility'),
                'platform': platform
            })
        
        return test_cases
    
    def _generate_title(self, platform: str) -> str:
        """Generate accessibility test title."""
        if platform == 'Windows 11':
            return f"{self.feature_name} / Accessibility / Keyboard Navigation and Focus Indicators (Windows 11)"
        elif platform == 'iPad':
            return f"{self.feature_name} / Accessibility / Touch Access with VoiceOver (iPad)"
        elif platform == 'Android Tablet':
            return f"{self.feature_name} / Accessibility / Touch Access with TalkBack (Android Tablet)"
        else:
            return f"{self.feature_name} / Accessibility / Accessibility Compliance ({platform})"
    
    def _generate_steps(self, platform: str, ac_text: str) -> List[Dict]:
        """Generate accessibility test steps."""
        steps = []
        
        # Launch
        steps.append({
            "action": "Launch ENV QuickDraw application.",
            "expected": ""
        })
        
        # Platform-specific PRE-REQ
        if platform == 'Windows 11':
            steps.append({
                "action": "PRE-REQ: Accessibility Insights for Windows is installed and running.",
                "expected": ""
            })
        elif platform == 'iPad':
            steps.append({
                "action": "PRE-REQ: VoiceOver is enabled on iPad.",
                "expected": ""
            })
        elif platform == 'Android Tablet':
            steps.append({
                "action": "PRE-REQ: TalkBack is enabled on Android Tablet.",
                "expected": ""
            })
        
        # Platform-specific navigation
        if platform == 'Windows 11':
            steps.append({
                "action": f"Navigate to {self.feature_name} using keyboard (Tab, Arrow keys).",
                "expected": ""
            })
            steps.append({
                "action": f"Verify that {self.feature_name} receives keyboard focus.",
                "expected": "Focus indicator is visible and keyboard focus is established."
            })
            steps.append({
                "action": f"Verify that {self.feature_name} has accessible labels and roles.",
                "expected": "Labels and roles are exposed correctly to assistive technologies."
            })
        elif platform in ['iPad', 'Android Tablet']:
            # NO keyboard navigation for tablets
            steps.append({
                "action": f"Navigate to {self.feature_name} using touch gestures.",
                "expected": ""
            })
            steps.append({
                "action": f"Verify that {self.feature_name} is accessible via touch and screen reader.",
                "expected": "Feature is accessible via touch and screen reader announces it correctly."
            })
        
        return steps
    
    def _generate_objective(self, platform: str) -> str:
        """Generate accessibility objective."""
        if platform == 'Windows 11':
            return f"Objective: Verify that {self.feature_name} is accessible via keyboard navigation with visible focus indicators and proper labels and roles."
        elif platform == 'iPad':
            return f"Objective: Verify that {self.feature_name} is accessible via touch and VoiceOver on iPad."
        elif platform == 'Android Tablet':
            return f"Objective: Verify that {self.feature_name} is accessible via touch and TalkBack on Android Tablet."
        else:
            return f"Objective: Verify that {self.feature_name} meets accessibility requirements for {platform}."


class BoundaryBuilder(BaseBuilder):
    """Builder for boundary/constraint tests."""
    
    def build(self, ac_bullet: EvidenceBullet) -> Optional[Dict]:
        """
        Build boundary test case.
        Only generates if ruleset.has_signal('constraint') is True.
        """
        if not self.ruleset.has_signal('constraint'):
            return None
        
        test_id = self.get_next_test_id()
        
        # Extract boundary type
        boundary_type = self._extract_boundary_type(ac_bullet.text)
        
        # Generate title
        title = f"{self.feature_name} / Boundary / {boundary_type}"
        
        # Generate steps
        steps = []
        
        # Launch
        steps.append({
            "action": "Launch ENV QuickDraw application.",
            "expected": ""
        })
        
        # Object setup
        if self.ruleset.requires_selection:
            steps.append({
                "action": "Draw a shape (e.g., rectangle, triangle, circle, polygon) on the Canvas.",
                "expected": ""
            })
            steps.append({
                "action": "Select the drawn object.",
                "expected": ""
            })
        
        # Boundary test step
        boundary_step = self._generate_boundary_step(ac_bullet.text, boundary_type)
        if boundary_step:
            steps.append(boundary_step)
        
        # Verify boundary behavior
        verify_step = self._generate_boundary_verify_step(ac_bullet.text, boundary_type)
        if verify_step:
            steps.append(verify_step)
        
        # Add mandatory steps
        steps = self._add_mandatory_steps(steps)
        
        # Generate objective
        objective = self._generate_boundary_objective(ac_bullet.text, boundary_type)
        
        return {
            'id': test_id,
            'title': f"{test_id}: {title}",
            'steps': steps,
            'objective': objective,
            'source_ac_id': ac_bullet.id,
            'evidence_refs': self.ruleset.get_evidence_refs('constraint')
        }
    
    def _extract_boundary_type(self, text: str) -> str:
        """Extract boundary type from AC text."""
        text_lower = text.lower()
        if '360' in text_lower or 'degree' in text_lower:
            return "Boundary Position Near 360 Degrees"
        elif '0' in text_lower and 'degree' in text_lower:
            return "Boundary Position at 0 Degrees"
        elif 'wrap' in text_lower or 'wrap-around' in text_lower:
            return "Wrap-Around Behavior"
        else:
            return "Boundary Constraint"
    
    def _generate_boundary_step(self, text: str, boundary_type: str) -> Optional[Dict]:
        """Generate boundary test step."""
        if '360' in boundary_type.lower():
            return {
                "action": "Rotate the selected object to near 360 degrees.",
                "expected": ""
            }
        elif 'wrap' in boundary_type.lower():
            return {
                "action": "Rotate the selected object beyond 360 degrees.",
                "expected": ""
            }
        else:
            return {
                "action": f"Perform {self.feature_name} action at boundary condition.",
                "expected": ""
            }
    
    def _generate_boundary_verify_step(self, text: str, boundary_type: str) -> Dict:
        """Generate boundary verification step."""
        if 'wrap' in boundary_type.lower():
            return {
                "action": "Verify that rotation wraps around to 0 degrees.",
                "expected": "Rotation wraps around correctly without errors."
            }
        else:
            return {
                "action": f"Verify that {self.feature_name} handles boundary condition correctly.",
                "expected": f"{self.feature_name} handles boundary condition without errors."
            }
    
    def _generate_boundary_objective(self, text: str, boundary_type: str) -> str:
        """Generate boundary objective."""
        if 'wrap' in boundary_type.lower():
            return f"Objective: Verify that {self.feature_name} wraps around correctly at boundary positions."
        else:
            return f"Objective: Verify that {self.feature_name} handles boundary conditions correctly."


class StateNegativeBuilder(BaseBuilder):
    """Builder for negative state tests (no selection, empty canvas, etc.)."""
    
    def build(self, ac_bullet: EvidenceBullet) -> Optional[Dict]:
        """
        Build negative state test case.
        Only generates if ruleset.has_signal('negative') is True.
        """
        if not self.ruleset.has_signal('negative'):
            return None
        
        # Check which negative condition
        negative_type = None
        if self.ruleset.has_signal('negative', 'no_selection'):
            negative_type = 'no_selection'
        elif self.ruleset.has_signal('negative', 'empty_canvas'):
            negative_type = 'empty_canvas'
        else:
            return None
        
        test_id = self.get_next_test_id()
        
        # Generate title
        if negative_type == 'no_selection':
            title = f"{self.feature_name} / Negative / No Selection State"
        else:
            title = f"{self.feature_name} / Negative / Empty Canvas State"
        
        # Generate steps
        steps = []
        
        # Launch
        steps.append({
            "action": "Launch ENV QuickDraw application.",
            "expected": ""
        })
        
        # Negative condition setup
        if negative_type == 'no_selection':
            steps.append({
                "action": "Ensure no objects are selected on the Canvas.",
                "expected": ""
            })
        elif negative_type == 'empty_canvas':
            steps.append({
                "action": "Ensure Canvas is empty (no objects drawn).",
                "expected": ""
            })
        
        # Attempt action
        steps.append({
            "action": f"Attempt to activate {self.feature_name}.",
            "expected": ""
        })
        
        # Verify negative behavior
        if negative_type == 'no_selection':
            steps.append({
                "action": f"Verify that {self.feature_name} is disabled or not available.",
                "expected": f"{self.feature_name} is disabled when no object is selected."
            })
        else:
            steps.append({
                "action": f"Verify that {self.feature_name} is disabled or not available.",
                "expected": f"{self.feature_name} is disabled when canvas is empty."
            })
        
        # Add mandatory steps
        steps = self._add_mandatory_steps(steps)
        
        # Generate objective
        if negative_type == 'no_selection':
            objective = f"Objective: Verify that {self.feature_name} is disabled when no object is selected."
        else:
            objective = f"Objective: Verify that {self.feature_name} is disabled when canvas is empty."
        
        return {
            'id': test_id,
            'title': f"{test_id}: {title}",
            'steps': steps,
            'objective': objective,
            'source_ac_id': ac_bullet.id,
            'evidence_refs': [ref for ref in self.ruleset.get_evidence_refs('negative') if negative_type in ref]
        }


class VisibilityBuilder(BaseBuilder):
    """Builder for visibility tests."""
    
    def build(self, ac_bullet: EvidenceBullet) -> Optional[Dict]:
        """
        Build visibility test case.
        Only generates if ruleset.has_signal('visibility') is True.
        """
        if not self.ruleset.has_signal('visibility'):
            return None
        
        test_id = self.get_next_test_id()
        
        # Generate title
        title = f"{self.feature_name} / Visibility / Element Visibility"
        
        # Generate steps
        steps = []
        
        # Launch
        steps.append({
            "action": "Launch ENV QuickDraw application.",
            "expected": ""
        })
        
        # Navigate to feature
        if self.ruleset.entry_points:
            entry_point = list(self.ruleset.entry_points)[0]
            steps.append({
                "action": f"Open {entry_point}.",
                "expected": ""
            })
        
        # Verify visibility
        steps.append({
            "action": f"Verify that {self.feature_name} is visible.",
            "expected": f"{self.feature_name} is displayed correctly."
        })
        
        # Add mandatory steps
        steps = self._add_mandatory_steps(steps)
        
        # Generate objective
        objective = f"Objective: Verify that {self.feature_name} is visible and displayed correctly."
        
        return {
            'id': test_id,
            'title': f"{test_id}: {title}",
            'steps': steps,
            'objective': objective,
            'source_ac_id': ac_bullet.id,
            'evidence_refs': self.ruleset.get_evidence_refs('visibility')
        }
