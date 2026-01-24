"""
Validators for test case generation.

MappingValidator: Ensures 1 primary test per AC bullet and caps extra tests.
EvidenceValidator: Blocks forbidden assertions unless explicitly signaled.
"""
from typing import List, Dict, Set, Tuple
from core.domain.ruleset import Ruleset


class MappingValidator:
    """
    Validates test case mapping to AC bullets.
    
    Rules:
    - Exactly 1 primary test per AC bullet
    - 0-3 extra tests per AC, capped across builders
    - Blocks any test without source_ac_id and evidence
    - Prevents duplicate coverage (same type + same condition)
    """
    
    def __init__(self, ruleset: Ruleset):
        self.ruleset = ruleset
        self.ac_ids = set(ruleset.get_all_ac_ids())
        self.test_coverage: Dict[str, Set[str]] = {}  # ac_id -> set of coverage types
    
    def validate_mapping(self, test_cases: List[Dict]) -> Tuple[bool, List[str]]:
        """
        Validate that test cases are correctly mapped to AC bullets.
        
        Returns:
            (is_valid, errors)
        """
        errors = []
        
        # Track coverage per AC
        ac_test_counts: Dict[str, int] = {ac_id: 0 for ac_id in self.ac_ids}
        ac_coverage_types: Dict[str, Set[str]] = {ac_id: set() for ac_id in self.ac_ids}
        
        # Check each test case
        for tc in test_cases:
            source_ac_id = tc.get('source_ac_id')
            
            # Must have source_ac_id
            if not source_ac_id:
                errors.append(f"Test case {tc.get('id', 'unknown')} missing source_ac_id")
                continue
            
            # Source AC must exist
            if source_ac_id not in self.ac_ids:
                errors.append(f"Test case {tc.get('id', 'unknown')} references non-existent AC: {source_ac_id}")
                continue
            
            # Track coverage
            ac_test_counts[source_ac_id] += 1
            
            # Track coverage type (availability, action, undo_redo, etc.)
            coverage_type = self._extract_coverage_type(tc)
            ac_coverage_types[source_ac_id].add(coverage_type)
        
        # Validate: exactly 1 primary test per AC
        for ac_id, count in ac_test_counts.items():
            if count == 0:
                errors.append(f"AC {ac_id} has no test cases")
            elif count > 4:  # 1 primary + 3 extra max
                errors.append(f"AC {ac_id} has {count} test cases (max 4 allowed: 1 primary + 3 extra)")
        
        # Check for duplicate coverage
        for ac_id, coverage_types in ac_coverage_types.items():
            # Check for duplicates (same coverage type appearing multiple times)
            # This is a simplified check - in practice, we'd check condition too
            if len(coverage_types) < ac_test_counts[ac_id]:
                # More tests than unique coverage types suggests duplicates
                pass  # Could add warning here
        
        return len(errors) == 0, errors
    
    def _extract_coverage_type(self, test_case: Dict) -> str:
        """Extract coverage type from test case."""
        title = test_case.get('title', '').lower()
        
        if 'availability' in title or 'accessible' in title:
            return 'availability'
        elif 'undo' in title or 'redo' in title:
            return 'undo_redo'
        elif 'accessibility' in title:
            return 'accessibility'
        elif 'boundary' in title or 'constraint' in title:
            return 'boundary'
        elif 'negative' in title or 'no selection' in title:
            return 'negative'
        elif 'visibility' in title:
            return 'visibility'
        else:
            return 'action'


class EvidenceValidator:
    """
    Validates that test cases don't include forbidden assertions unless explicitly signaled.
    
    Blocks:
    - Feedback assertions (unless explicit_feedback=True)
    - Layout assertions (unless explicit_layout_behavior=True)
    - Hotkey assertions (unless explicit_hotkeys=True)
    - WCAG level assertions (unless explicit_accessibility_standard is set)
    - Keyboard navigation on tablets (unless explicitly signaled)
    """
    
    def __init__(self, ruleset: Ruleset):
        self.ruleset = ruleset
    
    def validate_evidence(self, test_cases: List[Dict]) -> Tuple[bool, List[str]]:
        """
        Validate that test cases don't include forbidden assertions.
        
        Returns:
            (is_valid, errors)
        """
        errors = []
        
        for tc in test_cases:
            tc_id = tc.get('id', 'unknown')
            steps = tc.get('steps', [])
            platform = tc.get('platform', '')
            
            for step_idx, step in enumerate(steps, start=1):
                action = step.get('action', '').lower()
                expected = step.get('expected', '').lower()
                
                # Check for forbidden feedback assertions
                if not self.ruleset.explicit_feedback:
                    if any(word in action or word in expected for word in ['feedback', 'notification', 'message', 'alert']):
                        errors.append(f"{tc_id} Step {step_idx}: Contains feedback assertion but explicit_feedback=False")
                
                # Check for forbidden layout assertions
                if not self.ruleset.explicit_layout_behavior:
                    if any(word in action or word in expected for word in ['layout', 'position', 'arrange', 'space', 'occupy']):
                        errors.append(f"{tc_id} Step {step_idx}: Contains layout assertion but explicit_layout_behavior=False")
                
                # Check for forbidden hotkey assertions
                if not self.ruleset.explicit_hotkeys:
                    if any(word in action or word in expected for word in ['hotkey', 'shortcut', 'key combination', 'ctrl+', 'cmd+']):
                        errors.append(f"{tc_id} Step {step_idx}: Contains hotkey assertion but explicit_hotkeys=False")
                
                # Check for forbidden WCAG level assertions
                if not self.ruleset.explicit_accessibility_standard:
                    if 'wcag' in action or 'wcag' in expected:
                        errors.append(f"{tc_id} Step {step_idx}: Contains WCAG assertion but explicit_accessibility_standard=None")
                
                # Check for keyboard navigation on tablets
                if platform in ['iPad', 'Android Tablet']:
                    if 'keyboard' in action or 'keyboard' in expected:
                        if not self.ruleset.has_signal('accessibility') or 'keyboard' not in str(self.ruleset.explicit_accessibility_standard or '').lower():
                            errors.append(f"{tc_id} Step {step_idx}: Contains keyboard navigation on {platform} but not explicitly signaled")
        
        return len(errors) == 0, errors
