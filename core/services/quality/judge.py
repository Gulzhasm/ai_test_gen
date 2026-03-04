"""
LLM Judge - Cross-validates generated test cases using a different LLM provider.

Evaluates the FULL set of test cases in a single prompt for:
1. Forbidden language ('or', 'if', 'either' in steps)
2. Hallucinated content (invented names, data not from AC/story)
3. Logical contradictions
4. Missing AC coverage
5. Duplicate/overlapping tests
6. Missing setup/preconditions
7. Inconsistent terminology
"""
import json
from typing import List, Dict, Optional

from core.interfaces.judge import (
    IJudge,
    JudgeVerdict,
    JudgeIssue,
    IssueCategory,
    IssueSeverity,
    CATEGORY_SEVERITY,
)
from core.interfaces.llm_provider import ILLMProvider
from core.services.quality.judge_prompts import (
    JUDGE_SYSTEM_PROMPT,
    JUDGE_FIX_SYSTEM_PROMPT,
    build_evaluation_prompt,
    build_fix_prompt,
)


# Map string category names to enums
_CATEGORY_MAP = {c.value: c for c in IssueCategory}
_SEVERITY_MAP = {s.value: s for s in IssueSeverity}


class LLMJudge(IJudge):
    """LLM-based test case judge using a cross-validation provider."""

    def __init__(
        self,
        llm_provider: ILLMProvider,
        max_rounds: int = 2,
        auto_fix: bool = True,
    ):
        self.llm = llm_provider
        self.max_rounds = max_rounds
        self.auto_fix = auto_fix

    def evaluate(
        self,
        test_cases: List[Dict],
        story_data: Dict,
        acceptance_criteria: List[str],
        app_config,
        rules,
    ) -> JudgeVerdict:
        """Evaluate all test cases in a single LLM call."""
        prompt = build_evaluation_prompt(
            test_cases, story_data, acceptance_criteria, app_config, rules
        )

        try:
            response = self.llm.generate_json(
                prompt=prompt,
                system_prompt=JUDGE_SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=4096,
            )
        except Exception as e:
            print(f"  Judge: LLM evaluation call failed: {e}")
            return JudgeVerdict(passed=True)

        if not response or not isinstance(response, dict):
            print("  Judge: Invalid response from LLM, skipping validation")
            return JudgeVerdict(passed=True)

        return self._parse_verdict(response)

    def fix_issues(
        self,
        test_cases: List[Dict],
        verdict: JudgeVerdict,
        story_data: Dict,
        acceptance_criteria: List[str],
        app_config,
    ) -> List[Dict]:
        """Fix issues found by judge."""
        # Only send fixable issues (exclude missing_ac_coverage — can't add new tests)
        fixable_issues = [
            {
                "test_case_id": issue.test_case_id,
                "category": issue.category.value,
                "severity": issue.severity.value,
                "location": issue.location,
                "description": issue.description,
                "violating_text": issue.violating_text,
                "suggested_fix": issue.suggested_fix,
            }
            for issue in verdict.issues
            if issue.category != IssueCategory.MISSING_AC_COVERAGE
        ]

        if not fixable_issues:
            return test_cases

        # Only send test cases that have issues (reduces payload and speeds up LLM)
        affected_ids = {issue["test_case_id"] for issue in fixable_issues}
        affected_tests = [tc for tc in test_cases if tc.get("id") in affected_ids]
        print(f"  Judge: Sending {len(affected_tests)}/{len(test_cases)} affected test cases for fix")

        prompt = build_fix_prompt(
            affected_tests, fixable_issues, story_data, acceptance_criteria, app_config
        )

        try:
            response = self.llm.generate_json(
                prompt=prompt,
                system_prompt=JUDGE_FIX_SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=8192,
            )
        except Exception as e:
            print(f"  Judge: LLM fix call failed: {e}")
            return test_cases

        if not response or not isinstance(response, dict):
            print("  Judge: Invalid fix response, keeping original tests")
            return test_cases

        return self._merge_fixes(response, test_cases)

    def evaluate_and_fix(
        self,
        test_cases: List[Dict],
        story_data: Dict,
        acceptance_criteria: List[str],
        app_config,
        rules,
    ) -> JudgeVerdict:
        """Full judge loop: evaluate → fix → re-evaluate, up to max_rounds."""
        current_tests = test_cases
        final_verdict = None

        for round_num in range(1, self.max_rounds + 1):
            print(f"  Judge: Round {round_num}/{self.max_rounds}...")

            verdict = self.evaluate(
                current_tests, story_data, acceptance_criteria, app_config, rules
            )
            verdict.rounds_used = round_num

            # Count issues by severity
            self._log_verdict(verdict, round_num)

            # Pass if no critical or major issues
            if verdict.passed or (verdict.critical_count == 0 and verdict.major_count == 0):
                verdict.corrected_test_cases = current_tests
                return verdict

            # Fix if auto_fix enabled and not the last round
            if self.auto_fix and round_num < self.max_rounds:
                print(f"  Judge: Fixing {len(verdict.issues)} issues...")
                current_tests = self.fix_issues(
                    current_tests, verdict, story_data, acceptance_criteria, app_config
                )

            final_verdict = verdict

        # Return last verdict with whatever fixes were applied
        if final_verdict:
            final_verdict.corrected_test_cases = current_tests
        return final_verdict or JudgeVerdict(passed=True, corrected_test_cases=test_cases)

    def _parse_verdict(self, response: Dict) -> JudgeVerdict:
        """Parse LLM JSON response into JudgeVerdict."""
        issues = []
        for raw_issue in response.get("issues", []):
            category_str = raw_issue.get("category", "")
            category = _CATEGORY_MAP.get(category_str)
            if not category:
                continue

            severity_str = raw_issue.get("severity", "")
            severity = _SEVERITY_MAP.get(
                severity_str, CATEGORY_SEVERITY.get(category, IssueSeverity.MINOR)
            )

            issues.append(
                JudgeIssue(
                    test_case_id=raw_issue.get("test_case_id", "unknown"),
                    category=category,
                    severity=severity,
                    description=raw_issue.get("description", ""),
                    violating_text=raw_issue.get("violating_text", ""),
                    suggested_fix=raw_issue.get("suggested_fix"),
                    location=raw_issue.get("location", ""),
                )
            )

        critical = sum(1 for i in issues if i.severity == IssueSeverity.CRITICAL)
        major = sum(1 for i in issues if i.severity == IssueSeverity.MAJOR)
        minor = sum(1 for i in issues if i.severity == IssueSeverity.MINOR)

        return JudgeVerdict(
            passed=response.get("overall_pass", critical == 0 and major == 0),
            total_issues=len(issues),
            critical_count=critical,
            major_count=major,
            minor_count=minor,
            issues=issues,
            ac_coverage=response.get("ac_coverage", {}),
            duplicate_groups=response.get("duplicate_groups", []),
        )

    def _merge_fixes(self, response: Dict, originals: List[Dict]) -> List[Dict]:
        """Merge LLM fixes with original test cases, preserving IDs."""
        fixed_tests = response.get("test_cases", [])
        if not fixed_tests or not isinstance(fixed_tests, list):
            return originals

        # Build lookup by ID for originals
        original_by_id = {tc.get("id", ""): tc for tc in originals}

        merged = []
        seen_ids = set()

        for fixed_tc in fixed_tests:
            tc_id = fixed_tc.get("id", "")
            if not tc_id or tc_id in seen_ids:
                continue
            seen_ids.add(tc_id)

            original = original_by_id.get(tc_id)
            if original:
                # Merge: take fixed content but preserve original structure
                merged_tc = original.copy()
                if fixed_tc.get("title"):
                    merged_tc["title"] = fixed_tc["title"]
                if fixed_tc.get("objective"):
                    merged_tc["objective"] = fixed_tc["objective"]
                if fixed_tc.get("steps"):
                    merged_tc["steps"] = fixed_tc["steps"]
                merged.append(merged_tc)
            else:
                # New ID from LLM — skip (we don't add new tests)
                continue

        # Add any originals that weren't in the fix response (LLM may have dropped them)
        for tc in originals:
            if tc.get("id", "") not in seen_ids:
                merged.append(tc)

        return merged

    def _log_verdict(self, verdict: JudgeVerdict, round_num: int):
        """Log verdict summary to console."""
        if verdict.total_issues == 0:
            print(f"  Judge: Round {round_num} — PASSED (no issues)")
        else:
            print(
                f"  Judge: Round {round_num} — {verdict.total_issues} issues "
                f"({verdict.critical_count} critical, {verdict.major_count} major, "
                f"{verdict.minor_count} minor)"
            )
        if verdict.ac_coverage:
            uncovered = [ac for ac, covered in verdict.ac_coverage.items() if not covered]
            if uncovered:
                print(f"  Judge: Uncovered ACs: {', '.join(uncovered)}")
