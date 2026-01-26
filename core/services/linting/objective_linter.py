"""
Objective Linter
Validates objectives against test case titles and evidence.
"""
from typing import List
from core.domain.models import Objective, TestCase, EvidenceModel, LintResult


class ObjectiveLinter:
    """Lints objectives to prevent scope drift."""
    
    def __init__(self, evidence: EvidenceModel):
        """Initialize with evidence model.
        
        Args:
            evidence: Evidence model containing allowed/forbidden terms
        """
        self.evidence = evidence
    
    def lint_objective(self, objective: Objective, test_case: TestCase) -> LintResult:
        """Lint single objective against its test case.
        
        Args:
            objective: The objective to lint
            test_case: The corresponding test case
            
        Returns:
            LintResult with ok=True if all checks pass
        """
        result = LintResult(ok=True)
        
        # Check starts with "Objective: Verify that"
        self._check_format(objective, result)
        
        # Check doesn't add scope beyond title
        self._check_scope(objective, test_case, result)
        
        # Check device/tool inclusion
        self._check_device_tool(objective, test_case, result)
        
        # Check for forbidden speculative language
        self._check_speculative_language(objective, result)
        
        return result
    
    def lint_all(self, objectives: List[Objective], test_cases: List[TestCase]) -> LintResult:
        """Lint all objectives.
        
        Args:
            objectives: List of objectives
            test_cases: List of corresponding test cases
            
        Returns:
            Combined LintResult
        """
        combined_result = LintResult(ok=True)
        
        if len(objectives) != len(test_cases):
            combined_result.add_error(
                f"Objective count ({len(objectives)}) doesn't match "
                f"test case count ({len(test_cases)})"
            )
            return combined_result
        
        for obj, tc in zip(objectives, test_cases):
            if obj.test_id != tc.test_id:
                combined_result.add_error(
                    f"ID mismatch: objective {obj.test_id} vs test case {tc.test_id}"
                )
                continue
            
            obj_result = self.lint_objective(obj, tc)
            if not obj_result.ok:
                combined_result.errors.extend(
                    f"{obj.test_id}: {err}" for err in obj_result.errors
                )
                combined_result.ok = False
            
            if obj_result.warnings:
                combined_result.warnings.extend(
                    f"{obj.test_id}: {warn}" for warn in obj_result.warnings
                )
        
        return combined_result
    
    def _check_format(self, objective: Objective, result: LintResult):
        """Check objective starts with 'Objective: Verify that'."""
        text = objective.objective_text.strip()
        
        if not text.lower().startswith('verify that'):
            # Try to check if format is "Objective: Verify that"
            if 'objective:' not in text.lower():
                result.add_error("Objective must start with 'Verify that'")
    
    def _check_scope(self, objective: Objective, test_case: TestCase, result: LintResult):
        """Check objective doesn't add scope beyond title."""
        obj_text = objective.objective_text.lower()
        title = test_case.title.lower()
        
        # Extract scenario from title (after last /)
        if ' / ' in title:
            scenario = title.split(' / ')[-1].strip()
            scenario = scenario.split('(')[0].strip()  # Remove device suffix
            
            # Check if objective introduces new concepts not in title
            title_words = set(title.split())
            obj_words = set(obj_text.split())
            
            # Key domain words that if in objective must be in title
            key_terms = [
                'canvas', 'toolbar', 'dialog', 'modal', 'persistence',
                'horizontal', 'vertical', 'rotation', 'mirror', 'flip',
                'undo', 'redo', 'selection', 'properties', 'dimensions'
            ]
            
            for term in key_terms:
                if term in obj_words and term not in title_words:
                    result.add_warning(
                        f"Objective introduces '{term}' not in test case title"
                    )
    
    def _check_device_tool(self, objective: Objective, test_case: TestCase, result: LintResult):
        """Check device/tool mentioned when applicable."""
        obj_text = objective.objective_text.lower()
        title = test_case.title.lower()
        
        # If test case has device, objective should mention it
        if test_case.device:
            device = test_case.device.lower()
            if device == "tablets":
                # Check for iPad or Android mentions
                if 'ipad' not in obj_text and 'android' not in obj_text and 'tablet' not in obj_text:
                    result.add_warning("Objective should mention tablet device")
            else:
                if device not in obj_text:
                    result.add_warning(f"Objective should mention device: {test_case.device}")
        
        # If accessibility test, check for tool mention
        if test_case.is_accessibility:
            accessibility_terms = ['accessibility', 'keyboard', 'focus', 'aria', 'wcag']
            if not any(term in obj_text for term in accessibility_terms):
                result.add_warning("Accessibility objective should mention accessibility aspects")
    
    def _check_speculative_language(self, objective: Objective, result: LintResult):
        """Check for speculative language."""
        obj_text = objective.objective_text.lower()
        
        forbidden_words = [
            'assumingly', 'generally', 'presumably', 'supposedly',
            'probably', 'likely', 'possibly', 'potentially'
        ]
        
        for word in forbidden_words:
            if word in obj_text:
                result.add_error(f"Forbidden speculative word: '{word}'")
