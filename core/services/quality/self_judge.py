"""
Self-Judge — lightweight self-review using the SAME LLM that generated/corrected
the test cases.  Runs ONE round before the cross-LLM Gemini judge to catch the
obvious issues cheaply:  duplication, missing AC coverage, logic-flow errors,
forbidden language that slipped through correction, and hallucinated objectives.

Architecture:  Generate → LLM Correct → **Self-Judge** → Gemini Judge → CSV
"""
import json
from typing import List, Dict

from core.interfaces.judge import (
    JudgeVerdict,
    JudgeIssue,
    IssueCategory,
    IssueSeverity,
    CATEGORY_SEVERITY,
)
from core.interfaces.llm_provider import ILLMProvider


# ── Prompt templates ────────────────────────────────────────────────

SELF_JUDGE_SYSTEM_PROMPT = """You are reviewing test cases that YOU just generated. \
Perform a quick, honest self-check before an independent reviewer sees them.

Focus on these 8 checks (in priority order):

1. HALLUCINATED / UNGROUNDED TESTS (Critical — flag for REMOVAL)
   Every test case's objective AND steps must trace back to a specific AC or the story description.
   If a test covers behaviour NOT found in ANY AC, flag the ENTIRE test for removal.  Examples:
   - "State persistence across app restarts" — if no AC mentions persistence, REMOVE it.
   - "Rapid toggling" / "stress test" — if no AC mentions performance, REMOVE it.
   - "Multiple methods (keyboard shortcut)" — if an AC explicitly says hotkeys/shortcuts are OUT OF SCOPE, REMOVE it.
   - "Layout consistency after toggle" — if this is already covered by another test (e.g., "hidden panel does not occupy space"), REMOVE the duplicate.
   Be strict: if you cannot point to a specific AC number that the test validates, flag it as hallucinated_content with severity critical and suggested_fix "REMOVE".

2. OUT-OF-SCOPE TESTS (Critical — flag for REMOVAL)
   Read the ACs carefully for explicit exclusions like "out of scope", "not supported", "not in this phase".
   If a test exercises something that an AC explicitly excludes, flag for removal.
   Example: AC says "Hotkeys and tooltips are out of scope for Phase 1" → any test using keyboard shortcuts to toggle the feature must be REMOVED.

3. DUPLICATE / OVERLAPPING TESTS (Critical)
   Compare every pair of test cases.  If two tests have ≥70% identical step \
sequences (same actions in same order), flag the less complete one for removal.
   Also flag tests that verify the same thing with different wording (e.g., \
"hidden panel no space" vs "layout after toggle" — same verification).

4. VERIFY IN ACTION STEPS (Major)
   Action steps must describe WHAT THE TESTER DOES (click, select, observe, navigate).
   Flag any action step that starts with "Verify", "Confirm", "Validate", or "Check".
   These words belong ONLY in the Expected Result column.
   suggested_fix: Replace "Verify X" with "Observe X" in action, move the verification to expected.

5. MISSING AC COVERAGE (Major)
   For EVERY acceptance criterion, at least one test case must have concrete steps \
(not just a title/objective mention) that exercise it.
   Flag each AC number that has NO covering steps.

6. LOGIC-FLOW ERRORS (Major)
   Check that toggle sequences make sense (e.g., if a panel is already visible, \
toggling it should HIDE it first, not show it again).
   Check that verification steps follow the action they verify.

7. FORBIDDEN LANGUAGE IN ACTIONS (Major)
   Action steps must not contain ambiguous "or" (e.g., "Click A or B"), \
"if available", "if supported", "either…or", "and/or", "optionally".
   Descriptive "or" in expected results (e.g., "no errors or warnings") is fine.

8. UNNECESSARY SETUP STEPS (Minor)
   If a test does NOT interact with canvas objects, it should NOT include \
"Draw a circle" / "Select the object" steps.  Flag bloated setup.

IMPORTANT:
- Be AGGRESSIVE about removing hallucinated/out-of-scope tests. It is better to have \
fewer high-quality tests than many low-quality ones.
- An empty issues list is perfectly valid if the tests are clean.
- Return ONLY valid JSON — no markdown, no commentary.
"""

SELF_JUDGE_FIX_SYSTEM_PROMPT = """You are fixing issues you found in your own test \
cases during self-review.  Apply ONLY the listed fixes — do not change anything else.

Rules:
- REMOVE hallucinated/ungrounded tests entirely: if suggested_fix says "REMOVE", \
do NOT include that test case in the output at all.  This is the most important rule.
- REMOVE out-of-scope tests entirely (same as above).
- Remove duplicate tests (keep the more complete version, drop the other).
- For "Verify" in action steps: replace "Verify X" / "Check X" / "Confirm X" with \
"Observe X" in the action field, and move the verification statement to expected result.
- For missing AC coverage: add steps to an existing test case, do NOT create new tests.
- Fix logic-flow errors (correct toggle order).
- Remove forbidden language by splitting ambiguous actions into separate steps.
- Remove unnecessary setup steps (draw/select object) from tests that don't need them.
- Preserve test case IDs for tests you keep.
- Return ONLY valid JSON matching the schema.
- The output "test_cases" array must contain ONLY the tests that should survive. \
Omitted tests are considered removed."""


def build_self_eval_prompt(
    test_cases: List[Dict],
    acceptance_criteria: List[str],
    story_title: str,
    story_description: str = "",
) -> str:
    """Build a compact evaluation prompt — much smaller than the full judge prompt."""

    ac_lines = [f"  {i}. {ac}" for i, ac in enumerate(acceptance_criteria, 1)]

    tc_json = json.dumps(test_cases, indent=2)

    return f"""## STORY
- Title: {story_title}
- Description: {(story_description or '')[:600]}

## ACCEPTANCE CRITERIA
{chr(10).join(ac_lines)}

## TEST CASES ({len(test_cases)} total)
```json
{tc_json}
```

## EXPECTED OUTPUT
Return JSON:
```json
{{
  "overall_pass": true/false,
  "issues": [
    {{
      "test_case_id": "...",
      "category": "duplicate_overlap|missing_ac_coverage|hallucinated_content|logical_contradiction|forbidden_language|missing_setup",
      "severity": "critical|major|minor",
      "location": "step_N_action|step_N_expected|objective|set_level",
      "description": "...",
      "violating_text": "...",
      "suggested_fix": "..."
    }}
  ],
  "ac_coverage": {{"1": true, "2": false, ...}},
  "duplicate_groups": [["id-A", "id-B"]]
}}
```

Set "overall_pass" to true ONLY if zero critical and zero major issues.
For "ac_coverage" use 1-based AC index → boolean."""


def build_self_fix_prompt(
    test_cases: List[Dict],
    issues: List[Dict],
    acceptance_criteria: List[str],
) -> str:
    """Build a compact fix prompt for self-judge."""

    ac_lines = [f"  {i}. {ac}" for i, ac in enumerate(acceptance_criteria, 1)]

    return f"""## ACCEPTANCE CRITERIA
{chr(10).join(ac_lines)}

## ISSUES TO FIX ({len(issues)} total)
```json
{json.dumps(issues, indent=2)}
```

## TEST CASES TO CORRECT
```json
{json.dumps(test_cases, indent=2)}
```

## EXPECTED OUTPUT
Return JSON with key "test_cases" containing the corrected array:
```json
{{
  "test_cases": [
    {{"id": "...", "title": "...", "objective": "...", "steps": [{{"action": "...", "expected": "..."}}]}}
  ]
}}
```
Fix ONLY the listed issues.  Preserve IDs.  Do NOT add new test cases."""


# ── Category / severity maps (reuse from judge interface) ──────────

_CATEGORY_MAP = {c.value: c for c in IssueCategory}
_SEVERITY_MAP = {s.value: s for s in IssueSeverity}


# ── Self-Judge class ───────────────────────────────────────────────

class SelfJudge:
    """Lightweight single-round self-review using the corrector's own LLM."""

    def __init__(self, llm_provider: ILLMProvider):
        self.llm = llm_provider

    # ── public API ──────────────────────────────────────────────────

    def evaluate_and_fix(
        self,
        test_cases: List[Dict],
        acceptance_criteria: List[str],
        story_title: str,
        story_description: str = "",
    ) -> JudgeVerdict:
        """Single-round: evaluate → fix → return verdict with corrected tests."""

        # 1. Evaluate
        print("  Self-judge: Reviewing test cases...")
        verdict = self._evaluate(
            test_cases, acceptance_criteria, story_title, story_description
        )
        self._log_verdict(verdict)

        if verdict.passed or (verdict.critical_count == 0 and verdict.major_count == 0):
            verdict.corrected_test_cases = test_cases
            return verdict

        # 2. Fix
        fixable = [
            {
                "test_case_id": i.test_case_id,
                "category": i.category.value,
                "severity": i.severity.value,
                "location": i.location,
                "description": i.description,
                "violating_text": i.violating_text,
                "suggested_fix": i.suggested_fix,
            }
            for i in verdict.issues
            if i.category != IssueCategory.MISSING_AC_COVERAGE
        ]

        if fixable:
            affected_ids = {iss["test_case_id"] for iss in fixable}
            affected_tests = [tc for tc in test_cases if tc.get("id") in affected_ids]

            # Identify tests flagged for removal (hallucinated/out-of-scope/duplicate)
            removal_ids = {
                iss["test_case_id"] for iss in fixable
                if iss.get("suggested_fix", "").upper() == "REMOVE"
                or iss.get("category") in ("hallucinated_content", "duplicate_overlap")
                and iss.get("severity") == "critical"
            }

            print(f"  Self-judge: Fixing {len(fixable)} issues in {len(affected_tests)} test cases...")
            if removal_ids:
                print(f"  Self-judge: Flagged {len(removal_ids)} test(s) for removal: {', '.join(sorted(removal_ids))}")

            fixed = self._fix(affected_tests, fixable, acceptance_criteria)
            test_cases = self._merge_fixes(fixed, test_cases, removal_ids)

        verdict.corrected_test_cases = test_cases
        verdict.rounds_used = 1
        return verdict

    # ── private helpers ─────────────────────────────────────────────

    def _evaluate(
        self,
        test_cases: List[Dict],
        acceptance_criteria: List[str],
        story_title: str,
        story_description: str,
    ) -> JudgeVerdict:
        prompt = build_self_eval_prompt(
            test_cases, acceptance_criteria, story_title, story_description
        )
        try:
            response = self.llm.generate_json(
                prompt=prompt,
                system_prompt=SELF_JUDGE_SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=4096,
            )
        except Exception as e:
            print(f"  Self-judge: Evaluation call failed: {e}")
            return JudgeVerdict(passed=True)

        if not response or not isinstance(response, dict):
            print("  Self-judge: Invalid response, skipping self-review")
            return JudgeVerdict(passed=True)

        return self._parse_verdict(response)

    def _fix(
        self,
        test_cases: List[Dict],
        issues: List[Dict],
        acceptance_criteria: List[str],
    ) -> Dict:
        prompt = build_self_fix_prompt(test_cases, issues, acceptance_criteria)
        try:
            response = self.llm.generate_json(
                prompt=prompt,
                system_prompt=SELF_JUDGE_FIX_SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=8192,
            )
        except Exception as e:
            print(f"  Self-judge: Fix call failed: {e}")
            return {}

        if not response or not isinstance(response, dict):
            print("  Self-judge: Invalid fix response, keeping originals")
            return {}

        return response

    def _parse_verdict(self, response: Dict) -> JudgeVerdict:
        issues = []
        for raw in response.get("issues", []):
            category = _CATEGORY_MAP.get(raw.get("category", ""))
            if not category:
                continue
            severity = _SEVERITY_MAP.get(
                raw.get("severity", ""),
                CATEGORY_SEVERITY.get(category, IssueSeverity.MINOR),
            )
            issues.append(
                JudgeIssue(
                    test_case_id=raw.get("test_case_id", "unknown"),
                    category=category,
                    severity=severity,
                    description=raw.get("description", ""),
                    violating_text=raw.get("violating_text", ""),
                    suggested_fix=raw.get("suggested_fix"),
                    location=raw.get("location", ""),
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

    def _merge_fixes(self, response: Dict, originals: List[Dict], removal_ids: set = None) -> List[Dict]:
        removal_ids = removal_ids or set()
        fixed_tests = response.get("test_cases", [])

        if not fixed_tests or not isinstance(fixed_tests, list):
            # Even if fix failed, still remove flagged tests
            if removal_ids:
                result = [tc for tc in originals if tc.get("id", "") not in removal_ids]
                print(f"  Self-judge: Removed {len(originals) - len(result)} test(s)")
                return result
            return originals

        # Build lookup of fixed tests
        fixed_by_id = {}
        for fixed_tc in fixed_tests:
            tc_id = fixed_tc.get("id", "")
            if tc_id and tc_id not in fixed_by_id:
                fixed_by_id[tc_id] = fixed_tc

        merged = []
        for tc in originals:
            tc_id = tc.get("id", "")

            # Skip tests flagged for removal (whether or not LLM included them)
            if tc_id in removal_ids and tc_id not in fixed_by_id:
                continue

            if tc_id in fixed_by_id:
                # Apply fixes from LLM response
                fixed_tc = fixed_by_id[tc_id]
                merged_tc = tc.copy()
                if fixed_tc.get("title"):
                    merged_tc["title"] = fixed_tc["title"]
                if fixed_tc.get("objective"):
                    merged_tc["objective"] = fixed_tc["objective"]
                if fixed_tc.get("steps"):
                    merged_tc["steps"] = fixed_tc["steps"]
                merged.append(merged_tc)
            else:
                # Unaffected test — keep as-is
                merged.append(tc)

        removed_count = len(originals) - len(merged)
        if removed_count > 0:
            print(f"  Self-judge: Removed {removed_count} test(s)")

        return merged

    def _log_verdict(self, verdict: JudgeVerdict):
        if verdict.total_issues == 0:
            print("  Self-judge: PASSED (no issues)")
        else:
            print(
                f"  Self-judge: Found {verdict.total_issues} issues "
                f"({verdict.critical_count} critical, {verdict.major_count} major, "
                f"{verdict.minor_count} minor)"
            )
        if verdict.ac_coverage:
            uncovered = [ac for ac, covered in verdict.ac_coverage.items() if not covered]
            if uncovered:
                print(f"  Self-judge: Uncovered ACs: {', '.join(uncovered)}")
