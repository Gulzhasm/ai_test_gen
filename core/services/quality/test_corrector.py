"""
LLM-based Test Corrector - Uses LLMs to enhance test case quality.

Provides deterministic, cached corrections for poor quality test cases.
"""
import json
import hashlib
from typing import Dict, Optional, List, Any

from core.interfaces.quality_standards import (
    ITestCorrector,
    TestCaseQualityMetrics,
    CorrectionResult,
    QualityLevel,
)
from core.interfaces.llm_provider import ILLMProvider


class LLMTestCorrector(ITestCorrector):
    """Uses LLM to correct and enhance test case quality."""

    CORRECTION_SYSTEM_PROMPT = """You are a test case quality expert. Your job is to improve test case quality by:

1. Replacing generic actions like "Perform the action described" with specific, actionable instructions
2. Replacing generic expected results like "works as expected" with observable, verifiable outcomes
3. Ensuring test steps are clear, specific, and follow QA best practices

RULES:
- Keep the same test structure (number of steps)
- Keep prerequisite, launch, and close steps unchanged
- Only modify steps that need improvement
- Make actions specific with UI elements (button, field, menu, panel, dialog)
- Make expected results observable (is displayed, appears, opens, shows, is visible)
- Do NOT add generic phrases like "works correctly" or "as expected"
- Be deterministic - same input should produce same output

OUTPUT FORMAT: Return ONLY valid JSON with the corrected test case."""

    STEP_ENHANCEMENT_PROMPT = """Enhance this test step to be more specific and observable.

Feature: {feature_name}
Context: {context}

Original Step:
- Action: {action}
- Expected: {expected}

Requirements:
1. Action must be specific with UI element names (button, field, menu, panel)
2. Expected result must be observable (is displayed, appears, opens, shows)
3. Do NOT use generic phrases like "works as expected"
4. Keep the same intent as the original

Return ONLY valid JSON: {{"action": "...", "expected": "..."}}"""

    def __init__(
        self,
        llm_provider: ILLMProvider,
        cache_manager: Optional[Any] = None,
        quality_threshold: float = 0.6
    ):
        """
        Initialize test corrector.

        Args:
            llm_provider: LLM provider for generating corrections
            cache_manager: Optional cache manager for deterministic results
            quality_threshold: Minimum quality score (0-1) to skip correction
        """
        self.llm = llm_provider
        self.cache = cache_manager
        self.quality_threshold = quality_threshold

    def correct_test_case(
        self,
        test_case: Dict,
        quality_metrics: TestCaseQualityMetrics,
        feature_context: Optional[str] = None
    ) -> CorrectionResult:
        """Correct a test case using LLM."""
        # Check if correction is needed
        quality_before = quality_metrics.overall_score
        if quality_before >= self.quality_threshold:
            return CorrectionResult(
                original_test=test_case,
                corrected_test=test_case,
                changes_made=[],
                quality_before=quality_before,
                quality_after=quality_before,
                confidence=1.0
            )

        # Check cache for deterministic results
        cache_key = self._get_cache_key(test_case)
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return CorrectionResult(**cached)

        # Build correction prompt
        prompt = self._build_correction_prompt(test_case, quality_metrics, feature_context)

        try:
            # Call LLM for correction
            response = self.llm.generate_json(
                prompt=prompt,
                system_prompt=self.CORRECTION_SYSTEM_PROMPT,
                temperature=0.1  # Low temperature for determinism
            )

            if response and isinstance(response, dict):
                corrected_test = self._merge_correction(test_case, response)
                changes = self._identify_changes(test_case, corrected_test)

                result = CorrectionResult(
                    original_test=test_case,
                    corrected_test=corrected_test,
                    changes_made=changes,
                    quality_before=quality_before,
                    quality_after=0.0,  # Will be recalculated by caller
                    confidence=0.8 if changes else 1.0
                )

                # Cache result
                if self.cache:
                    self.cache.set(cache_key, result.__dict__)

                return result

        except Exception as e:
            print(f"LLM correction failed: {e}")

        # Return unchanged if correction fails
        return CorrectionResult(
            original_test=test_case,
            corrected_test=test_case,
            changes_made=[],
            quality_before=quality_before,
            quality_after=quality_before,
            confidence=0.0
        )

    def enhance_step(
        self,
        action: str,
        expected: str,
        feature_name: str,
        step_context: Optional[str] = None
    ) -> Dict[str, str]:
        """Enhance a single step using LLM."""
        # Check if enhancement is needed
        if not self._needs_enhancement(action, expected):
            return {"action": action, "expected": expected}

        # Check cache
        cache_key = self._get_step_cache_key(action, expected, feature_name)
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached

        prompt = self.STEP_ENHANCEMENT_PROMPT.format(
            feature_name=feature_name,
            context=step_context or "General test step",
            action=action,
            expected=expected
        )

        try:
            response = self.llm.generate_json(
                prompt=prompt,
                temperature=0.1
            )

            if response and isinstance(response, dict):
                enhanced = {
                    "action": response.get("action", action),
                    "expected": response.get("expected", expected)
                }

                # Cache result
                if self.cache:
                    self.cache.set(cache_key, enhanced)

                return enhanced

        except Exception as e:
            print(f"Step enhancement failed: {e}")

        return {"action": action, "expected": expected}

    def _build_correction_prompt(
        self,
        test_case: Dict,
        metrics: TestCaseQualityMetrics,
        context: Optional[str]
    ) -> str:
        """Build the correction prompt for LLM."""
        issues = []
        for idx, step_metric in enumerate(metrics.step_metrics):
            if step_metric.has_generic_phrases:
                issues.append(f"Step {idx + 1}: Contains generic phrases")
            if step_metric.action_specificity < 0.5:
                issues.append(f"Step {idx + 1}: Action not specific enough")
            if step_metric.expected_observability < 0.5:
                issues.append(f"Step {idx + 1}: Expected result not observable")

        prompt = f"""Correct this test case to improve quality.

TEST CASE:
Title: {test_case.get('title', '')}
Objective: {test_case.get('objective', '')}

STEPS:
"""
        for idx, step in enumerate(test_case.get('steps', [])):
            prompt += f"{idx + 1}. Action: {step.get('action', '')}\n"
            prompt += f"   Expected: {step.get('expected', '')}\n"

        prompt += f"""
ISSUES FOUND:
{chr(10).join('- ' + issue for issue in issues)}

CONTEXT:
{context or 'Software application testing'}

Return corrected test case as JSON with same structure:
{{
    "title": "...",
    "objective": "...",
    "steps": [
        {{"action": "...", "expected": "..."}},
        ...
    ]
}}"""
        return prompt

    def _merge_correction(self, original: Dict, correction: Dict) -> Dict:
        """Merge LLM correction with original test case."""
        corrected = original.copy()

        # Update title if improved
        if correction.get('title'):
            corrected['title'] = correction['title']

        # Update objective if improved
        if correction.get('objective'):
            corrected['objective'] = correction['objective']

        # Update steps
        if correction.get('steps'):
            original_steps = original.get('steps', [])
            corrected_steps = correction.get('steps', [])

            # Match by index, keeping original structure
            merged_steps = []
            for idx in range(max(len(original_steps), len(corrected_steps))):
                if idx < len(original_steps):
                    orig_step = original_steps[idx]
                    if idx < len(corrected_steps):
                        corr_step = corrected_steps[idx]
                        merged_steps.append({
                            'action': corr_step.get('action', orig_step.get('action', '')),
                            'expected': corr_step.get('expected', orig_step.get('expected', ''))
                        })
                    else:
                        merged_steps.append(orig_step)
                elif idx < len(corrected_steps):
                    merged_steps.append(corrected_steps[idx])

            corrected['steps'] = merged_steps

        # Preserve ID
        corrected['id'] = original.get('id', '')

        return corrected

    def _identify_changes(self, original: Dict, corrected: Dict) -> List[str]:
        """Identify changes made during correction."""
        changes = []

        if original.get('title') != corrected.get('title'):
            changes.append("Title updated")

        if original.get('objective') != corrected.get('objective'):
            changes.append("Objective updated")

        orig_steps = original.get('steps', [])
        corr_steps = corrected.get('steps', [])

        for idx in range(min(len(orig_steps), len(corr_steps))):
            if orig_steps[idx].get('action') != corr_steps[idx].get('action'):
                changes.append(f"Step {idx + 1} action updated")
            if orig_steps[idx].get('expected') != corr_steps[idx].get('expected'):
                changes.append(f"Step {idx + 1} expected result updated")

        return changes

    def _needs_enhancement(self, action: str, expected: str) -> bool:
        """Check if a step needs enhancement."""
        generic_patterns = [
            "works as expected",
            "perform the action",
            "perform action",
            "as expected",
            "is completed successfully",
            "works correctly",
        ]

        text = (action + " " + expected).lower()
        return any(pattern in text for pattern in generic_patterns)

    def _get_cache_key(self, test_case: Dict) -> str:
        """Generate cache key for test case."""
        content = json.dumps(test_case, sort_keys=True)
        return f"tc_correction_{hashlib.sha256(content.encode()).hexdigest()[:16]}"

    def _get_step_cache_key(self, action: str, expected: str, feature: str) -> str:
        """Generate cache key for step enhancement."""
        content = f"{action}|{expected}|{feature}"
        return f"step_enhance_{hashlib.sha256(content.encode()).hexdigest()[:16]}"


class BatchTestCorrector:
    """Batch corrector for processing multiple test cases efficiently."""

    def __init__(
        self,
        corrector: LLMTestCorrector,
        quality_analyzer: Any,
        min_quality: float = 0.6
    ):
        """
        Initialize batch corrector.

        Args:
            corrector: LLM test corrector instance
            quality_analyzer: Quality analyzer instance
            min_quality: Minimum quality score to accept without correction
        """
        self.corrector = corrector
        self.analyzer = quality_analyzer
        self.min_quality = min_quality

    def correct_test_cases(
        self,
        test_cases: List[Dict],
        feature_context: Optional[str] = None
    ) -> List[CorrectionResult]:
        """
        Correct multiple test cases.

        Args:
            test_cases: List of test case dictionaries
            feature_context: Optional context about the feature

        Returns:
            List of correction results
        """
        results = []

        for test_case in test_cases:
            # Analyze quality
            metrics = self.analyzer.analyze_test_case(test_case)

            # Skip if already high quality
            if metrics.overall_score >= self.min_quality:
                results.append(CorrectionResult(
                    original_test=test_case,
                    corrected_test=test_case,
                    changes_made=[],
                    quality_before=metrics.overall_score,
                    quality_after=metrics.overall_score,
                    confidence=1.0
                ))
                continue

            # Correct low quality tests
            result = self.corrector.correct_test_case(
                test_case, metrics, feature_context
            )

            # Re-analyze corrected test
            if result.changes_made:
                new_metrics = self.analyzer.analyze_test_case(result.corrected_test)
                result.quality_after = new_metrics.overall_score

            results.append(result)

        return results

    def get_quality_report(self, results: List[CorrectionResult]) -> Dict:
        """Generate quality improvement report."""
        total = len(results)
        corrected = sum(1 for r in results if r.changes_made)
        avg_before = sum(r.quality_before for r in results) / total if total else 0
        avg_after = sum(r.quality_after for r in results) / total if total else 0

        return {
            "total_test_cases": total,
            "corrected_count": corrected,
            "unchanged_count": total - corrected,
            "average_quality_before": round(avg_before, 2),
            "average_quality_after": round(avg_after, 2),
            "quality_improvement": round(avg_after - avg_before, 2),
            "correction_rate": round(corrected / total * 100, 1) if total else 0
        }
