"""
Validator Module
Validates test cases against all strict QA rules.
"""
import re
from typing import Dict, List, Tuple

import config


class TestCaseValidator:
    """Validates test cases against strict QA rules."""
    
    def validate_test_cases(self, test_cases: List[Dict]) -> Tuple[bool, List[str]]:
        """Quality Gate: Validate all test cases against strict rules."""
        errors = []
        
        for idx, tc in enumerate(test_cases):
            tc_id = tc['id']
            
            # Check ID format
            if idx == 0:
                if not tc_id.endswith('-AC1'):
                    errors.append(f"{tc_id}: AC1 test case must be first")
            else:
                if not re.match(r'\d+-\d{3}$', tc_id):
                    errors.append(f"{tc_id}: Invalid ID format (should be 005, 010, etc.)")
            
            # Check mandatory PRE-REQ
            has_prereq = any(
                'PRE-REQ: ENV QuickDraw application is installed' in step.get('action', '')
                for step in tc['steps']
            )
            if not has_prereq:
                errors.append(f"{tc_id}: Missing mandatory PRE-REQ step")
            
            # Check mandatory Close step (exact text required)
            has_close = any(
                'Close/Exit the QuickDraw application' in step.get('action', '')
                for step in tc['steps']
            )
            if not has_close:
                errors.append(f"{tc_id}: Missing mandatory Close step: 'Close/Exit the QuickDraw application'")
            
            # Check Close step has no expected result
            for step in tc['steps']:
                if 'Close/Exit the QuickDraw application' in step.get('action', ''):
                    if step.get('expected', '').strip():
                        errors.append(f"{tc_id}: Close step must have no expected result")
            
            # Check forbidden words
            for step in tc['steps']:
                action = step.get('action', '').lower()
                for forbidden in config.FORBIDDEN_WORDS:
                    if forbidden.lower() in action:
                        errors.append(f"{tc_id}: Contains forbidden word: {forbidden}")
            
            # Check accessibility tests
            if tc.get('is_accessibility'):
                if not tc.get('device'):
                    errors.append(f"{tc_id}: Accessibility test must specify device")
                
                # Check tool PRE-REQ
                has_tool_prereq = any(
                    'PRE-REQ:' in step.get('action', '') and
                    ('Accessibility Insights' in step.get('action', '') or
                     'VoiceOver' in step.get('action', '') or
                     'Accessibility Scanner' in step.get('action', ''))
                    for step in tc['steps']
                )
                if not has_tool_prereq:
                    errors.append(f"{tc_id}: Accessibility test missing tool PRE-REQ")
            
            # Check object interaction steps
            # Only require drawing steps if test actually involves object operations
            if tc.get('requires_object'):
                # Check if test involves object operations (drawing, selecting, modifying objects)
                has_object_ops = any(
                    keyword in step.get('action', '').lower() 
                    for step in tc['steps']
                    for keyword in ['draw', 'shape', 'object', 'select the', 'modify', 'rotate', 'move', 'transform']
                )
                
                if has_object_ops:
                    # Test involves object operations, so it must have drawing steps
                    has_draw = any('Draw a shape' in step.get('action', '') for step in tc['steps'])
                    has_select = any('Select' in step.get('action', '') and ('shape' in step.get('action', '').lower() or 'object' in step.get('action', '').lower() or 'drawn' in step.get('action', '').lower()) for step in tc['steps'])
                    if not has_draw:
                        errors.append(f"{tc_id}: Missing 'Draw a shape on the Canvas' step")
                    if not has_select:
                        errors.append(f"{tc_id}: Missing 'Select the drawn shape' step")
            
            # Check title format
            title = tc['title']
            if not re.match(r'\d+-(AC1|\d{3}):', title):
                errors.append(f"{tc_id}: Invalid title format")
            
            # Check title clarity (FROM WHERE / WHAT / SCOPE)
            if ' / ' not in title or title.count(' / ') < 2:
                errors.append(f"{tc_id}: Title must follow format: <ID>: <Feature> / <Area> / <Scenario>")
            
            # Validate Step Expected rules
            for step_idx, step in enumerate(tc['steps'], start=1):
                action = step.get('action', '').lower()
                expected = step.get('expected', '').strip()
                
                # Setup/teardown steps must have blank expected
                # Note: Menu opening steps can have expected results if they describe what should happen
                # (e.g., "Edit menu opens" is acceptable)
                setup_patterns = [
                    'pre-req:',
                    'launch env quickdraw',
                    'close/exit the quickdraw',
                    'draw a shape on the canvas',
                    'select the shape',
                    # 'open tools menu',  # Can have expected if it describes what should happen
                    # 'open file menu',  # Can have expected if it describes what should happen
                    # 'open edit menu',  # Can have expected if it describes what should happen
                    # 'open help menu',  # Can have expected if it describes what should happen
                    'open properties panel',
                    'open dimensions panel',
                    # 'activate',  # Can have expected if it describes what should happen
                    'select another drawing tool',
                    'select horizontal flip option',
                    'select vertical flip option',
                    # 'execute undo command',  # Can have expected if it's verification
                    # 'execute redo command',  # Can have expected if it's verification
                    'hold shift key',
                    'click and drag',
                ]
                
                is_setup_step = any(pattern in action for pattern in setup_patterns)
                
                # Note: Menu opening steps can have expected results if they describe what should happen
                # So we don't automatically flag them as setup steps
                # Only flag as setup if it's a panel opening (not menu) or if it's explicitly a setup pattern
                # if ('open' in action and 'panel' in action) and 'verify' not in action:
                #     is_setup_step = True
                
                # Tool activation for setup (not verification)
                # Note: "activate undo/redo functionality" can have expected results if it's verification
                # Only flag as setup if it's tool activation (not undo/redo functionality activation)
                if 'activate' in action and 'verify' not in action:
                    # Allow expected results for undo/redo functionality activation (it's verification, not setup)
                    if 'undo' not in action and 'redo' not in action:
                        is_setup_step = True
                
                if is_setup_step:
                    if expected:
                        errors.append(f"{tc_id}: Step {step_idx} ({action[:50]}...): Setup step must have blank Step Expected")
                else:
                    # Verification steps must have expected
                    if 'verify' in action or 'confirm' in action or 'check' in action:
                        if not expected:
                            errors.append(f"{tc_id}: Step {step_idx} ({action[:50]}...): Verification step must have Step Expected")
                        else:
                            # Check for forbidden ambiguous language in expected
                            forbidden_phrases = [
                                'or / or',
                                ' or ',  # Check for standalone " or " (not in words like "for")
                                'if available',
                                'if supported',
                                'works correctly',
                                'as expected',
                                'works as expected',
                                'should be correct',
                                'no issues found',
                            ]
                            expected_lower = expected.lower()
                            for phrase in forbidden_phrases:
                                # For " or ", check as whole word boundary to avoid false positives
                                if phrase == ' or ':
                                    if ' or ' in expected_lower:
                                        errors.append(f"{tc_id}: Step {step_idx}: Step Expected contains forbidden phrase: 'or'")
                                elif phrase in expected_lower:
                                    errors.append(f"{tc_id}: Step {step_idx}: Step Expected contains forbidden phrase: '{phrase}'")
                            
                            # Check expected is balanced (has what + where)
                            if len(expected.split()) < 3:
                                errors.append(f"{tc_id}: Step {step_idx}: Step Expected too short, must describe what changed and where")
        
        return len(errors) == 0, errors
