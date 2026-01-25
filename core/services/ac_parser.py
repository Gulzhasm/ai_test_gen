"""
AC Intelligence Module

Intelligently parses acceptance criteria to extract:
- Actions (what the user does)
- Targets (what object/control is affected)
- Outcomes (what should happen)
- Boundary cases (edge conditions to test)

This enables automatic generation of comprehensive, balanced test cases.
"""

from typing import Dict, List, Optional, Tuple
import re
from dataclasses import dataclass


@dataclass
class ACSemantics:
    """Semantic structure extracted from AC bullet."""
    action: str  # e.g., "Bring to Front", "Enable", "Disable"
    target: str  # e.g., "selected object", "diameter measurement", "Draw Order actions"
    outcome: str  # e.g., "moves to highest z-order", "becomes visible", "are enabled"
    conditions: List[str]  # e.g., ["when object is selected", "for ellipse only"]
    boundary_cases: List[str]  # e.g., ["at top", "at bottom", "no selection"]
    negation: bool  # True if this is a negative scenario (disabled, hidden, etc.)
    
    def get_balanced_scenario(self) -> str:
        """Generate balanced scenario name from semantics."""
        # Format: Action + Target + Outcome
        # Example: "Bring To Front Moves Object To Highest Z Order"
        
        # Capitalize each word
        action_cap = ' '.join(word.capitalize() for word in self.action.split())
        outcome_cap = ' '.join(word.capitalize() for word in self.outcome.split())
        
        if self.negation:
            # For negative scenarios: "Actions Disabled Without Selection"
            return f"{action_cap} {outcome_cap}"
        else:
            # For positive scenarios: "Bring To Front Moves Object To Highest Z Order"
            return f"{action_cap} {outcome_cap}"


class ACParser:
    """Intelligent AC parser that extracts semantic structure."""
    
    # Action patterns
    ACTION_PATTERNS = [
        # Transformation actions
        (r'(bring|move|send)\s+(?:to\s+)?(front|back|above|under)', r'\1 to \2'),
        (r'(bring)\s+(above\s+objects?)', r'\1 \2'),
        (r'(send)\s+(under\s+objects?)', r'\1 \2'),
        (r'(rotate|flip|mirror|transform|scale)', r'\1'),
        (r'(enable|disable|toggle|show|hide)', r'\1'),
        
        # State changes
        (r'(are|is|become[s]?)\s+(enabled|disabled|visible|hidden|available)', r'state: \2'),
        
        # User actions
        (r'user\s+(chooses?|selects?|clicks?|toggles?)', r'\1'),
        (r'(add|remove|create|delete)', r'\1'),
    ]
    
    # Outcome patterns
    OUTCOME_PATTERNS = [
        # Z-order outcomes
        (r'(?:move[s]?|appear[s]?)\s+(?:to\s+)?(?:the\s+)?(highest|top|above all)\s+(?:z-?order|level)?', 
         'moves to highest z-order'),
        (r'(?:move[s]?|appear[s]?)\s+(?:to\s+)?(?:the\s+)?(lowest|bottom|below all)\s+(?:z-?order|level)?',
         'moves to lowest z-order'),
        (r'(?:increase[s]?|move[s]? up)\s+(?:by\s+)?one\s+level',
         'increases z-order by one level'),
        (r'(?:decrease[s]?|move[s]? down)\s+(?:by\s+)?one\s+level',
         'decreases z-order by one level'),
        
        # State outcomes
        (r'(?:become[s]?|are|is)\s+(enabled|disabled|visible|hidden)',
         r'are \1'),
        (r'(?:remain[s]?|stay[s]?)\s+(?:the\s+same|unchanged)',
         'remains unchanged'),
        
        # Display outcomes
        (r'(?:display[s]?|show[s]?|appear[s]?)',
         'is displayed'),
        (r'(?:hide[s]?|remove[s]?|disappear[s]?)',
         'is hidden'),
    ]
    
    # Boundary condition patterns
    BOUNDARY_PATTERNS = [
        (r'(?:at|when at|already at)\s+(?:the\s+)?(top|front|highest)',
         'at top'),
        (r'(?:at|when at|already at)\s+(?:the\s+)?(bottom|back|lowest)',
         'at bottom'),
        (r'(?:when|with|if)\s+no\s+(selection|object)',
         'no selection'),
        (r'(?:when|with|if)\s+(?:an?\s+)?(non-ellipse|non-circle|rectangle|wrong\s+type)',
         'wrong object type'),
        (r'multi(?:-|\s)?select',
         'multi-selection'),
        (r'(?:repeat|duplicate|reappl)',
         'repeated action'),
    ]
    
    def parse(self, ac_bullet: str) -> ACSemantics:
        """Parse AC bullet into semantic structure."""
        ac_clean = self._clean_ac(ac_bullet)
        ac_lower = ac_clean.lower()
        
        # Extract action
        action = self._extract_action(ac_lower)
        
        # Extract target
        target = self._extract_target(ac_lower, action)
        
        # Extract outcome
        outcome = self._extract_outcome(ac_lower, action)
        
        # Extract conditions
        conditions = self._extract_conditions(ac_lower)
        
        # Detect boundary cases
        boundary_cases = self._detect_boundary_cases(ac_lower)
        
        # Determine if negation
        negation = self._is_negation(ac_lower)
        
        return ACSemantics(
            action=action,
            target=target,
            outcome=outcome,
            conditions=conditions,
            boundary_cases=boundary_cases,
            negation=negation
        )
    
    def _clean_ac(self, ac_bullet: str) -> str:
        """Remove numbering and clean AC bullet."""
        # Remove leading numbers/bullets
        ac_clean = re.sub(r'^\d+[\.)]\s*', '', ac_bullet).strip()
        # Remove "Acceptance Criteria" header if present
        ac_clean = re.sub(r'^Acceptance Criteria:?\s*', '', ac_clean, flags=re.IGNORECASE)
        return ac_clean
    
    def _extract_action(self, ac_lower: str) -> str:
        """Extract primary action from AC."""
        for pattern, replacement in self.ACTION_PATTERNS:
            match = re.search(pattern, ac_lower)
            if match:
                if replacement.startswith(r'\1'):
                    return match.group(0)
                else:
                    return replacement
        
        # Fallback: First verb phrase
        verb_match = re.search(r'((?:bring|send|move|enable|disable|show|hide|toggle|rotate|flip|mirror)\s+\w+)', ac_lower)
        if verb_match:
            return verb_match.group(1)
        
        return "perform action"
    
    def _extract_target(self, ac_lower: str, action: str) -> str:
        """Extract target object/control."""
        # Common targets
        targets = [
            r'draw\s+order\s+(?:actions?|commands?|operations?)',
            r'selected\s+(?:object|shape|item)',
            r'diameter\s+(?:measurement|label|line)',
            r'(?:the\s+)?object',
            r'(?:the\s+)?shape',
            r'(?:the\s+)?control',
            r'menu\s+items?',
        ]
        
        for target_pattern in targets:
            match = re.search(target_pattern, ac_lower)
            if match:
                return match.group(0)
        
        return "item"
    
    def _extract_outcome(self, ac_lower: str, action: str) -> str:
        """Extract expected outcome."""
        for pattern, replacement in self.OUTCOME_PATTERNS:
            match = re.search(pattern, ac_lower)
            if match:
                if r'\1' in replacement:
                    return re.sub(pattern, replacement, match.group(0))
                else:
                    return replacement
        
        # Fallback: Use action as outcome
        if 'enable' in action:
            return 'are enabled'
        elif 'disable' in action:
            return 'are disabled'
        elif 'show' in action or 'visible' in action:
            return 'are visible'
        elif 'hide' in action or 'hidden' in action:
            return 'are hidden'
        else:
            return 'works correctly'
    
    def _extract_conditions(self, ac_lower: str) -> List[str]:
        """Extract conditions/constraints."""
        conditions = []
        
        # "when X" patterns
        when_patterns = [
            r'when\s+(?:an?\s+)?object\s+is\s+selected',
            r'when\s+no\s+object\s+is\s+selected',
            r'when\s+(?:the\s+)?object\s+is\s+(?:at\s+)?(?:top|bottom)',
            r'for\s+(?:ellipse|circle|rectangle)',
        ]
        
        for pattern in when_patterns:
            match = re.search(pattern, ac_lower)
            if match:
                conditions.append(match.group(0))
        
        return conditions
    
    def _detect_boundary_cases(self, ac_lower: str) -> List[str]:
        """Detect boundary cases mentioned in AC."""
        boundary_cases = []
        
        for pattern, boundary_type in self.BOUNDARY_PATTERNS:
            if re.search(pattern, ac_lower):
                boundary_cases.append(boundary_type)
        
        return boundary_cases
    
    def _is_negation(self, ac_lower: str) -> bool:
        """Check if this is a negative scenario."""
        negative_indicators = [
            'disable', 'disabled', 'hide', 'hidden', 'no selection',
            'cannot', 'should not', 'must not', 'without'
        ]
        
        return any(indicator in ac_lower for indicator in negative_indicators)


class BoundaryCaseGenerator:
    """Generates boundary case tests from AC analysis."""
    
    def generate_boundary_tests(
        self,
        story_id: int,
        feature_name: str,
        semantics: ACSemantics,
        base_test_id: str,
        context: Dict
    ) -> List[Dict]:
        """Generate boundary case tests based on AC semantics."""
        boundary_tests = []
        
        # For stacking operations, generate boundary tests
        if 'z-order' in semantics.outcome or 'level' in semantics.outcome:
            boundary_tests.extend(
                self._generate_stacking_boundaries(story_id, feature_name, semantics, context)
            )
        
        # For state changes, generate "no selection" test
        if semantics.conditions and any('no object' in c for c in semantics.conditions):
            boundary_test = self._generate_no_selection_test(story_id, feature_name, semantics, context)
            if boundary_test:
                boundary_tests.append(boundary_test)
        
        return boundary_tests
    
    def _generate_stacking_boundaries(
        self,
        story_id: int,
        feature_name: str,
        semantics: ACSemantics,
        context: Dict
    ) -> List[Dict]:
        """Generate stacking operation boundary tests."""
        tests = []
        
        # "Above" action at top
        if 'above' in semantics.action.lower():
            test = {
                'type': 'boundary',
                'scenario': 'At Top Does Not Change Order',
                'setup': 'top-most',
                'action': semantics.action,
                'expected': 'remains top-most'
            }
            tests.append(test)
        
        # "Under" action at bottom
        if 'under' in semantics.action.lower():
            test = {
                'type': 'boundary',
                'scenario': 'At Bottom Does Not Change Order',
                'setup': 'bottom-most',
                'action': semantics.action,
                'expected': 'remains bottom-most'
            }
            tests.append(test)
        
        return tests
    
    def _generate_no_selection_test(
        self,
        story_id: int,
        feature_name: str,
        semantics: ACSemantics,
        context: Dict
    ) -> Optional[Dict]:
        """Generate 'no selection' boundary test."""
        return {
            'type': 'boundary',
            'scenario': 'Actions Disabled Without Selection',
            'setup': 'no selection',
            'action': 'open menu',
            'expected': 'actions are disabled'
        }


class ComprehensiveStepBuilder:
    """Builds comprehensive, properly sequenced test steps."""

    def __init__(self, app_config=None):
        """Initialize with optional application configuration.

        Args:
            app_config: Application configuration with name, prereq_template, etc.
        """
        self._app_config = app_config
        # Default values if no config provided
        self._app_name = "Application"
        self._prereq = "Pre-req: The application is installed"
        self._launch = "Launch the application."
        self._close = "Close the application"

        if app_config:
            self._app_name = getattr(app_config, 'name', self._app_name)
            if hasattr(app_config, 'get_prereq_step'):
                self._prereq = app_config.get_prereq_step()
            if hasattr(app_config, 'get_launch_step'):
                self._launch = app_config.get_launch_step()
            if hasattr(app_config, 'get_close_step'):
                self._close = app_config.get_close_step()

    def build_steps(
        self,
        semantics: ACSemantics,
        feature_name: str,
        context: Dict
    ) -> List[Dict]:
        """Build test steps from AC semantics."""
        steps = []

        # Step 1: PRE-REQ (mandatory)
        steps.append({"action": self._prereq, "expected": ""})

        # Step 2: Launch
        steps.append({"action": self._launch, "expected": ""})

        # Step 3: Setup (based on what's needed)
        setup_steps = self._build_setup_steps(semantics, context)
        steps.extend(setup_steps)

        # Step 4: Action steps
        action_steps = self._build_action_steps(semantics, feature_name, context)
        steps.extend(action_steps)

        # Step 5: Verification
        verification = self._build_verification(semantics)
        steps.append(verification)

        # Step 6: Close/Exit (mandatory, no expected)
        steps.append({"action": self._close, "expected": ""})
        
        return steps
    
    def _build_setup_steps(self, semantics: ACSemantics, context: Dict) -> List[Dict]:
        """Build setup steps based on semantics."""
        steps = []
        
        # Check if we need overlapping objects (for stacking tests)
        if 'z-order' in semantics.outcome or 'level' in semantics.outcome:
            # Need overlapping objects
            num_objects = 3
            steps.append({"action": f"Draw {self._num_to_word(num_objects)} overlapping shapes on the Canvas.", "expected": ""})
            
            # Select appropriate object based on action
            if 'front' in semantics.action.lower() or 'above' in semantics.action.lower():
                steps.append({"action": "Select the bottom-most shape.", "expected": ""})
            elif 'back' in semantics.action.lower() or 'under' in semantics.action.lower():
                steps.append({"action": "Select the top-most shape.", "expected": ""})
            else:
                steps.append({"action": "Select one shape.", "expected": ""})
        
        # Check if we need single object selection
        elif semantics.conditions and any('selected' in c for c in semantics.conditions):
            steps.append({"action": "Draw a shape on the Canvas.", "expected": ""})
            steps.append({"action": "Select the drawn shape.", "expected": ""})
        
        # Check if we explicitly need no selection
        elif semantics.negation and 'selection' in semantics.target:
            steps.append({"action": "Ensure no object is selected on the Canvas.", "expected": ""})
        
        return steps
    
    def _build_action_steps(
        self,
        semantics: ACSemantics,
        feature_name: str,
        context: Dict
    ) -> List[Dict]:
        """Build action steps based on semantics."""
        steps = []
        entry_point = context.get('entry_point', 'Menu')
        
        # Build specific action based on action type
        if 'bring to front' in semantics.action.lower():
            steps.append({"action": f"Select {entry_point} → {feature_name} → Bring to Front.", "expected": ""})
        elif 'send to back' in semantics.action.lower():
            steps.append({"action": f"Select {entry_point} → {feature_name} → Send to Back.", "expected": ""})
        elif 'bring above' in semantics.action.lower():
            steps.append({"action": f"Select {entry_point} → {feature_name} → Bring Above Objects.", "expected": ""})
        elif 'send under' in semantics.action.lower():
            steps.append({"action": f"Select {entry_point} → {feature_name} → Send Under Objects.", "expected": ""})
        else:
            # Generic action
            action_cap = ' '.join(word.capitalize() for word in semantics.action.split())
            steps.append({"action": f"Select {entry_point} → {feature_name}.", "expected": ""})
        
        return steps
    
    def _build_verification(self, semantics: ACSemantics) -> Dict:
        """Build verification step from semantics."""
        # Build verification based on outcome
        if 'highest z-order' in semantics.outcome:
            action = "Verify the selected shape appears above all other objects."
            expected = "The selected shape is displayed above all other objects."
        elif 'lowest z-order' in semantics.outcome:
            action = "Verify the selected shape appears below all other objects."
            expected = "The selected shape is displayed below all other objects."
        elif 'one level' in semantics.outcome:
            if 'increase' in semantics.outcome:
                action = "Verify the selected shape is above the previously adjacent object and below the top object."
                expected = "The selected shape increases its stacking order by exactly one level."
            else:
                action = "Verify the selected shape is below the previously adjacent object and above the bottom object."
                expected = "The selected shape decreases its stacking order by exactly one level."
        elif 'enabled' in semantics.outcome:
            action = f"Verify all {semantics.target} are enabled."
            expected = f"All {semantics.target} are enabled when an object is selected."
        elif 'disabled' in semantics.outcome:
            action = f"Verify all {semantics.target} are disabled."
            expected = f"{semantics.target.capitalize()} are disabled when no object is selected."
        else:
            # Generic verification
            action = "Verify the expected behavior is observed."
            expected = f"{semantics.outcome.capitalize()}."
        
        return {"action": action, "expected": expected}
    
    def _num_to_word(self, n: int) -> str:
        """Convert number to word."""
        words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
        return words.get(n, str(n))
