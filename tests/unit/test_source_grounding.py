"""Strict source grounding: prompt sections, judge rule merge, provider request, config fixes."""
from unittest.mock import MagicMock

from core.interfaces.judge import IssueCategory, IssueSeverity
from core.services.llm.anthropic_provider import AnthropicProvider
from core.services.llm.prompt_builder import PromptBuilder, PromptContext
from core.services.quality.judge import LLMJudge
from core.services.quality.qa_rules_checker import QARulesChecker, to_judge_issues


def _ctx(**over):
    base = dict(app_name="App", app_type="web", story_id="1", feature_name="User Search",
                acceptance_criteria=["An administrator can search users."], qa_prep="OLD QA PREP TEXT",
                unavailable_features=[], feature_notes={}, ui_surfaces=["Legacy Users Screen"],
                entry_points={}, platforms=["Chrome"], prereq_template="Pre-req: x", launch_step="Sign in.",
                launch_expected="", create_file_step="", create_file_expected="",
                close_step="Sign out of {app_name}.", forbidden_words=[], allowed_areas=["Legacy Users Screen"])
    base.update(over)
    return PromptContext(**base)


def _tc(steps):
    return {"id": "1-AC1", "title": "1-AC1: User Search / Result List / Shows Users", "objective": "Verify that x.",
            "ac_refs": [1], "steps": [{"action": "Pre-req: Non-production environment.", "expected": ""}] + steps}


# --- prompt builder ------------------------------------------------------------

def test_strict_prompt_has_rules_docs_and_grounded_tasks():
    b = PromptBuilder(_ctx(strict_grounding=True, use_qa_prep_as_source=False, auto_accessibility_tests=False,
                           requirement_docs="<requirement_documents>DOC</requirement_documents>",
                           glossary={"result list": "the list of results"}))
    system = b.build_system_prompt()
    user = b.build_user_prompt('{"test_cases": []}')
    assert system.startswith("## SOURCE-GROUNDED WRITING RULES")
    assert "result list: the list of results" in system
    assert "<requirement_documents>DOC</requirement_documents>" in user
    assert "YOUR TASK (source-grounded)" in user
    assert "isn't obvious from the AC" not in user          # no open-ended brainstorming
    assert "OLD QA PREP TEXT" not in user                     # untrusted QA Prep dropped
    assert '"Legacy Users Screen"' not in user              # legacy surface list not offered for titles


def test_default_prompt_is_unchanged_by_strict_features():
    b = PromptBuilder(_ctx())
    assert not b.build_system_prompt().startswith("## SOURCE-GROUNDED")
    user = b.build_user_prompt('{"test_cases": []}')
    assert "OLD QA PREP TEXT" in user and "YOUR TASK (Expert QA Level)" in user


# --- checker: missed scenarios -----------------------------------------------------

def test_missed_scenarios_from_acs_are_errors_and_from_docs_are_warnings():
    tc = _tc([{"action": "Save the form.", "expected": "The form is saved."}])
    findings = QARulesChecker("x", ac_texts=["Cancelling leaves data unchanged."],
                              docs_text="A stale save offers Reload. Board title audit done.").check([tc])
    got = {(f.severity, f.evidence) for f in findings if f.code == "missed_scenario"}
    assert ("error", "cancel/discard") in got
    assert ("warning", "stale or concurrent edit") in got
    assert not any(e == "audit/attribution" for _, e in got)   # doc-level audit wording is ignored


def test_covered_scenario_is_not_reported():
    tc = _tc([{"action": "Select Cancel.", "expected": "The original values remain."}])
    findings = QARulesChecker("x", ac_texts=["Cancelling leaves data unchanged."]).check([tc])
    assert not [f for f in findings if f.code == "missed_scenario"]


# --- judge merge -------------------------------------------------------------------

def test_judge_merges_rule_findings_and_fails_closed(monkeypatch):
    monkeypatch.setattr("core.services.quality.judge.build_evaluation_prompt", lambda *a, **k: "prompt")
    llm = MagicMock()
    llm.generate_json.return_value = {"overall_pass": True, "issues": [], "ac_coverage": {"1": True}}
    checker = QARulesChecker("Sign out of the app", ac_count=2)
    judge = LLMJudge(llm, max_rounds=1, auto_fix=False,
                     rule_checker=lambda tcs: to_judge_issues(checker.check(tcs)))
    tc = _tc([{"action": "Sign in as Admin A.", "expected": "Signed in."},
              {"action": "Restore the database snapshot of the user table.", "expected": "Data reset."}])
    verdict = judge.evaluate([tc], {"story_id": "1", "title": "t", "description": ""}, ["a", "b"], None, None)
    cats = {i.category for i in verdict.issues}
    assert IssueCategory.LETTERED_ROLE in cats and IssueCategory.DATABASE_CHANGE in cats
    assert verdict.passed is False and verdict.critical_count >= 1
    assert "2" in verdict.uncovered_acs


def test_to_judge_issues_severity_mapping():
    findings = QARulesChecker("x").check([_tc([{"action": "Ask the team to confirm the mapping (TBD).", "expected": "ok"}])])
    issues, _ = to_judge_issues(findings)
    inline = [i for i in issues if i.category == IssueCategory.INLINE_COMMENT]
    assert inline and inline[0].severity == IssueSeverity.MAJOR


# --- Anthropic provider --------------------------------------------------------------

def test_anthropic_request_for_current_models():
    p = AnthropicProvider(api_key="k", model="opus")
    req = p._build_request("q", "sys", {"max_tokens": 8192, "temperature": 0.2})
    assert req["model"] == "claude-opus-5-5"
    assert req["max_tokens"] >= 32000                      # thinking shares the budget
    assert req["output_config"]["effort"] == "high"         # Opus 5.5 defaults to medium otherwise
    assert "temperature" not in req and req["cache_control"] == {"type": "ephemeral"}


def test_anthropic_stream_uses_default_fallbacks():
    p = AnthropicProvider(api_key="k", model="claude-sonnet-5-5")
    msg = MagicMock(stop_reason="end_turn", content=[MagicMock(type="text", text='{"ok": true}')], model="claude-sonnet-5-5")
    msg.usage.input_tokens, msg.usage.output_tokens = 1, 1
    client = MagicMock()
    client.beta.messages.stream.return_value.__enter__.return_value.get_final_message.return_value = msg
    p._client = client
    assert p.generate_json("q") == {"ok": True}
    kwargs = client.beta.messages.stream.call_args.kwargs
    assert kwargs["betas"] == ["server-side-fallback-2026-07-01"]
    assert kwargs["extra_body"] == {"fallbacks": "default"}


def test_anthropic_older_model_gets_no_effort_or_fallback():
    p = AnthropicProvider(api_key="k", model="claude-sonnet-5", max_tokens=8000)
    req = p._build_request("q", None, {})
    assert "output_config" not in req and req["max_tokens"] == 8000


# --- config matching fixes ------------------------------------------------------------

def test_unavailable_feature_matches_whole_words_only():
    from projects.project_config import _word_in
    assert not _word_in("SSO", "users associated with the agency")
    assert _word_in("SSO", "sign in with sso")


def test_qa_prep_keywords_match_whole_words_only():
    from projects.test_suite_creator import _has_word
    assert not _has_word("a controlled prototype", "role", "type")
    assert _has_word("the user role changes", "role")


def test_missed_scenario_is_an_issue_not_an_ac_number():
    tc = _tc([{"action": "Save the form.", "expected": "The form is saved."}])
    issues, uncovered = to_judge_issues(
        QARulesChecker("x", ac_count=2, ac_texts=["Cancelling leaves data unchanged."]).check([tc]))
    assert uncovered == ["2"]
    assert any(i.test_case_id == "story" and i.category == IssueCategory.MISSING_AC_COVERAGE for i in issues)


def test_strict_normalization_keeps_filled_templates_and_merges_prereq():
    from types import SimpleNamespace

    from core.services.llm.corrector import LLMCorrector
    app = SimpleNamespace(name="App", get_prereq_step=lambda: "Pre-req: Non-production environment. <Role name>: <definition>.",
                          get_launch_step=lambda: "Sign in as the <Role name from the Pre-req>.", launch_expected="The user is signed in.",
                          get_create_file_step=lambda: "", create_file_expected="", get_close_step=lambda: "Sign out of the app.",
                          supported_platforms=["Chrome"], setup_step_policy="never")
    cfg = SimpleNamespace(application=app, qa_rules=SimpleNamespace(strict_grounding=True),
                          rules=SimpleNamespace(test_id_increment=5, first_test_id="AC1"), llm_provider="openai")
    c = LLMCorrector(api_key="x", model="m", project_config=cfg, provider_type="openai")
    tc = {"id": "x", "title": "Area / Component / Behavior", "steps": [
        {"action": "Pre-req: Non-production environment. <Role name>: <definition>.", "expected": ""},
        {"action": "Standard User: a newly created user.", "expected": ""},
        {"action": "Sign in as the <Role name from the Pre-req>.", "expected": "The user is signed in."},
        {"action": "Sign in as the Standard User.", "expected": "The user is signed in."},
    ]}
    out = c._post_process_corrections([tc], "9")[0]
    assert out["title"] == "9-AC1: Area / Component / Behavior"
    assert out["steps"][0]["action"] == "Pre-req: Non-production environment. Standard User: a newly created user."
    assert [s["action"] for s in out["steps"][1:]] == ["Sign in as the Standard User.", "Sign out of the app."]
