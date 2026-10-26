"""
LLM Judge - Cross-validates generated test cases using a different LLM provider.

Evaluates the FULL set of test cases in a single prompt (see judge_prompts for
the categories). Reliability rules:

- Fail closed: if the judge cannot produce a verdict, the result is marked
  ``evaluated=False`` and never counts as a pass.
- The pass/fail decision is computed from the parsed issues, not taken from the
  model's own ``overall_pass`` flag.
- Unknown categories are kept as ``other`` instead of being dropped.
- Every saved version has been evaluated: fixes are only applied when a later
  round can re-evaluate them, and the best-scoring evaluated version wins, so a
  fix that makes things worse is discarded.
- ACs the judge marks as uncovered are handed to an optional gap filler, which
  adds tests that the next round evaluates.
"""
from collections.abc import Callable

from core.interfaces.judge import (
    CATEGORY_SEVERITY,
    IJudge,
    IssueCategory,
    IssueSeverity,
    JudgeIssue,
    JudgeVerdict,
)
from core.interfaces.llm_provider import ILLMProvider
from core.services.quality.judge_prompts import (
    JUDGE_FIX_SYSTEM_PROMPT,
    JUDGE_SYSTEM_PROMPT,
    build_evaluation_prompt,
    build_fix_prompt,
)

# Map string category names to enums
_CATEGORY_MAP = {c.value: c for c in IssueCategory}
_SEVERITY_MAP = {s.value: s for s in IssueSeverity}

# (uncovered [(ac_number, ac_text)], current tests) -> new tests to append
GapFiller = Callable[[list[tuple[int, str]], list[dict]], list[dict]]


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1", "covered"}


def _valid_test_case(tc) -> bool:
    steps = tc.get("steps") if isinstance(tc, dict) else None
    return bool(steps) and isinstance(steps, list) and all(
        isinstance(s, dict) and str(s.get("action", "")).strip() for s in steps
    )


class LLMJudge(IJudge):
    """LLM-based test case judge using a cross-validation provider."""

    def __init__(
        self,
        llm_provider: ILLMProvider,
        max_rounds: int = 2,
        auto_fix: bool = True,
        fixer_provider: ILLMProvider | None = None,
        gap_filler: GapFiller | None = None,
        rule_checker: Callable[[list[dict]], tuple[list[JudgeIssue], list[str]]] | None = None,
    ):
        # Cross-validation: the judge LLM evaluates; a SEPARATE LLM (the corrector,
        # which authored the content) applies fixes. Keeping evaluate and fix on
        # different models preserves independence — the judge never grades its own
        # fix. Falls back to the judge LLM only if no fixer is provided.
        self.llm = llm_provider
        self.fixer = fixer_provider or llm_provider
        self.max_rounds = max(1, max_rounds)
        self.auto_fix = auto_fix
        self.gap_filler = gap_filler
        # Deterministic reviewer rules: (tests) -> (issues, uncovered AC numbers).
        # Merged into every evaluated verdict so rule violations always block a
        # pass and reach the fixer, whatever the judge model noticed.
        self.rule_checker = rule_checker

    def evaluate(
        self,
        test_cases: list[dict],
        story_data: dict,
        acceptance_criteria: list[str],
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
                max_tokens=8192,
            )
        except Exception as e:  # noqa: BLE001 - provider SDKs raise many types
            return JudgeVerdict(passed=False, evaluated=False,
                                error=f"evaluation call failed: {e}")

        if not response or not isinstance(response, dict):
            return JudgeVerdict(passed=False, evaluated=False,
                                error="judge returned no parseable JSON verdict")

        verdict = self._parse_verdict(response)
        if self.rule_checker:
            self._merge_rule_findings(verdict, test_cases)
        return verdict

    def _merge_rule_findings(self, verdict: JudgeVerdict, test_cases: list[dict]) -> None:
        try:
            rule_issues, uncovered = self.rule_checker(test_cases)
        except Exception as e:  # noqa: BLE001 - a checker bug must not hide the LLM verdict
            print(f"  Judge: rule checker failed: {e}")
            return
        seen = {(i.test_case_id, i.location, i.violating_text) for i in verdict.issues}
        for issue in rule_issues:
            if (issue.test_case_id, issue.location, issue.violating_text) not in seen:
                verdict.issues.append(issue)
        for ac in uncovered:
            verdict.ac_coverage[str(ac)] = False
        verdict.critical_count = sum(1 for i in verdict.issues if i.severity == IssueSeverity.CRITICAL)
        verdict.major_count = sum(1 for i in verdict.issues if i.severity == IssueSeverity.MAJOR)
        verdict.minor_count = sum(1 for i in verdict.issues if i.severity == IssueSeverity.MINOR)
        verdict.total_issues = len(verdict.issues)
        verdict.passed = verdict.critical_count == 0 and verdict.major_count == 0
        if rule_issues:
            print(f"  Judge: + {len(rule_issues)} reviewer-rule findings")

    def fix_issues(
        self,
        test_cases: list[dict],
        verdict: JudgeVerdict,
        story_data: dict,
        acceptance_criteria: list[str],
        app_config,
    ) -> list[dict]:
        """Fix issues found by judge. Returns ``test_cases`` unchanged on failure."""
        known_ids = {tc.get("id") for tc in test_cases}
        # A missing_ac_coverage issue on an existing test (a compound AC half
        # covered) can be fixed by adding steps; a wholly uncovered AC cannot and
        # goes to the gap filler instead.
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
            if issue.test_case_id in known_ids
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
            response = self.fixer.generate_json(
                prompt=prompt,
                system_prompt=JUDGE_FIX_SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=16000,
            )
        except Exception as e:  # noqa: BLE001 - provider SDKs raise many types
            print(f"  Judge: LLM fix call failed: {e}")
            return test_cases

        if isinstance(response, list):  # tolerate a bare array
            response = {"test_cases": response}
        if not response or not isinstance(response, dict):
            print("  Judge: Invalid fix response, keeping original tests")
            return test_cases

        return self._merge_fixes(response, test_cases)

    def evaluate_and_fix(
        self,
        test_cases: list[dict],
        story_data: dict,
        acceptance_criteria: list[str],
        app_config,
        rules,
    ) -> JudgeVerdict:
        """Evaluate → repair → re-evaluate, returning the best evaluated version.

        ``max_rounds`` is the number of evaluations. A repair is only made when
        another evaluation will check it, so the returned tests always match the
        returned verdict.
        """
        current = test_cases
        best_tests: list[dict] | None = None
        best: JudgeVerdict | None = None
        last: JudgeVerdict | None = None
        evaluations = 0

        for round_num in range(1, self.max_rounds + 1):
            print(f"  Judge: Round {round_num}/{self.max_rounds}...")
            verdict = self.evaluate(
                current, story_data, acceptance_criteria, app_config, rules
            )
            last = verdict
            if not verdict.evaluated:
                print(f"  Judge: {verdict.error} — this version is NOT cross-validated")
                break
            evaluations = round_num
            self._log_verdict(verdict, round_num)

            if best is None or verdict.score < best.score:
                best_tests, best = current, verdict
            else:
                print(f"  Judge: Round {round_num} did not improve on the best version "
                      f"(score {verdict.score} vs {best.score}); discarding its changes")

            if verdict.passed and not verdict.uncovered_acs:
                break
            if not self.auto_fix or round_num == self.max_rounds:
                break

            repaired = self._repair(
                best_tests, best, story_data, acceptance_criteria, app_config
            )
            if repaired is best_tests:
                print("  Judge: No repair could be applied; stopping")
                break
            current = repaired

        if best is None:
            failed = last or JudgeVerdict(passed=False, evaluated=False,
                                          error="judge did not run")
            failed.passed = False
            failed.corrected_test_cases = test_cases
            return failed

        best.rounds_used = evaluations
        best.corrected_test_cases = best_tests
        return best

    def _repair(
        self,
        test_cases: list[dict],
        verdict: JudgeVerdict,
        story_data: dict,
        acceptance_criteria: list[str],
        app_config,
    ) -> list[dict]:
        """Apply fixes and fill coverage gaps. Returns the input list when nothing changed."""
        repaired = test_cases
        fixer_name = "corrector" if self.fixer is not self.llm else "judge"
        if verdict.issues:
            print(f"  Judge: Fixing {len(verdict.issues)} issues via {fixer_name} LLM...")
            repaired = self.fix_issues(
                test_cases, verdict, story_data, acceptance_criteria, app_config
            )

        uncovered = []
        for key in verdict.uncovered_acs:
            try:
                n = int(str(key).strip().lstrip("ACac"))
            except ValueError:
                continue
            if 1 <= n <= len(acceptance_criteria):
                uncovered.append((n, acceptance_criteria[n - 1]))
        if uncovered and self.gap_filler:
            print(f"  Judge: Generating tests for {len(uncovered)} uncovered AC(s)...")
            try:
                new_tests = self.gap_filler(uncovered, list(repaired))
            except Exception as e:  # noqa: BLE001 - gap filling is best effort
                print(f"  Judge: Gap filling failed: {e}")
                new_tests = []
            if new_tests:
                repaired = list(repaired) + list(new_tests)
        return repaired

    def _parse_verdict(self, response: dict) -> JudgeVerdict:
        """Parse LLM JSON response into JudgeVerdict."""
        issues = []
        for raw_issue in response.get("issues") or []:
            if not isinstance(raw_issue, dict):
                continue
            category_str = str(raw_issue.get("category", "")).strip().lower()
            category = _CATEGORY_MAP.get(category_str, IssueCategory.OTHER)
            severity = _SEVERITY_MAP.get(
                str(raw_issue.get("severity", "")).strip().lower(),
                CATEGORY_SEVERITY.get(category, IssueSeverity.MINOR),
            )
            description = str(raw_issue.get("description", ""))
            if category is IssueCategory.OTHER and category_str not in ("", "other"):
                description = f"[{category_str}] {description}"

            issues.append(
                JudgeIssue(
                    test_case_id=str(raw_issue.get("test_case_id", "unknown")),
                    category=category,
                    severity=severity,
                    description=description,
                    violating_text=str(raw_issue.get("violating_text", "") or ""),
                    suggested_fix=raw_issue.get("suggested_fix"),
                    location=str(raw_issue.get("location", "") or ""),
                )
            )

        critical = sum(1 for i in issues if i.severity == IssueSeverity.CRITICAL)
        major = sum(1 for i in issues if i.severity == IssueSeverity.MAJOR)
        minor = sum(1 for i in issues if i.severity == IssueSeverity.MINOR)

        raw_coverage = response.get("ac_coverage")
        ac_coverage = (
            {str(k): _as_bool(v) for k, v in raw_coverage.items()}
            if isinstance(raw_coverage, dict) else {}
        )
        groups = response.get("duplicate_groups")

        return JudgeVerdict(
            # Computed, not trusted: models often say overall_pass=true while
            # listing critical issues.
            passed=critical == 0 and major == 0,
            total_issues=len(issues),
            critical_count=critical,
            major_count=major,
            minor_count=minor,
            issues=issues,
            ac_coverage=ac_coverage,
            duplicate_groups=groups if isinstance(groups, list) else [],
        )

    def _merge_fixes(self, response: dict, originals: list[dict]) -> list[dict]:
        """Merge LLM fixes into the originals, preserving IDs, order and extra fields."""
        fixed_tests = response.get("test_cases", [])
        if not fixed_tests or not isinstance(fixed_tests, list):
            return originals

        fixed_by_id = {}
        for fixed_tc in fixed_tests:
            if isinstance(fixed_tc, dict) and fixed_tc.get("id") and _valid_test_case(fixed_tc):
                fixed_by_id.setdefault(fixed_tc["id"], fixed_tc)

        merged = []
        changed = False
        for original in originals:
            fixed_tc = fixed_by_id.get(original.get("id", ""))
            if not fixed_tc:
                # Not returned, or returned malformed — keep the original
                merged.append(original)
                continue
            merged_tc = original.copy()
            for key in ("title", "objective", "steps"):
                if fixed_tc.get(key):
                    merged_tc[key] = fixed_tc[key]
            changed = changed or merged_tc != original
            merged.append(merged_tc)

        return merged if changed else originals

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
        if verdict.uncovered_acs:
            print(f"  Judge: Uncovered ACs: {', '.join(verdict.uncovered_acs)}")
