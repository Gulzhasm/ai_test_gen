"""Tests for the reviewer-rule checker (hallucination and style rules)."""
from core.services.quality.qa_rules_checker import (
    ERROR,
    QARulesChecker,
    QARulesConfig,
    feedback_by_test,
    summarize,
)

SOURCES = """
As an authorized administrator, I want to find existing users and open their permitted
profile details. The approved list information columns are Signin, Name, Email, Record Status.
The Sign In page must display: Your password was changed successfully. Confirm New Password field.
APP_USER.REGION_ID stores the saved current region. The 30-minute inactivity timeout applies.
"""


def _tc(tc_id="100-AC1", title=None, steps=None, objective="Verify that the result list shows permitted users.", ac=(1,)):
    return {
        "id": tc_id,
        "title": title or f"{tc_id}: User Search / Result List / Shows Permitted Users",
        "objective": objective,
        "ac_refs": list(ac),
        "steps": steps or [
            {"action": "Pre-req: Non-production environment. Authorized Administrator: a user with administration-read permission.", "expected": ""},
            {"action": "Sign in as the Authorized Administrator.", "expected": "The Authorized Administrator is signed in."},
            {"action": "Search for a permitted user.", "expected": "The result list shows Signin, Name and Email."},
            {"action": "Sign out of the app.", "expected": ""},
        ],
    }


def _codes(findings, severity=ERROR):
    return {f.code for f in findings if f.severity == severity}


def test_clean_test_case_has_no_errors():
    findings = QARulesChecker(SOURCES, ac_count=1).check([_tc()])
    assert _codes(findings) == set()


def test_letter_roles_and_fixture_values_are_errors():
    steps = _tc()["steps"]
    steps[1] = {"action": "Sign in as Admin A with Pwd-Old.", "expected": "P1 and R1 are listed."}
    codes = [f.evidence for f in QARulesChecker(SOURCES).check([_tc(steps=steps)]) if f.code == "letter_role"]
    assert {"Admin A", "Pwd-Old", "P1", "R1"} <= set(codes)


def test_invented_menu_path_ui_name_and_quote_are_errors():
    steps = _tc()["steps"]
    steps[2] = {"action": "Open Admin Functions > Users and the User Maintenance Page.",
                "expected": "The message 'User saved successfully to the database' is displayed."}
    codes = _codes(QARulesChecker(SOURCES, QARulesConfig(legacy_terms=["User Maintenance Page"])).check([_tc(steps=steps)]))
    assert {"menu_path", "ungrounded_ui_name", "ungrounded_quote", "legacy_term"} <= codes


def test_quote_and_identifier_from_sources_are_allowed():
    steps = _tc()["steps"]
    steps[2] = {"action": "Query APP_USER.REGION_ID read-only.",
                "expected": "The Sign In page displays 'Your password was changed successfully.'"}
    assert _codes(QARulesChecker(SOURCES).check([_tc(steps=steps)])) == set()


def test_prereq_defined_terms_are_grounded():
    steps = _tc()["steps"]
    steps[0]["action"] = "Pre-req: Non-production environment. Shared Search Term: a term shared by all permitted users."
    steps[2] = {"action": "Search for the 'Shared Search Term'.", "expected": "The result list shows permitted users."}
    assert "ungrounded_quote" not in _codes(QARulesChecker(SOURCES).check([_tc(steps=steps)]))


def test_team_work_attribution_db_write_and_comments():
    steps = _tc()["steps"]
    steps[2] = {"action": "Review the developer's evidence.", "expected": "The mapping is documented and agreed (TBD)."}
    steps.insert(3, {"action": "Restore the database snapshot of the APP_USER table.", "expected": "Data is reset."})
    codes = _codes(QARulesChecker(SOURCES).check([_tc(steps=steps)]))
    assert {"attributed_evidence", "documented_check", "inline_comment", "db_change"} <= codes


def test_ui_label_containing_confirm_is_not_team_work():
    steps = _tc()["steps"]
    steps[2] = {"action": "Enter a value in the Confirm New Password field.", "expected": "The value is masked."}
    assert "team_work" not in {f.code for f in QARulesChecker(SOURCES).check([_tc(steps=steps)])}


def test_grammar_nor_and_unsourced_values():
    steps = _tc()["steps"]
    steps[2] = {"action": "Resize the browser to 375px.", "expected": "No name nor email is shown after 25 minutes."}
    codes = _codes(QARulesChecker(SOURCES).check([_tc(steps=steps)]))
    assert {"nor", "ungrounded_value"} <= codes


def test_value_stated_in_sources_is_allowed():
    steps = _tc()["steps"]
    steps[2] = {"action": "Wait 30 minutes without activity.", "expected": "The session expires."}
    assert "ungrounded_value" not in _codes(QARulesChecker(SOURCES).check([_tc(steps=steps)]))


def test_structure_rules():
    bad = _tc(title="100-AC1: Users can search", steps=[
        {"action": "Sign in.", "expected": "Signed in."},
        {"action": "Open the list and then select a user.", "expected": ""},
    ])
    findings = QARulesChecker(SOURCES).check([bad])
    assert {"title_pattern", "prereq_missing", "empty_expected"} <= _codes(findings)
    assert "compound_action" in {f.code for f in findings}


def test_prereq_state_claims_are_errors():
    steps = _tc()["steps"]
    steps[0]["action"] = "Pre-req: The QA setup is available and the import has been completed."
    assert "prereq_state_claim" in _codes(QARulesChecker(SOURCES).check([_tc(steps=steps)]))


def test_ac_coverage_and_synonyms():
    cfg = QARulesConfig(synonyms={"QA setup notes": "the provided setup instructions"})
    steps = _tc()["steps"]
    steps[2] = {"action": "Follow the QA setup notes.", "expected": "The result list shows permitted users."}
    findings = QARulesChecker(SOURCES, cfg, ac_count=3).check([_tc(steps=steps, ac=(1, 2))])
    assert any(f.code == "ac_uncovered" and f.location == "AC3" for f in findings)
    assert "synonym" in _codes(findings)


def test_feedback_and_summary_helpers():
    steps = _tc()["steps"]
    steps[1] = {"action": "Sign in as User N.", "expected": "Signed in."}
    findings = QARulesChecker(SOURCES).check([_tc(steps=steps)])
    fb = feedback_by_test(findings)
    assert "100-AC1" in fb and any("User N" in line for line in fb["100-AC1"])
    assert summarize(findings)["by_rule"]["R2"] >= 1
