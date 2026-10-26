"""
Deterministic output quality gate.

The LLM judge is a second opinion, not a guarantee: it can be unavailable,
return malformed JSON, or grade differently between runs. This gate applies
fixed rules to the FINAL test cases so every generation ends with a
reproducible verdict that does not depend on any model. It reads only the
project config, so the same rules hold for desktop, tablet and web projects.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field

from core.services.platform_scope import platforms_mentioned

CRITICAL, MAJOR, MINOR = "critical", "major", "minor"

_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"|‘[^’]*’|“[^”]*”")
_WORDS = re.compile(r"[a-z0-9']+")
_NEGATIONS = frozenset({
    "no", "not", "without", "never", "neither", "nor", "none", "nothing",
    "cannot", "can't", "doesn't", "don't", "isn't", "aren't", "won't",
})
# "or" followed by these words is a threshold, not an alternative outcome
_THRESHOLD_WORDS = frozenset({
    "more", "less", "later", "earlier", "higher", "lower", "above", "below",
    "greater", "fewer", "newer", "older",
})
_CONDITIONAL = re.compile(
    r"^\s*if\b|\bif\s+(?:available|supported|applicable|needed|necessary|present"
    r"|possible|prompted|required|desired)\b|\boptionally\b|\bwhere\s+applicable\b"
    r"|\band/or\b|\beither\b",
    re.IGNORECASE,
)
_VAGUE_EXPECTED: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"\bas expected\b", re.IGNORECASE), "as expected"),
    (re.compile(r"\bworks?\s+(?:correctly|properly|as intended|fine)\b", re.IGNORECASE),
     "works correctly"),
    (re.compile(r"\b(?:displayed|displays|shown|shows|rendered|renders|handled|handles"
                r"|processed|applied|behaves|functions|responds)\s+(?:correctly|properly"
                r"|appropriately|as intended)\b", re.IGNORECASE),
     "displayed correctly"),
    (re.compile(r"\bappropriate(?:ly)?\b", re.IGNORECASE), "appropriate"),
    (re.compile(r"\betc\b\.?", re.IGNORECASE), "etc."),
    (re.compile(r"\b(?:TBD|TODO)\b"), "TBD/TODO"),
    (re.compile(r"\bmatches\s+the\s+(?:approved|expected|correct|required)\s+(?:version"
                r"|design|specification|spec|document|behaviou?r)\b", re.IGNORECASE),
     "comparison with no stated reference"),
    (re.compile(r"\b(?:is|are)\s+(?:confirmed\s+to\s+be\s+)?the\s+(?:correct|right|expected"
                r"|proper)\s+(?:approved\s+)?(?:version|document|file|content)\b", re.IGNORECASE),
     "'the correct version' with no stated reference"),
    (re.compile(r"\breflects?\s+the\s+(?:approved|expected|required|correct|latest)\s+"
                r"(?:changes|version|content|updates)\b", re.IGNORECASE),
     "'reflects the approved changes' without naming a change"),
)
_VERIFY_ACTION = re.compile(
    r"^\s*(?:verify|confirm|validate|ensure)\b|^\s*check\s+(?:that|whether|if)\b",
    re.IGNORECASE,
)


@dataclass
class GateFinding:
    test_case_id: str
    rule: str
    severity: str
    location: str
    message: str
    text: str = ""


@dataclass
class GateReport:
    findings: list[GateFinding] = field(default_factory=list)
    story_platforms: list[str] = field(default_factory=list)

    def count(self, severity: str) -> int:
        return sum(1 for f in self.findings if f.severity == severity)

    @property
    def passed(self) -> bool:
        return self.count(CRITICAL) == 0 and self.count(MAJOR) == 0

    def summary_line(self) -> str:
        return (f"{len(self.findings)} findings ({self.count(CRITICAL)} critical, "
                f"{self.count(MAJOR)} major, {self.count(MINOR)} minor)")

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "critical_count": self.count(CRITICAL),
            "major_count": self.count(MAJOR),
            "minor_count": self.count(MINOR),
            "story_platforms": self.story_platforms,
            "findings": [asdict(f) for f in self.findings],
        }


def offers_alternatives(text: str) -> bool:
    """True when ``text`` uses "or" to offer alternatives.

    Quoted UI labels, negated lists ("no errors or warnings", "no critical
    issues related to access or display") and thresholds ("1.0.246 or later")
    are not alternatives. A negation anywhere earlier in the same clause
    counts.
    """
    stripped = _QUOTED.sub(" ", text or "").lower()
    for clause in re.split(r"[.;:!?]", stripped):
        words = _WORDS.findall(clause)
        for i, word in enumerate(words):
            if word != "or":
                continue
            if any(w in _NEGATIONS for w in words[:i]):
                continue
            if i + 1 < len(words) and words[i + 1] in _THRESHOLD_WORDS:
                continue
            return True
    return False


def _is_accessibility_test(tc: dict) -> bool:
    return "/ accessibility /" in tc.get("title", "").lower()


def _term_pattern(term: str) -> re.Pattern:
    return re.compile(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", re.IGNORECASE)


class OutputQualityGate:
    """Rule-based checks over final test cases, driven only by project config."""

    def __init__(
        self,
        app_config,
        rules=None,
        story_platforms: Sequence[str] | None = None,
        ac_count: int = 0,
    ):
        self.app = app_config
        self.story_platforms = list(story_platforms or [])
        self.ac_count = ac_count
        self.platform_aliases = getattr(app_config, "platform_aliases", None) or {}
        self._ui_terms = [
            (t, _term_pattern(t)) for t in getattr(app_config, "forbidden_ui_terms", []) or []
        ]
        covered = {"or", "if available", "if supported", "if applicable", "as expected",
                   "works correctly", "appropriate", "etc.", "tbd", "todo"}
        self._words = [
            (w, _term_pattern(w))
            for w in (getattr(rules, "forbidden_words", []) or [])
            if w and not re.match(r"^\s*or\b", w, re.IGNORECASE) and w.lower() not in covered
        ]

    def run(self, test_cases: list[dict]) -> GateReport:
        report = GateReport(story_platforms=self.story_platforms)
        seen_signatures: dict[tuple, str] = {}
        for tc in test_cases:
            self._check_test(tc, report, seen_signatures)
        self._check_platform_coverage(test_cases, report)
        self._check_traceability(test_cases, report)
        return report

    def _add(self, report, tc_id, rule, severity, location, message, text=""):
        report.findings.append(GateFinding(tc_id, rule, severity, location, message, text[:200]))

    def _check_test(self, tc: dict, report: GateReport, seen: dict) -> None:
        tc_id = tc.get("id", "?")
        steps = tc.get("steps") or []
        if not steps:
            self._add(report, tc_id, "no_steps", CRITICAL, "steps", "Test case has no steps.")
            return

        blob = " ".join([tc.get("title", ""), tc.get("objective", "")] + [
            f"{s.get('action', '')} {s.get('expected', '')}" for s in steps
        ])
        for term, pattern in self._ui_terms:
            if pattern.search(blob):
                self._add(report, tc_id, "forbidden_ui_term", CRITICAL, "test",
                          f"Uses '{term}', which the project config says does not exist.", term)

        last = len(steps) - 1
        for i, step in enumerate(steps):
            action = (step.get("action") or "").strip()
            expected = (step.get("expected") or "").strip()
            loc = f"step_{i + 1}"
            if offers_alternatives(action):
                self._add(report, tc_id, "alternative_action", CRITICAL, f"{loc}_action",
                          "Action offers alternatives; give one instruction.", action)
            if _CONDITIONAL.search(action) and not action.lower().startswith("pre-req"):
                self._add(report, tc_id, "conditional_action", CRITICAL, f"{loc}_action",
                          "Action is conditional; make the precondition a Pre-req.", action)
            if expected and offers_alternatives(expected):
                self._add(report, tc_id, "ambiguous_expected", MAJOR, f"{loc}_expected",
                          "Expected result offers alternative outcomes; state one.", expected)
            for pattern, label in _VAGUE_EXPECTED:
                if expected and pattern.search(expected):
                    self._add(report, tc_id, "unverifiable_expected", MAJOR, f"{loc}_expected",
                              f"Expected result is not objectively checkable ('{label}').",
                              expected)
                    break
            for word, pattern in self._words:
                if pattern.search(action) or pattern.search(expected):
                    self._add(report, tc_id, "forbidden_word", MAJOR, loc,
                              f"Uses forbidden wording '{word}'.", f"{action} | {expected}")
            is_prereq = action.lower().startswith("pre-req")
            if 0 < i < last and not expected and not is_prereq:
                self._add(report, tc_id, "empty_expected", MAJOR, f"{loc}_expected",
                          "Middle step has no expected result.", action)
            if _VERIFY_ACTION.search(action):
                self._add(report, tc_id, "verify_in_action", MINOR, f"{loc}_action",
                          "Action is a verification; describe what the tester does.", action)

        signature = tuple(
            (re.sub(r"\s+", " ", (s.get("action") or "").lower()).strip(),
             re.sub(r"\s+", " ", (s.get("expected") or "").lower()).strip())
            for s in steps
        )
        if signature in seen:
            self._add(report, tc_id, "duplicate_test", MINOR, "steps",
                      f"Same steps and expected results as {seen[signature]}.")
        else:
            seen[signature] = tc_id

    def _check_platform_coverage(self, test_cases: list[dict], report: GateReport) -> None:
        if len(self.story_platforms) <= 1:
            return
        covered: set[str] = set()
        for tc in test_cases:
            if _is_accessibility_test(tc):
                continue  # an accessibility check is not functional coverage
            text = " ".join([tc.get("title", "")] + [
                f"{s.get('action', '')} {s.get('expected', '')}" for s in tc.get("steps") or []
            ])
            covered.update(platforms_mentioned(
                text, self.story_platforms, self.platform_aliases, include_generic=False))
        for platform in self.story_platforms:
            if platform not in covered:
                self._add(report, "*", "missing_platform", MAJOR, platform,
                          f"The story is in scope for {platform} but no functional test "
                          f"exercises it.")

    def _check_traceability(self, test_cases: list[dict], report: GateReport) -> None:
        if not any("ac_refs" in tc for tc in test_cases):
            return  # output predates traceability; nothing to check
        cited: set[int] = set()
        for tc in test_cases:
            if _is_accessibility_test(tc):
                continue
            refs = tc.get("ac_refs")
            valid = [r for r in refs or [] if isinstance(r, int) and 1 <= r <= self.ac_count]
            if not refs:
                self._add(report, tc.get("id", "?"), "untraced_test", MAJOR, "ac_refs",
                          "Test does not cite the acceptance criterion it verifies.")
            elif self.ac_count and len(valid) != len(refs):
                self._add(report, tc.get("id", "?"), "invalid_ac_ref", MAJOR, "ac_refs",
                          f"Cites AC numbers that do not exist: {refs}.")
            cited.update(valid)
        for n in range(1, self.ac_count + 1):
            if n not in cited:
                self._add(report, "*", "uncited_ac", MAJOR, f"AC{n}",
                          f"No test case cites AC{n}.")
