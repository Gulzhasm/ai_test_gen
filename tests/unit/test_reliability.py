"""
Reliability regressions for the generation pipeline.

Each test pins a failure seen in real generations:
- story 294626 lost iPad and Android because its ACs said "Apple/iOS" and
  "Google Play/Android" instead of the config's platform names;
- the judge reported "5 critical issues remain" and the run still passed,
  saved an unverified fix, and silently dropped three of its own categories;
- web projects got a second launch step and a second sign-out step;
- a feature step "Close the About dialog" lost its expected result;
- platform variants of one test were removed as duplicates;
- an accessibility test for a web app told the tester to launch a desktop app
  and use a Windows desktop scanner.
"""
from types import SimpleNamespace

import pytest

from core.interfaces.judge import IssueCategory, IssueSeverity
from core.services.llm.corrector import LLMCorrector
from core.services.llm.prompt_builder import OUTPUT_SCHEMA, PromptBuilder, PromptContext
from core.services.platform_scope import (
    accessibility_profile,
    platforms_mentioned,
    select_story_platforms,
)
from core.services.quality.judge import LLMJudge
from core.services.quality.output_gate import OutputQualityGate, offers_alternatives
from projects.project_config import ApplicationConfig

PLATFORMS = ["Windows 11", "iPad", "Android Tablet"]

AC_ALL_PACKAGES = ("The final approved User Manual PDF replaces the previous version in all "
                   "applicable SiteDraft installation packages.")
AC_NAMED_STORES = ("The approved User Manual versions are included in all applicable "
                   "Microsoft/Windows, Apple/iOS, and Google Play/Android packages.")


def _desktop_app(**overrides) -> ApplicationConfig:
    values = dict(
        name="SiteDraft",
        prereq_template="Pre-req: The {app_name} App is installed",
        launch_step="Launch the {app_name} application.",
        launch_expected="The SiteDraft Home Screen is displayed.",
        create_file_step="From the Home screen, create a new file.",
        create_file_expected="A new blank drawing opens.",
        close_step="Close the {app_name} App",
        supported_platforms=list(PLATFORMS),
    )
    values.update(overrides)
    return ApplicationConfig(**values)


def _web_app(**overrides) -> ApplicationConfig:
    values = dict(
        name="IMS",
        app_type="web",
        prereq_template="Pre-req: User has a valid {app_name} account",
        launch_step="Navigate to the {app_name} web application and sign in with valid credentials.",
        launch_expected="The Home Page is displayed.",
        create_file_step="Open Establishments and select one establishment row.",
        create_file_expected="The establishment row is selected.",
        close_step="Sign out of {app_name}.",
        setup_step_policy="when_needed",
        supported_platforms=["Chrome (Windows 11)"],
        object_interaction_keywords=["establishment", "inspection"],
    )
    values.update(overrides)
    return ApplicationConfig(**values)


def _tc(tc_id, steps, title=None, objective="", **extra):
    return {"id": tc_id, "title": title or f"{tc_id}: Feature / Area / Scenario",
            "objective": objective,
            "steps": [{"action": a, "expected": e} for a, e in steps], **extra}


# ---------------------------------------------------------------------------
# Platform scope
# ---------------------------------------------------------------------------

class TestPlatformScope:
    def test_store_and_os_aliases_select_every_named_platform(self):
        assert select_story_platforms(PLATFORMS, [AC_NAMED_STORES]) == PLATFORMS

    def test_all_applicable_packages_selects_all_platforms(self):
        assert select_story_platforms(PLATFORMS, [AC_ALL_PACKAGES]) == PLATFORMS

    def test_desktop_only_story_keeps_primary_platform_only(self):
        acs = ["User can toggle grid visibility from the View Menu."]
        assert select_story_platforms(PLATFORMS, acs) == ["Windows 11"]

    def test_single_store_name(self):
        acs = ["QA downloads SiteDraft from Google Play."]
        assert select_story_platforms(PLATFORMS, acs) == ["Windows 11", "Android Tablet"]

    def test_generic_tablet_word_widens_story_scope(self):
        assert select_story_platforms(PLATFORMS, ["Works on tablets."]) == PLATFORMS

    def test_generic_word_is_not_coverage_of_another_platform(self):
        title = "Touch Interaction (Android Tablet)"
        assert platforms_mentioned(title, PLATFORMS, include_generic=False) == ["Android Tablet"]

    def test_edge_case_is_not_the_edge_browser(self):
        assert platforms_mentioned("Add an edge case test.", ["Chrome", "Microsoft Edge"]) == []

    def test_custom_alias_from_config(self):
        acs = ["Runs on the field device."]
        selected = select_story_platforms(PLATFORMS, acs, {"iPad": ["field device"]})
        assert selected == ["Windows 11", "iPad"]

    def test_web_platform_gets_web_accessibility_tooling(self):
        assert accessibility_profile("Chrome (Windows 11)", "web")["tool"] == "Accessibility Insights for Web"
        assert accessibility_profile("Windows 11", "desktop")["tool"] == "Accessibility Insights for Windows"
        assert accessibility_profile("iPad")["tool"] == "VoiceOver"


# ---------------------------------------------------------------------------
# Judge
# ---------------------------------------------------------------------------

class FakeLLM:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def generate_json(self, **_kwargs):
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


RULES = SimpleNamespace(forbidden_words=[])
STORY = {"story_id": "1", "title": "Demo", "description": "Demo story."}
ACS = ["AC one", "AC two"]
TESTS = [_tc("1-AC1", [("Launch the SiteDraft application.", "Home Screen."), ("Do X.", "Y.")])]


def _issue(category, severity, tc_id="1-AC1"):
    return {"test_case_id": tc_id, "category": category, "severity": severity,
            "description": "d"}


def _judge(judge_llm, fixer_llm=None, **kwargs):
    return LLMJudge(llm_provider=judge_llm, fixer_provider=fixer_llm, **kwargs)


class TestJudge:
    def test_failed_evaluation_is_never_a_pass(self):
        verdict = _judge(FakeLLM(RuntimeError("timeout"))).evaluate_and_fix(
            TESTS, STORY, ACS, _desktop_app(), RULES)
        assert verdict.evaluated is False
        assert verdict.passed is False
        assert verdict.corrected_test_cases == TESTS

    def test_unparseable_response_is_never_a_pass(self):
        verdict = _judge(FakeLLM("not json")).evaluate(TESTS, STORY, ACS, _desktop_app(), RULES)
        assert not verdict.evaluated and not verdict.passed

    def test_pass_is_computed_not_trusted(self):
        response = {"overall_pass": True,
                    "issues": [_issue("hallucinated_content", "critical")]}
        verdict = _judge(FakeLLM(response)).evaluate(TESTS, STORY, ACS, _desktop_app(), RULES)
        assert verdict.passed is False
        assert verdict.critical_count == 1

    @pytest.mark.parametrize("category", [
        "verify_in_action", "missing_create_file", "undo_redo_combined",
        "ambiguous_expected_result", "unverifiable_expected_result",
    ])
    def test_categories_the_prompt_lists_are_parsed(self, category):
        response = {"issues": [_issue(category, "major")]}
        verdict = _judge(FakeLLM(response)).evaluate(TESTS, STORY, ACS, _desktop_app(), RULES)
        assert verdict.issues[0].category == IssueCategory(category)

    def test_unknown_category_is_kept_not_dropped(self):
        response = {"issues": [_issue("wrong_platform", "major")]}
        verdict = _judge(FakeLLM(response)).evaluate(TESTS, STORY, ACS, _desktop_app(), RULES)
        assert verdict.issues[0].category is IssueCategory.OTHER
        assert verdict.issues[0].severity is IssueSeverity.MAJOR
        assert "[wrong_platform]" in verdict.issues[0].description

    def test_fix_that_makes_things_worse_is_discarded(self):
        fixed = [_tc("1-AC1", [("Launch the SiteDraft application.", "Home Screen."),
                               ("Do Z.", "W.")])]
        judge_llm = FakeLLM({"issues": [_issue("logical_contradiction", "major")]},
                            {"issues": [_issue("hallucinated_content", "critical"),
                                        _issue("hallucinated_content", "critical")]})
        fixer = FakeLLM({"test_cases": fixed})
        verdict = _judge(judge_llm, fixer, max_rounds=2).evaluate_and_fix(
            TESTS, STORY, ACS, _desktop_app(), RULES)
        assert verdict.corrected_test_cases == TESTS
        assert verdict.major_count == 1 and verdict.critical_count == 0
        assert verdict.rounds_used == 2

    def test_fix_that_helps_is_kept(self):
        fixed = [_tc("1-AC1", [("Launch the SiteDraft application.", "Home Screen."),
                               ("Do Z.", "W.")])]
        judge_llm = FakeLLM({"issues": [_issue("logical_contradiction", "major")]},
                            {"issues": []})
        verdict = _judge(judge_llm, FakeLLM({"test_cases": fixed})).evaluate_and_fix(
            TESTS, STORY, ACS, _desktop_app(), RULES)
        assert verdict.passed
        assert verdict.corrected_test_cases == fixed

    def test_final_round_never_ships_an_unverified_fix(self):
        judge_llm = FakeLLM({"issues": [_issue("logical_contradiction", "major")]})
        fixer = FakeLLM({"test_cases": []})
        verdict = _judge(judge_llm, fixer, max_rounds=1).evaluate_and_fix(
            TESTS, STORY, ACS, _desktop_app(), RULES)
        assert fixer.calls == 0
        assert verdict.corrected_test_cases == TESTS

    def test_uncovered_acs_are_sent_to_the_gap_filler(self):
        new_test = _tc("1-010", [("Launch the SiteDraft application.", "Home Screen."),
                                 ("Do two.", "Two happens.")], ac_refs=[2])
        seen = []

        def gap_filler(uncovered, current):
            seen.append(uncovered)
            return [new_test]

        judge_llm = FakeLLM({"issues": [], "ac_coverage": {"1": True, "2": False}},
                            {"issues": [], "ac_coverage": {"1": True, "2": True}})
        verdict = _judge(judge_llm, gap_filler=gap_filler).evaluate_and_fix(
            TESTS, STORY, ACS, _desktop_app(), RULES)
        assert seen == [[(2, "AC two")]]
        assert verdict.corrected_test_cases == TESTS + [new_test]
        assert verdict.uncovered_acs == []

    def test_malformed_fix_keeps_the_original(self):
        judge_llm = FakeLLM({"issues": [_issue("logical_contradiction", "major")]},
                            {"issues": []})
        fixer = FakeLLM({"test_cases": [{"id": "1-AC1", "steps": []}]})
        verdict = _judge(judge_llm, fixer).evaluate_and_fix(
            TESTS, STORY, ACS, _desktop_app(), RULES)
        # nothing could be applied, so the evaluated original is returned
        assert verdict.corrected_test_cases == TESTS


# ---------------------------------------------------------------------------
# Deterministic output gate
# ---------------------------------------------------------------------------

class TestOutputGate:
    @pytest.mark.parametrize("text, expected", [
        ("The manual opens in a viewer or an external application.", True),
        ("No errors or warnings are displayed.", False),
        ("Installed Version is 1.0.246 or later.", False),
        ("Click 'Save or Export'.", False),
        ("Press Enter or click OK.", True),
    ])
    def test_offers_alternatives(self, text, expected):
        assert offers_alternatives(text) is expected

    def _rules(self, **findings):
        return {f.rule for f in findings["report"].findings}

    def test_flags_ambiguous_vague_and_empty_expected_results(self):
        tc = _tc("1-005", [
            ("Pre-req: The SiteDraft App is installed", ""),
            ("Launch the SiteDraft application.", "The Home Screen is displayed."),
            ("Select 'User Manual'.", "The manual opens in a viewer or an external application."),
            ("Review the manual.", "The content matches the approved version."),
            ("Scroll to the last page.", ""),
            ("Close the SiteDraft App", ""),
        ])
        report = OutputQualityGate(_desktop_app(), RULES).run([tc])
        rules = {f.rule for f in report.findings}
        assert {"ambiguous_expected", "unverifiable_expected", "empty_expected"} <= rules
        assert not report.passed

    def test_flags_forbidden_ui_terms(self):
        app = _desktop_app(forbidden_ui_terms=["Side Panel"])
        tc = _tc("1-005", [("Launch the SiteDraft application.", "Home."),
                           ("Open the Side Panel.", "It opens.")])
        report = OutputQualityGate(app, RULES).run([tc])
        assert any(f.rule == "forbidden_ui_term" and f.severity == "critical"
                   for f in report.findings)

    def test_flags_platform_without_functional_test(self):
        tests = [
            _tc("1-AC1", [("Launch.", "Home."), ("Open the manual on Windows 11.", "It opens.")]),
            _tc("1-040", [("Launch.", "Home."), ("Run VoiceOver.", "Announced.")],
                title="1-040: Manual / Accessibility / VoiceOver Navigation (iPad)"),
        ]
        report = OutputQualityGate(_desktop_app(), RULES, story_platforms=PLATFORMS).run(tests)
        missing = {f.location for f in report.findings if f.rule == "missing_platform"}
        # an accessibility check is not functional coverage of iPad
        assert missing == {"iPad", "Android Tablet"}

    def test_traceability(self):
        tests = [
            _tc("1-AC1", [("Launch.", "Home."), ("Do one.", "One.")], ac_refs=[1]),
            _tc("1-005", [("Launch.", "Home."), ("Do more.", "More.")], ac_refs=[]),
        ]
        report = OutputQualityGate(_desktop_app(), RULES, ac_count=2).run(tests)
        rules = {(f.rule, f.location) for f in report.findings}
        assert ("untraced_test", "ac_refs") in rules
        assert ("uncited_ac", "AC2") in rules


# ---------------------------------------------------------------------------
# Corrector: config-driven structure, dedup, coverage, accessibility
# ---------------------------------------------------------------------------

class TestCorrectorStructure:
    def test_web_launch_and_sign_out_are_not_duplicated(self):
        corrector = LLMCorrector(app_config=_web_app())
        tc = _tc("1-005", [
            ("Pre-req: User has a valid IMS account", ""),
            ("Navigate to the IMS web application and sign in with valid credentials.", "x"),
            ("Open the News Search Page.", "The News Search Page is displayed."),
            ("Sign out of IMS.", ""),
        ])
        corrector._normalize_structure(tc)
        actions = [s["action"] for s in tc["steps"]]
        assert sum("Navigate to the IMS web application" in a for a in actions) == 1
        assert actions.count("Sign out of IMS.") == 1
        assert actions[-1] == "Sign out of IMS."
        assert tc["steps"][1]["expected"] == "The Home Page is displayed."

    def test_feature_close_step_keeps_its_expected_result(self):
        corrector = LLMCorrector(app_config=_desktop_app())
        tc = _tc("1-005", [
            ("Pre-req: The SiteDraft App is installed", ""),
            ("Launch the SiteDraft application.", "Home."),
            ("Close the About dialog.", "The About dialog closes."),
        ])
        corrector._normalize_structure(tc)
        steps = tc["steps"]
        assert steps[2] == {"action": "Close the About dialog.",
                            "expected": "The About dialog closes.", "step": 3}
        assert steps[-1]["action"] == "Close the SiteDraft App"

    def test_app_close_variant_is_standardised(self):
        corrector = LLMCorrector(app_config=_desktop_app())
        tc = _tc("1-005", [("Launch SiteDraft.", "Home."), ("Do X.", "Y."),
                           ("Close the SiteDraft App without saving the drawing.", "")])
        corrector._normalize_structure(tc)
        actions = [s["action"] for s in tc["steps"]]
        assert actions[0] == "Pre-req: The SiteDraft App is installed"
        assert actions[1] == "Launch the SiteDraft application."
        assert actions[-1] == "Close the SiteDraft App"
        assert len(actions) == 4

    def test_specific_pre_req_is_kept_after_the_template(self):
        corrector = LLMCorrector(app_config=_desktop_app())
        tc = _tc("1-005", [("Pre-req: An iPad without SiteDraft installed", ""),
                           ("Launch the SiteDraft application.", "Home.")])
        corrector._normalize_structure(tc)
        actions = [s["action"] for s in tc["steps"]]
        assert actions[:2] == ["Pre-req: The SiteDraft App is installed",
                               "Pre-req: An iPad without SiteDraft installed"]


class TestCorrectorDedupAndCoverage:
    def _steps(self, platform):
        return [("Launch the SiteDraft application.", "Home."),
                (f"Open the User Manual on {platform}.", "The v2.0 cover is displayed."),
                ("Close the SiteDraft App", "")]

    def test_platform_variants_are_not_duplicates(self):
        corrector = LLMCorrector(app_config=_desktop_app())
        tests = [
            _tc("1-AC1", self._steps("Windows 11")),
            _tc("1-005", self._steps("Windows 11"), title="1-005: M / Help Menu / Opens (Windows 11)",
                objective="Verify that the approved manual opens on Windows 11"),
            _tc("1-010", self._steps("iPad"), title="1-010: M / Help Menu / Opens (iPad)",
                objective="Verify that the approved manual opens on iPad"),
            _tc("1-015", self._steps("Windows 11"), title="1-015: M / Help Menu / Opens Again (Windows 11)",
                objective="Verify that the approved manual opens on Windows 11"),
        ]
        kept = corrector._remove_duplicate_tests(tests, "1")
        assert len(kept) == 3  # 015 duplicates 005; the iPad variant stays

    def test_multi_platform_ac_needs_a_test_per_platform(self):
        corrector = LLMCorrector(app_config=_desktop_app())
        tests = [_tc("1-AC1", [
            ("Launch the SiteDraft application.", "Home."),
            ("Open the approved User Manual versions in the Microsoft Windows package.",
             "The approved User Manual is included."),
        ])]
        coverage = corrector._map_acs_to_tests(tests, [AC_NAMED_STORES])
        assert coverage[1] == ["1-AC1"]
        gaps = corrector._missing_platform_variants(tests, [AC_NAMED_STORES], coverage)
        assert [text.rsplit(": ", 1)[1] for _, text in gaps] == ["iPad]", "Android Tablet]"]

    def test_template_steps_are_not_coverage_evidence(self):
        corrector = LLMCorrector(app_config=_desktop_app())
        ac = "The SiteDraft application launches successfully and shows the Home Screen."
        tests = [_tc("1-005", [("Pre-req: The SiteDraft App is installed", ""),
                               ("Launch the SiteDraft application.", "The SiteDraft Home Screen is displayed."),
                               ("Open the Help Menu.", "The Help Menu opens.")])]
        assert corrector._map_acs_to_tests(tests, [ac])[1] == []

    def test_web_accessibility_test_uses_project_steps_and_web_tool(self):
        corrector = LLMCorrector(app_config=_web_app())
        tc = corrector._generate_accessibility_test("1", "News Search", "Chrome (Windows 11)", 40)
        text = " ".join(f"{s['action']} {s['expected']}" for s in tc["steps"])
        assert "Accessibility Insights for Web" in text
        assert "Navigate to the IMS web application" in text
        assert "Launch the IMS application" not in text
        assert "Windows" not in tc["title"].split("(")[0]
        # sign-in/news pages need no establishment selected (when_needed policy)
        assert "establishment" not in text.lower()


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _context(**overrides) -> PromptContext:
    values = dict(
        app_name="IMS", app_type="web", story_id="1", feature_name="News Search",
        acceptance_criteria=["User can search news by title."], qa_prep="",
        unavailable_features=[], feature_notes={}, ui_surfaces=["News Search Page"],
        entry_points={}, platforms=["Chrome (Windows 11)"],
        prereq_template="Pre-req: User has a valid {app_name} account",
        launch_step="Navigate to the {app_name} web application and sign in.",
        launch_expected="The Home Page is displayed.",
        create_file_step="Select one establishment row.",
        create_file_expected="The row is selected.",
        close_step="Sign out of {app_name}.", forbidden_words=[], allowed_areas=[],
        setup_step_policy="when_needed",
    )
    values.update(overrides)
    return PromptContext(**values)


class TestPromptBuilder:
    def test_web_prompt_uses_policy_and_web_tooling(self):
        prompt = PromptBuilder(_context()).build_system_prompt()
        assert "Accessibility Insights for Web" in prompt
        assert "Accessibility Insights for Windows" not in prompt
        assert "ONLY when the feature under test needs that context" in prompt
        assert "MANDATORY in EVERY test case" not in prompt

    def test_desktop_prompt_keeps_mandatory_setup(self):
        ctx = _context(app_type="desktop", platforms=["Windows 11"], setup_step_policy="always")
        assert "MANDATORY in EVERY test case" in PromptBuilder(ctx).build_system_prompt()

    def test_output_contract_requires_traceability(self):
        assert "ac_refs" in OUTPUT_SCHEMA["test_cases"][0]

    def test_platform_filter_uses_aliases(self):
        ctx = _context(app_type="desktop", platforms=list(PLATFORMS),
                       acceptance_criteria=[AC_NAMED_STORES])
        assert PromptBuilder(ctx).ctx.platforms == PLATFORMS


# ---------------------------------------------------------------------------
# Workflow filter
# ---------------------------------------------------------------------------

class TestFilterIrrelevantTests:
    def _filter(self, tests, acs, unavailable):
        from workflows import GenerateWorkflow
        return GenerateWorkflow()._filter_irrelevant_tests(tests, acs, unavailable)

    def test_real_absence_test_is_kept(self):
        tc = _tc("1-030", [("Tap the support email.", "No 'Webpage not available' error page is shown.")],
                 title="1-030: M / Hamburger Menu / No Error Page When Tapping Links")
        assert self._filter([tc], ["Links open."], ["multi-object selection"]) == [tc]

    def test_filler_about_an_unavailable_feature_is_dropped(self):
        tc = _tc("1-030", [("Open the Edit Menu.", "No option is shown.")],
                 title="1-030: M / Edit Menu / No Multi-Object Selection Available")
        assert self._filter([tc], ["User can rotate one object."], ["multi-object selection"]) == []

    def test_same_actions_with_different_oracles_are_not_duplicates(self):
        a = _tc("1-005", [("Open the manual.", "The cover reads 'Version: 2.0'.")])
        b = _tc("1-010", [("Open the manual.", "Page 43 shows '6.2 Contact Support'.")])
        assert len(self._filter([a, b], ["AC"], [])) == 2

    def test_same_steps_on_another_platform_are_kept(self):
        # Story 294626: identical steps titled (iPad) and (Android Tablet) were
        # dropped as duplicates, losing Android coverage entirely.
        steps = [("Open the Hamburger Menu and select 'User Manual / Tutorial'.", "The manual opens.")]
        ipad = _tc("1-020", steps, title="1-020: M / Hamburger Menu / Manual Opens (iPad)")
        android = _tc("1-025", steps, title="1-025: M / Hamburger Menu / Manual Opens (Android Tablet)")
        from workflows import GenerateWorkflow
        kept = GenerateWorkflow()._filter_irrelevant_tests([ipad, android], ["AC"], [], PLATFORMS)
        assert kept == [ipad, android]


class TestReviewFindingsFromLiveRun:
    def test_negation_anywhere_in_the_clause_is_not_an_alternative(self):
        text = "Accessibility Scanner reports no critical issues related to the User Manual access or display."
        assert offers_alternatives(text) is False
        assert offers_alternatives("The manual opens. It is shown in a new window or tab.") is True

    @pytest.mark.parametrize("expected", [
        "The content of the User Manual PDF is confirmed to be the correct approved version.",
        "The User Manual content reflects the approved changes and is not the previous version.",
    ])
    def test_unreferenced_version_claims_are_unverifiable(self, expected):
        tc = _tc("1-010", [("Launch.", "Home."), ("Review the manual.", expected), ("Close.", "")])
        report = OutputQualityGate(_desktop_app(), RULES).run([tc])
        assert any(f.rule == "unverifiable_expected" for f in report.findings)

    def test_domain_notes_reach_the_generator_prompt(self):
        ctx = _context(feature_notes={"delete": "IMS uses soft delete."},
                       feature_aliases={"EHS": "Environmental Health Specialist"})
        user_prompt = PromptBuilder(ctx).build_user_prompt('{"test_cases": []}')
        assert "delete: IMS uses soft delete." in user_prompt
        assert "EHS: Environmental Health Specialist" in user_prompt
