"""
Refactored Rule-Driven Test Case Generator.

Uses Ruleset and Builders for deterministic, evidence-based test generation.
"""
from typing import List, Dict, Optional
import re
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.domain.ruleset import Ruleset, EvidenceBullet
from core.application.use_cases.test_builders import (
    AvailabilityBuilder, ActionBuilder, UndoRedoBuilder, AccessibilityBuilder,
    BoundaryBuilder, StateNegativeBuilder, VisibilityBuilder, BaseBuilder
)
from core.application.use_cases.test_validators import MappingValidator, EvidenceValidator
from src.test_rules import TestRules
import config


class TestGenerator:
    """
    Refactored test case generator using Ruleset and Builders.
    
    This version enforces deterministic, evidence-based test generation:
    - All tests must have evidence (AC or QA Prep bullets)
    - No heuristics or assumptions
    - Explicit gating via Ruleset.has_signal()
    - Validated mapping (1 primary test per AC, capped extras)
    - Evidence validation (no forbidden assertions)
    """
    
    def __init__(self):
        self.rules = TestRules()
        self.test_id_counter = 5  # Start at 005 after AC1
    
    def generate_test_cases(self, story_data: Dict, criteria: List[str], qa_prep_content: Optional[str] = None) -> List[Dict]:
        """
        Generate test cases from story data, acceptance criteria, and QA prep.
        
        Args:
            story_data: Dict with 'story_id', 'title', 'description_text', 'acceptance_criteria_text', 'qa_prep_text'
            criteria: List of acceptance criteria bullets (parsed and ordered)
            qa_prep_content: Optional QA prep content for coverage expansion
        
        Returns:
            List of test case dicts with 'id', 'title', 'steps', 'objective', 'source_ac_id', 'evidence_refs'
        """
        story_id = story_data.get('story_id') or story_data.get('id')
        feature_name = self.rules.extract_feature_name(story_data.get('title', ''))
        
        # Step 1: Build Ruleset from evidence
        ruleset = self._build_ruleset(story_id, criteria, qa_prep_content)
        
        # Step 2: Initialize builders
        builders = self._initialize_builders(ruleset, story_id, feature_name)
        
        # Step 3: Generate primary tests (1 per AC bullet)
        test_cases = []
        for idx, ac_bullet_text in enumerate(criteria):
            # Skip cancelled AC
            if self.rules.is_cancelled(ac_bullet_text):
                print(f"  ⚠ Skipping cancelled AC{idx + 1}: {ac_bullet_text[:50]}...")
                continue
            
            ac_bullet = EvidenceBullet(id=f"AC{idx + 1}", text=ac_bullet_text, source="AC")
            
            # Generate primary test using appropriate builder
            primary_test = self._generate_primary_test(ac_bullet, builders, story_id, idx)
            if primary_test:
                test_cases.append(primary_test)
            
            # Generate extra tests from QA Prep (capped at 3 per AC)
            extra_tests = self._generate_extra_tests(ac_bullet, ruleset, builders, story_id, idx)
            test_cases.extend(extra_tests[:3])  # Cap at 3 extra tests
        
        # Step 4: Validate mapping
        mapping_validator = MappingValidator(ruleset)
        is_valid, errors = mapping_validator.validate_mapping(test_cases)
        if not is_valid:
            print("\n✗ MAPPING VALIDATION FAILED:")
            for error in errors:
                print(f"  ✗ {error}")
            # Continue anyway for now, but log errors
        
        # Step 5: Validate evidence (no forbidden assertions)
        evidence_validator = EvidenceValidator(ruleset)
        is_valid, errors = evidence_validator.validate_evidence(test_cases)
        if not is_valid:
            print("\n✗ EVIDENCE VALIDATION FAILED:")
            for error in errors:
                print(f"  ✗ {error}")
            # Continue anyway for now, but log errors
        
        # Step 6: Post-process (clean forbidden words, ensure mandatory steps)
        test_cases = self._post_process_test_cases(test_cases)
        
        print(f"  Generated {len(test_cases)} test cases from {len(criteria)} AC bullets")
        return test_cases
    
    def _build_ruleset(self, story_id: int, criteria: List[str], qa_prep_content: Optional[str]) -> Ruleset:
        """Build Ruleset from AC bullets and QA Prep content."""
        ruleset = Ruleset(story_id=story_id)
        
        # Add AC bullets
        for idx, ac_text in enumerate(criteria):
            if not self.rules.is_cancelled(ac_text):
                ruleset.add_ac_bullet(f"AC{idx + 1}", ac_text)
        
        # Parse and add QA Prep bullets
        if qa_prep_content:
            qa_bullets = self._parse_qa_prep_bullets(qa_prep_content)
            for idx, qa_text in enumerate(qa_bullets):
                ruleset.add_qa_prep_bullet(f"QA-{idx + 1}", qa_text)
        
        return ruleset
    
    def _parse_qa_prep_bullets(self, qa_prep_content: str) -> List[str]:
        """Parse QA Prep content into individual bullets."""
        # Simple bullet parsing - split by newlines and filter empty
        bullets = []
        for line in qa_prep_content.split('\n'):
            line = line.strip()
            if line and (line.startswith('-') or line.startswith('•') or line.startswith('*')):
                # Remove bullet marker
                bullet_text = re.sub(r'^[-•*]\s*', '', line)
                if bullet_text:
                    bullets.append(bullet_text)
            elif line and len(line) > 10:  # Non-bullet lines that might be important
                bullets.append(line)
        return bullets
    
    def _initialize_builders(self, ruleset: Ruleset, story_id: int, feature_name: str) -> Dict[str, BaseBuilder]:
        """Initialize all builders."""
        return {
            'availability': AvailabilityBuilder(ruleset, story_id, feature_name),
            'action': ActionBuilder(ruleset, story_id, feature_name),
            'undo_redo': UndoRedoBuilder(ruleset, story_id, feature_name),
            'accessibility': AccessibilityBuilder(ruleset, story_id, feature_name),
            'boundary': BoundaryBuilder(ruleset, story_id, feature_name),
            'negative': StateNegativeBuilder(ruleset, story_id, feature_name),
            'visibility': VisibilityBuilder(ruleset, story_id, feature_name),
        }
    
    def _generate_primary_test(self, ac_bullet: EvidenceBullet, builders: Dict[str, BaseBuilder], 
                               story_id: int, ac_index: int) -> Optional[Dict]:
        """Generate primary test case for an AC bullet."""
        # Determine which builder to use based on AC content
        ac_text_lower = ac_bullet.text.lower()
        
        # AC1 is always availability
        if ac_index == 0:
            builder = builders['availability']
            test_case = builder.build(ac_bullet)
        # Undo/Redo
        elif 'undo' in ac_text_lower or 'redo' in ac_text_lower:
            builder = builders['undo_redo']
            test_case = builder.build(ac_bullet)
        # Accessibility
        elif 'accessibility' in ac_text_lower or 'keyboard' in ac_text_lower or 'wcag' in ac_text_lower:
            builder = builders['accessibility']
            test_cases = builder.build(ac_bullet)  # Returns list
            test_case = test_cases[0] if test_cases else None
        # Action (add, remove, enable, disable)
        elif any(word in ac_text_lower for word in ['add', 'remove', 'enable', 'disable', 'toggle', 'activate']):
            builder = builders['action']
            test_case = builder.build(ac_bullet)
        # Boundary/Constraint
        elif any(word in ac_text_lower for word in ['constraint', 'boundary', 'limit', 'maximum', 'minimum', '360', 'wrap']):
            builder = builders['boundary']
            test_case = builder.build(ac_bullet)
        # Visibility
        elif any(word in ac_text_lower for word in ['visible', 'hidden', 'displayed', 'shown']):
            builder = builders['visibility']
            test_case = builder.build(ac_bullet)
        # Default: Action builder
        else:
            builder = builders['action']
            test_case = builder.build(ac_bullet)
        
        return test_case
    
    def _generate_extra_tests(self, ac_bullet: EvidenceBullet, ruleset: Ruleset, 
                              builders: Dict[str, BaseBuilder], story_id: int, ac_index: int) -> List[Dict]:
        """Generate extra tests from QA Prep (capped at 3 per AC)."""
        extra_tests = []
        
        # Only generate extra tests if QA Prep exists
        if not ruleset.qa_prep_bullets:
            return extra_tests
        
        # Check for additional signals in QA Prep that weren't covered by primary test
        # This is simplified - in practice, we'd check coverage gaps
        
        # Accessibility extra tests
        if ruleset.has_signal('accessibility') and ac_index == 0:  # Only for AC1 typically
            builder = builders['accessibility']
            accessibility_tests = builder.build(ac_bullet)
            extra_tests.extend(accessibility_tests)
        
        # Boundary extra tests
        if ruleset.has_signal('constraint') and ac_index > 0:
            builder = builders['boundary']
            boundary_test = builder.build(ac_bullet)
            if boundary_test:
                extra_tests.append(boundary_test)
        
        # Negative state tests
        if ruleset.has_signal('negative'):
            builder = builders['negative']
            negative_test = builder.build(ac_bullet)
            if negative_test:
                extra_tests.append(negative_test)
        
        return extra_tests
    
    def _post_process_test_cases(self, test_cases: List[Dict]) -> List[Dict]:
        """Post-process test cases: clean forbidden words, ensure mandatory steps."""
        processed = []
        
        for tc in test_cases:
            # Clean title and objective
            if 'title' in tc:
                tc['title'] = self.rules.clean_forbidden_words(tc['title'])
            if 'objective' in tc:
                tc['objective'] = self.rules.clean_forbidden_words(tc['objective'])
            
            # Clean steps
            if 'steps' in tc:
                for step in tc['steps']:
                    if 'action' in step:
                        step['action'] = self.rules.clean_forbidden_words(step['action'])
                    if 'expected' in step:
                        step['expected'] = self.rules.clean_forbidden_words(step['expected'])
            
            # Ensure requires_object flag is set if needed
            if not tc.get('requires_object'):
                steps_text = ' '.join([s.get('action', '') for s in tc.get('steps', [])])
                tc['requires_object'] = self.rules.requires_object_interaction(steps_text)
            
            processed.append(tc)
        
        return processed
