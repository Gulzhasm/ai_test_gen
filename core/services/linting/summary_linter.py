"""
Summary Linter
Validates QA Planning Summary against evidence sources.
"""
import re
from typing import List
from core.domain.models import EvidenceModel, LintResult


class SummaryLinter:
    """Lints QA Planning Summary to prevent hallucinations and scope drift."""
    
    def __init__(self, evidence: EvidenceModel):
        """Initialize with evidence model.
        
        Args:
            evidence: Evidence model containing allowed/forbidden terms
        """
        self.evidence = evidence
        
        # Forbidden speculative words (always forbidden)
        self.forbidden_speculative = [
            'assumingly', 'generally', 'presumably', 'supposedly',
            'probably', 'likely', 'possibly', 'potentially'
        ]
        
        # UI surfaces that must be evidence-based
        self.ui_surfaces = [
            'canvas', 'toolbar', 'dialog', 'persistence', 'file menu',
            'edit menu', 'tools menu', 'properties panel', 'dimensions panel',
            'modal window', 'top action toolbar'
        ]
    
    def lint(self, summary: str) -> LintResult:
        """Lint summary against evidence.
        
        Args:
            summary: The generated summary text
            
        Returns:
            LintResult with ok=True if all checks pass
        """
        result = LintResult(ok=True)
        
        # Check structure
        self._check_structure(summary, result)
        
        # Check for invented UI surfaces
        self._check_ui_surfaces(summary, result)
        
        # Check for speculative language
        self._check_speculative_language(summary, result)
        
        # Check for forbidden words
        self._check_forbidden_words(summary, result)
        
        # Check bullet count
        self._check_bullet_count(summary, result)
        
        # Check for fragmented bullets
        self._check_fragmented_bullets(summary, result)
        
        # Check platform sentence
        self._check_platform_sentence(summary, result)
        
        return result
    
    def _check_structure(self, summary: str, result: LintResult):
        """Check required structure."""
        required_sections = [
            "This work item introduces",
            "Testing will focus on verifying:",
            "Functional dependencies include",
            "Accessibility testing will validate",
            "Tests will be executed on"
        ]
        
        for section in required_sections:
            if section not in summary:
                result.add_error(f"Missing required section: '{section}'")
    
    def _check_ui_surfaces(self, summary: str, result: LintResult):
        """Check UI surfaces are supported by evidence."""
        summary_lower = summary.lower()
        
        for ui_surface in self.ui_surfaces:
            if ui_surface in summary_lower:
                if not self.evidence.is_supported(ui_surface):
                    result.add_error(
                        f"Invented UI surface: '{ui_surface}' not found in evidence "
                        f"(Description, AC, or test titles)"
                    )
    
    def _check_speculative_language(self, summary: str, result: LintResult):
        """Check for speculative words."""
        summary_lower = summary.lower()
        
        for word in self.forbidden_speculative:
            if word in summary_lower:
                result.add_error(f"Forbidden speculative word: '{word}'")
    
    def _check_forbidden_words(self, summary: str, result: LintResult):
        """Check for forbidden words from evidence model."""
        summary_lower = summary.lower()
        
        for word in self.evidence.forbidden_words:
            if word.lower() in summary_lower:
                result.add_error(f"Forbidden word: '{word}'")
    
    def _check_bullet_count(self, summary: str, result: LintResult):
        """Check bullet count is 6-9."""
        bullet_count = summary.count('•')
        
        if bullet_count < 6:
            result.add_error(f"Too few bullets: {bullet_count} (minimum 6)")
        elif bullet_count > 9:
            result.add_error(f"Too many bullets: {bullet_count} (maximum 9)")
    
    def _check_fragmented_bullets(self, summary: str, result: LintResult):
        """Check bullets are not fragmented."""
        lines = summary.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('•'):
                bullet_text = line[1:].strip()
                
                # Check for too-short bullets
                if len(bullet_text.split()) < 3:
                    result.add_warning(f"Very short bullet: '{bullet_text}'")
                
                # Check for incomplete sentences
                if not any(c in bullet_text for c in ['.', ',', ' ']):
                    result.add_warning(f"Fragmented bullet: '{bullet_text}'")
    
    def _check_platform_sentence(self, summary: str, result: LintResult):
        """Check platform sentence is correct and fixed."""
        expected_sentence = (
            "Tests will be executed on Windows 11 and tablet devices "
            "(iOS iPad and Android Tablet) to validate consistent behavior "
            "across mouse-based and touch-based interaction models."
        )
        
        if expected_sentence not in summary:
            # Check if it starts with the right phrase
            if "Tests will be executed on" not in summary:
                result.add_error("Missing platform execution sentence")
            else:
                result.add_warning(
                    "Platform sentence format differs from standard format. "
                    "Expected format: 'Tests will be executed on Windows 11 and tablet devices...'"
                )
