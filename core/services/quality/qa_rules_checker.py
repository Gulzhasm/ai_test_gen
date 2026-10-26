"""
QA Rules Checker - deterministic enforcement of the reviewer's test-case rules.

A human reviewer of a generated test plan found that test
cases invented menu paths, screens, fields, accounts and values; used lettered
roles (Admin A, User N, P1); mixed synonyms; packed several actions into one step;
asked QA to do team work (confirm, agree, approve); attributed evidence to the
developer; asked QA to change the database; and left TBD / bracket notes in the
text. Prompt instructions alone did not stop this, so these rules are checked in
code and the findings are fed back to the fixer and the judge.

Rules (numbering follows the reviewer's list):
 1  Use only the provided sources (story + linked requirement docs). Quoted text,
    DB identifiers and screen/field names must appear in a source or be defined
    in the test's own Pre-req.
 2  General role names, defined once in the Pre-req; no lettered/numbered roles.
 3  One term per concept (project glossary of banned synonyms).
 4  No legacy menu paths, counties, values or messages not in the sources.
 5  One imperative action per step; every step after the Pre-req has an expected
    result (a closing sign-out step may have none).
 6  Title "<ID>: Area / Component / Behavior"; TC IDs unchanged.
 7  Short Pre-req; no "is available" / "has been completed".
 8  No team work (confirm/agree/approve/discuss/check something is documented).
 9  Evidence review phrased "the provided evidence" - never "the developer's".
10  QA only reads the database.
11  No TBD / to be confirmed / proposed / bracket notes in test text.
12  Grammar: "No X, Y or Z" (no "nor"); one apostrophe style.
13  Keep coverage: every acceptance criterion is covered by at least one test.

The checker is source-aware: give it the full grounding text (story title,
description, acceptance criteria and any requirement documents) and it treats
anything found there as allowed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

ERROR = "error"
WARNING = "warning"


@dataclass
class RuleFinding:
    """One rule violation in one test case."""

    rule: str            # e.g. "R1", "R2"
    code: str            # short machine code, e.g. "ungrounded_quote"
    severity: str        # "error" | "warning"
    tc_id: str
    location: str        # "title", "objective", "step3.action", ...
    message: str
    evidence: str = ""

    def to_feedback(self) -> str:
        loc = f"{self.tc_id} {self.location}".strip()
        ev = f' ("{self.evidence}")' if self.evidence else ""
        return f"[{self.rule}] {loc}: {self.message}{ev}"


@dataclass
class QARulesConfig:
    """Project-tunable inputs. Every list is optional."""

    # Terms that come from a legacy system / old inventory and must not appear
    # unless the sources contain them (rule 4).
    legacy_terms: list[str] = field(default_factory=list)
    # Banned synonym -> preferred term (rule 3).
    synonyms: dict[str, str] = field(default_factory=dict)
    # Extra banned phrases (regex, case-insensitive) with the rule they break.
    extra_banned: list[tuple[str, str, str]] = field(default_factory=list)
    # Closing step that may have an empty expected result.
    closing_step_pattern: str = r"^Sign out\b"
    # Words in source text that make a team-work word legitimate (e.g. a UI
    # label "Confirm New Password"); matched against the sources automatically.
    pre_req_prefix: str = "Pre-req:"


# --- patterns ---------------------------------------------------------------

_LETTER_ROLE = [
    r"\b(?:Admin|User|Target User|Profile|Session|Agency|County|Establishment|Workstation|Account)\s[A-Z]\d?\b(?![-'\w])",
    r"\b[PR]\d\b",
    r"\bPwd-\w+",
    r"\b(?:NP|RP|IP|P0)\b",
    r"\b(?:Profiles?|Users?|Admins?)\s\d\b",
]
_TEAM_WORK = r"\b(?:confirm\w*|agree\w*|discuss\w*|sign-off|approv\w*|decision)\b"
_DOC_CHECK = r"\b(?:is|are|has been|have been|was|were)\s+(?:documented|recorded|agreed|approved|confirmed)\b"
_ATTRIBUTED = r"(?<!browser )\bdeveloper'?s?\b|\bdev team'?s\b"
_DB_WRITE = (r"\b(?:insert|update|delete|truncate|drop|alter|restore|lock|snapshot)\b[^.;]{0,60}"
             r"\b(?:table|row|rows|database|oracle|record|records|schema)\b")
_DB_WRITE_SAFE = r"\b(?:read-only|query|queries|compare|does not|do not|is not|are not|never|no )\b"
_INLINE_COMMENT = [r"\bTBD\b", r"\bto be confirmed\b", r"\bproposed\b", r"\bif applicable\b",
                   r"\bTODO\b", r"\be\.g\.", r"\bi\.e\."]
_PREREQ_BANNED = [r"\bis available\b", r"\bare available\b", r"\bhas been completed\b",
                  r"\bhave been completed\b", r"\bis provided\b", r"\bare provided\b"]
_IMPERATIVE_BAD_START = r"^(?:The|A|An|User|Admin|QA|It|This|Verify that)\b"
_COMPOUND = (r"\b(?:and|then)\s+(?:open|click|select|enter|type|press|search|sign|return|close|copy|"
             r"paste|navigate|review|compare|record|wait|refresh|submit|save|reload|move|go|use|repeat|attempt|try|change|edit|verify)\b")
_DB_IDENT = r"\b[A-Z][A-Z0-9]*_[A-Z0-9_]+(?:\.[A-Z0-9_]+)?\b"
_QUOTED = r"[\"“']([^\"”']{6,120})[\"”']"
_UI_NAME = r"\b((?:[A-Z][a-z]+)(?:\s(?:[A-Z][a-z]+|of|and|to)){1,4}\s(?:Page|Screen|Menu|Dialog|Grid|Panel|Form|Tab|Button|Field|Link|Toolbar|View))\b"
_MENU_PATH = r"\b[A-Z][\w ]{2,40}\s?>\s?[A-Z][\w ]{2,40}"
_NUMERIC_VALUE = [r"\b\d{3,4}\s?x\s?\d{3,4}\b", r"\b\d{3}\s?px\b", r"\b\d+\s?(?:minutes?|seconds?|characters?)\b"]


def _norm(text: str) -> str:
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).lower()


class QARulesChecker:
    """Checks generated test cases against the reviewer rules."""

    def __init__(self, sources_text: str, config: QARulesConfig | None = None, ac_count: int | None = None,
                 ac_texts: list[str] | None = None, docs_text: str = ""):
        self.src = _norm(sources_text or "")
        self.cfg = config or QARulesConfig()
        self.ac_count = ac_count
        self.ac_text = _norm(" ".join(ac_texts or []))
        self.docs_text = _norm(docs_text or "")

    # -- public ---------------------------------------------------------------

    def check(self, test_cases: list[dict], original_ids: dict[str, str] | None = None) -> list[RuleFinding]:
        """Return all findings for a list of test cases.

        Args:
            test_cases: dicts with id, title, objective, steps[{action, expected}], ac_refs.
            original_ids: optional {tc_id: previous_title}; findings flag a changed TC ID.
        """
        findings: list[RuleFinding] = []
        for tc in test_cases:
            findings.extend(self.check_one(tc, original_ids))
        findings.extend(self._check_coverage(test_cases))
        findings.extend(self._check_scenarios(test_cases))
        return findings

    def check_one(self, tc: dict, original_ids: dict[str, str] | None = None) -> list[RuleFinding]:
        tc_id = str(tc.get("id") or str(tc.get("title", "")).split(":")[0] or "?")
        out: list[RuleFinding] = []
        steps = tc.get("steps") or []
        prereq = steps[0].get("action", "") if steps else ""
        defined = self._defined_terms(prereq)

        def add(rule, code, sev, loc, msg, ev=""):
            out.append(RuleFinding(rule, code, sev, tc_id, loc, msg, ev))

        # Rule 6: title pattern and ID
        title = str(tc.get("title", ""))
        if not re.match(rf"^{re.escape(tc_id)}: [^/]+ / [^/]+ / [^/]+$", title):
            add("R6", "title_pattern", ERROR, "title", "Title must be '<ID>: Area / Component / Behavior'", title[:80])
        if original_ids and tc_id not in original_ids:
            add("R6", "tc_id_changed", ERROR, "title", "TC ID is not one of the existing IDs; keep IDs unchanged")

        # Rule 7: Pre-req
        if not prereq.startswith(self.cfg.pre_req_prefix) or (steps and steps[0].get("expected")):
            add("R7", "prereq_missing", ERROR, "step1", "Step 1 must be the Pre-req with an empty expected result")
        for p in _PREREQ_BANNED:
            m = re.search(p, prereq, re.IGNORECASE)
            if m:
                add("R7", "prereq_state_claim", ERROR, "step1.action",
                    "Pre-req states something 'is available'/'completed'; define roles and data instead", m.group(0))

        # Rule 7: roles used in steps must be defined in the Pre-req
        role_refs = set()
        for i, st in enumerate(steps[1:], start=2):
            act = st.get("action", "")
            if re.search(r"role defined in the Pre-req|<role", act, re.IGNORECASE):
                add("R7", "role_template_unresolved", ERROR, f"step{i}.action",
                    "Name the role (and define it in the Pre-req) instead of the template placeholder", act[:70])
            for m in re.finditer(r"\b(?:as|by) the ((?:[A-Z][\w'-]*)(?:\s[A-Z][\w'-]*){0,3})\b", act):
                role_refs.add(m.group(1))
        for role in sorted(role_refs):
            if _norm(role) not in defined and _norm(role) not in self.src:
                add("R7", "role_undefined", ERROR, "step1", "Role used in the steps is not defined in the Pre-req", role)
        # Rule 6: Area is short (1-4 words)
        parts = title.split(": ", 1)[-1].split(" / ")
        if len(parts) == 3 and len(parts[0].split()) > 4:
            add("R6", "area_too_long", WARNING, "title", "Area should be the feature in 1-3 words, not the story title", parts[0][:60])

        # Rule 5: steps
        for i, s in enumerate(steps[1:], start=2):
            action, expected = s.get("action", "").strip(), s.get("expected", "").strip()
            if not expected and not re.match(self.cfg.closing_step_pattern, action, re.IGNORECASE):
                add("R5", "empty_expected", ERROR, f"step{i}", "Step has no expected result", action[:70])
            if len(re.findall(r"[.!?](?:\s|$)", action)) > 1:
                add("R5", "multi_sentence_action", WARNING, f"step{i}.action", "Action has more than one sentence; split it", action[:70])
            m = re.search(_COMPOUND, action, re.IGNORECASE)
            if m:
                add("R5", "compound_action", WARNING, f"step{i}.action", "Possible compound action; one action per step", m.group(0))
            if re.match(_IMPERATIVE_BAD_START, action):
                add("R5", "not_imperative", WARNING, f"step{i}.action", "Action is not in the imperative mood", action[:50])

        for loc, text in self._texts(tc):
            out.extend(self._check_text(tc_id, loc, text, defined))
        return out

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _texts(tc: dict):
        yield "title", str(tc.get("title", "")).split(": ", 1)[-1]
        yield "objective", str(tc.get("objective", ""))
        for i, s in enumerate(tc.get("steps") or [], start=1):
            yield f"step{i}.action", str(s.get("action", ""))
            yield f"step{i}.expected", str(s.get("expected", ""))

    @staticmethod
    def _defined_terms(prereq: str) -> set[str]:
        """Terms the Pre-req defines as 'Name: definition.' count as grounded."""
        body = prereq.split(":", 1)[-1]
        terms = re.findall(r"(?:^|\.\s+)([A-Z][\w'/-]*(?:\s[\w'/-]+){0,5}):", body)
        return {_norm(t) for t in terms}

    def _in_sources(self, text: str, defined: set[str]) -> bool:
        t = _norm(text).strip(" .,;:")
        if not t:
            return True
        if t in self.src or any(t in d or d in t for d in defined if len(d) > 3):
            return True
        return False

    _LEAD = {"no", "each", "every", "the", "a", "an", "and", "or", "back", "any", "all", "new", "open", "select", "this", "that", "inspect", "check", "view", "use", "go", "verify"}

    def _strip_lead(self, name: str) -> str:
        words = name.split()
        while len(words) > 2 and words[0].lower() in self._LEAD:
            words = words[1:]
        return " ".join(words)

    def _value_in_sources(self, value: str) -> bool:
        v = _norm(value)
        if v in self.src or v.replace(" ", "") in self.src:
            return True
        m = re.match(r"(\d+)\s?([a-z]+)", v)
        if not m:
            return False
        num, unit = m.group(1), m.group(2).rstrip("s")[:6]
        return bool(re.search(rf"\b{num}\b[^.]{{0,40}}{unit}|{unit}[^.]{{0,40}}\b{num}\b", self.src))

    def _phrase_in_sources(self, text: str, start: int, end: int, defined: set[str]) -> bool:
        """True when the matched word plus a neighbouring word occurs in the sources
        (e.g. the UI label 'Confirm New Password', AC wording 'confirmed assignment set')."""
        before = re.findall(r"[\w'-]+", text[:start])[-1:]
        after = re.findall(r"[\w'-]+", text[end:])[:1]
        word = text[start:end]
        candidates = [" ".join(before + [word]), " ".join([word] + after)]
        return any(len(c.split()) > 1 and self._in_sources(c, defined) for c in candidates)

    def _check_text(self, tc_id: str, loc: str, text: str, defined: set[str]) -> list[RuleFinding]:
        out: list[RuleFinding] = []

        def add(rule, code, sev, msg, ev=""):
            out.append(RuleFinding(rule, code, sev, tc_id, loc, msg, ev))

        # Rule 2
        for p in _LETTER_ROLE:
            for m in re.finditer(p, text):
                add("R2", "letter_role", ERROR, "Lettered/numbered role or fixture name; use a general role defined in the Pre-req", m.group(0))
        # Rule 1 / 4: quoted text, DB identifiers, UI names, menu paths, legacy terms
        for m in re.finditer(_QUOTED, text):
            q = m.group(1)
            if "'" in m.group(0)[:1] and re.match(r"^[a-z]", q):   # possessive apostrophe pair, not a quote
                continue
            if not self._in_sources(q, defined):
                add("R1", "ungrounded_quote", ERROR, "Quoted message/label not found in the story or requirement docs", q[:80])
        for m in re.finditer(_DB_IDENT, text):
            if not self._in_sources(m.group(0), defined):
                add("R1", "ungrounded_identifier", ERROR, "Database/config identifier not found in the sources", m.group(0))
        if loc != "title":   # titles name neutral components by design (rule 6)
            for m in re.finditer(_UI_NAME, text):
                name = self._strip_lead(m.group(1))
                if name and not self._in_sources(name, defined):
                    add("R1", "ungrounded_ui_name", ERROR, "Screen/control name not found in the sources", name)
        for m in re.finditer(_MENU_PATH, text):
            if not self._in_sources(m.group(0), defined):
                add("R4", "menu_path", ERROR, "Menu path not confirmed by the sources", m.group(0)[:60])
        for term in self.cfg.legacy_terms:
            if re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE) and _norm(term) not in self.src:
                add("R4", "legacy_term", ERROR, "Legacy/old-system term not confirmed by the sources", term)
        for p in _NUMERIC_VALUE:
            for m in re.finditer(p, text, re.IGNORECASE):
                if not self._value_in_sources(m.group(0)):
                    add("R4", "ungrounded_value", ERROR, "Concrete value not stated in the sources", m.group(0))
        for m in re.finditer(r"\bsuch as\b|\bfor example\b|\bfor instance\b", text, re.IGNORECASE):
            add("R1", "example_value", WARNING, "Example wording in test text; name the exact sourced value or use neutral wording", m.group(0))
        # Rule 3
        for bad, good in self.cfg.synonyms.items():
            if re.search(rf"\b{re.escape(bad)}\b", text, re.IGNORECASE):
                add("R3", "synonym", ERROR, f"Use the project term '{good}'", bad)
        # Rule 8
        for m in re.finditer(_TEAM_WORK, text, re.IGNORECASE):
            if not self._phrase_in_sources(text, m.start(), m.end(), defined):
                add("R8", "team_work", WARNING, "Possible team-work wording (confirm/agree/approve); QA checks observable results", m.group(0))
        for m in re.finditer(_DOC_CHECK, text, re.IGNORECASE):
            add("R8", "documented_check", ERROR, "Checks that something was documented/agreed - team work, not QA", m.group(0))
        # Rule 9
        for m in re.finditer(_ATTRIBUTED, text, re.IGNORECASE):
            add("R9", "attributed_evidence", ERROR, "Do not name who provided evidence; write 'the provided evidence'", m.group(0))
        # Rule 10
        m = re.search(_DB_WRITE, text, re.IGNORECASE)
        context = text[max(0, m.start() - 30): m.end()] if m else ""
        if m and loc not in ("objective", "title") and not re.search(_DB_WRITE_SAFE, context, re.IGNORECASE):
            add("R10", "db_change", ERROR, "QA can only read the database; do not change or restore data there", m.group(0)[:70])
        # Rule 11
        for p in _INLINE_COMMENT:
            for m in re.finditer(p, text, re.IGNORECASE):
                add("R11", "inline_comment", ERROR, "Remove comments/hedges from test text; move open points to open_questions", m.group(0))
        for m in re.finditer(r"\(([^)]{3,})\)", text):
            if not self._in_sources(m.group(0), defined):
                add("R11", "bracket_note", WARNING, "Bracketed note in test text", m.group(0)[:60])
        # Rule 12
        if re.search(r"\bnor\b", text, re.IGNORECASE):
            add("R12", "nor", ERROR, "Write 'No X, Y or Z' instead of 'nor'", "nor")
        if "’" in text:
            add("R12", "apostrophe", WARNING, "Use straight apostrophes", "’")
        return out

    def _check_scenarios(self, test_cases: list[dict]) -> list[RuleFinding]:
        """Scenario classes the ACs (error) or requirement docs (warning) describe but no test exercises."""
        if not (self.ac_text or self.docs_text):
            return []
        tests_text = _norm(" ".join(" ".join(t for _, t in self._texts(tc)) for tc in test_cases))
        out = []
        ac_classes = _scenario_hits(self.ac_text)
        # Developer ledgers use "audit" for unrelated things (board audits), so it counts only from ACs
        doc_classes = _scenario_hits(self.docs_text) - ac_classes - _DOC_EXCLUDED_SCENARIOS
        for name in sorted(ac_classes | doc_classes):
            if not re.search(SCENARIO_CLASSES[name][1], tests_text, re.IGNORECASE):
                in_ac = name in ac_classes
                out.append(RuleFinding(
                    "R13", "missed_scenario", ERROR if in_ac else WARNING, "story", "scenarios",
                    f"The {'acceptance criteria' if in_ac else 'requirement documents'} describe "
                    f"'{name}' but no test exercises it", name))
        return out

    def _check_coverage(self, test_cases: list[dict]) -> list[RuleFinding]:
        if not self.ac_count:
            return []
        covered = set()
        for tc in test_cases:
            for a in tc.get("ac_refs") or tc.get("ac_covered") or []:
                try:
                    covered.add(int(a))
                except (TypeError, ValueError):
                    continue
        missing = sorted(set(range(1, self.ac_count + 1)) - covered)
        return [RuleFinding("R13", "ac_uncovered", ERROR, "story", f"AC{n}",
                            "Acceptance criterion has no covering test") for n in missing]


# Scenario classes that reviewers found missing when the sources described them.
# (source pattern, test pattern) - both case-insensitive.
SCENARIO_CLASSES: dict[str, tuple[str, str]] = {
    "cancel/discard": (r"\bcancel\w*|\bdiscard\w*", r"\bcancel\w*|\bdiscard\w*"),
    "stale or concurrent edit": (r"\bstale\b|\bconcurren\w+|\bconflict\w*|\bsimultaneous\w*|\bcompeting\b",
                                 r"\bstale\b|\bconcurren\w+|\bconflict\w*|\bsecond (?:browser|session|administrator|editor)|\bcompeting\b|\breload\b"),
    "retry/duplicate submit": (r"\bretr(?:y|ies)\b|\bdouble[- ]submit\w*|\bidempoten\w+",
                               r"\bretr(?:y|ies)\b|\bdouble|\btwice\b|\bagain\b|\brepeat\w*"),
    "denied access": (r"\bdenied\b|\bforbidden\b|\b403\b|\bwithout (?:the )?(?:required )?permission|\bunauthori[sz]ed\b|\brestricted\b",
                      r"\bdenied\b|\b403\b|\bunauthori[sz]ed\b|\brestricted\b|\brefused\b|\bwithout\b"),
    "empty result": (r"\bno match\w*|\bempty (?:state|result|list)|\bno results?\b", r"\bno match\w*|\bempty\b|\bno results?\b|\bno rows?\b"),
    "failure/unavailable dependency": (r"\bunavailable\b|\bfail(?:ed|ure|s)\b|\b503\b|\boutage\b",
                                       r"\bunavailable\b|\bfail\w*|\b503\b|\boutage\b|\berror\b"),
    "session expiry": (r"\bsession (?:expir\w+|timeout)|\binactivity\b|\bexpired session", r"\bexpir\w+|\btimeout\b|\binactiv\w+"),
    "keyboard use": (r"\bkeyboard\b", r"\bkeyboard\b|\btab\b|\benter key\b|\bpress\b"),
    "narrow width": (r"\bnarrow\b|\b375\s?px\b|\bmobile width", r"\bnarrow\b|\b375\b"),
    "validation": (r"\bvalidat\w+|\binvalid\b|\brequired field|\bmaximum length|\bover-length",
                   r"\bvalidat\w+|\binvalid\b|\brequired\b|\bmaximum\b|\bover-length|\bempty\b|\brejected\b"),
    "direct URL/link": (r"\bdirect (?:url|link|request|access)|\btyped url|\bbookmark", r"\bdirect\b|\burl\b|\bbookmark\w*|\baddress bar"),
    "audit/attribution": (r"\baudit\w*|\battribut\w+", r"\baudit\w*|\battribut\w+|update_user_id"),
}


_DOC_EXCLUDED_SCENARIOS = {"audit/attribution"}


def _scenario_hits(text: str) -> set[str]:
    return {name for name, (src_pat, _) in SCENARIO_CLASSES.items() if re.search(src_pat, text, re.IGNORECASE)}


def summarize(findings: list[RuleFinding]) -> dict:
    """Counts by rule and severity, for reports."""
    by_rule: dict[str, int] = {}
    for f in findings:
        by_rule[f.rule] = by_rule.get(f.rule, 0) + 1
    return {
        "errors": sum(f.severity == ERROR for f in findings),
        "warnings": sum(f.severity == WARNING for f in findings),
        "by_rule": dict(sorted(by_rule.items())),
    }


def feedback_by_test(findings: list[RuleFinding], severities=(ERROR,)) -> dict[str, list[str]]:
    """Group findings into per-test feedback lines for a fixer prompt."""
    grouped: dict[str, list[str]] = {}
    for f in findings:
        if f.severity in severities:
            grouped.setdefault(f.tc_id, []).append(f.to_feedback())
    return grouped


# --- judge integration --------------------------------------------------------

_RULE_CATEGORY = {
    "R1": "hallucinated_content", "R4": "hallucinated_content",
    "R2": "lettered_role", "R3": "inconsistent_terminology",
    "R6": "inconsistent_step_structure", "R7": "inconsistent_step_structure",
    "R8": "team_work_step", "R9": "forbidden_language", "R10": "database_change",
    "R11": "inline_comment", "R12": "forbidden_language", "R13": "missing_ac_coverage",
}


def to_judge_issues(findings: list[RuleFinding]):
    """Convert rule findings into JudgeIssue objects (errors keep the category's
    severity; warnings are minor). R13 findings are returned separately as AC numbers."""
    from core.interfaces.judge import (
        CATEGORY_SEVERITY,
        IssueCategory,
        IssueSeverity,
        JudgeIssue,
    )

    issues, uncovered = [], []
    for f in findings:
        if f.code == "ac_uncovered":
            uncovered.append(f.location.removeprefix("AC"))
            continue
        cat_name = "empty_expected_result" if f.code == "empty_expected" else _RULE_CATEGORY.get(
            f.rule, "inconsistent_step_structure")
        category = IssueCategory(cat_name)
        severity = CATEGORY_SEVERITY.get(category, IssueSeverity.MAJOR) if f.severity == ERROR else IssueSeverity.MINOR
        if f.severity == ERROR and severity == IssueSeverity.MINOR:
            severity = IssueSeverity.MAJOR
        issues.append(JudgeIssue(
            test_case_id=f.tc_id, category=category, severity=severity,
            description=f"[rule {f.rule}] {f.message}", violating_text=f.evidence,
            location=f.location,
        ))
    return issues, uncovered
