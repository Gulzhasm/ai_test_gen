"""
Judge Prompt Templates - System prompts and prompt builders for the Judge LLM layer.

The Judge evaluates ALL test cases in a single prompt to detect cross-test
issues (duplicates, missing AC coverage) that per-test analysis cannot catch.
"""
import json
from typing import List, Dict


JUDGE_SYSTEM_PROMPT = """You are a senior QA review specialist. Your job is to validate test cases written by another engineer. You are NOT the author — you are the independent reviewer.

IMPORTANT: Be precise and balanced. Flag real issues that would cause problems for a tester, but do NOT flag false positives. For each potential issue, verify it actually violates the rule before flagging it.

You check for these 9 categories of defects (in priority order):

1. FORBIDDEN LANGUAGE (Critical): The word 'or' is forbidden ONLY when it creates ambiguity about WHAT ACTION to perform — e.g., "Click Save or Export" (which one?), "Select A or B" (which one?), "Press Enter or click OK" (which one?). Each action step must have exactly ONE unambiguous instruction.
   - DO flag: "Click Rotate or Mirror" (ambiguous action), "if available, click Save" (conditional)
   - Do NOT flag: "no errors or warnings" (describing a state, not an action), "PDF or physical printer" in a title/description (naming the feature), "enabled or disabled" in expected results (describing possible states to verify one of)
   - Also flag: 'if available', 'if supported', 'either...or', 'and/or', 'optionally' — ONLY in action steps that create conditional behavior.

2. HALLUCINATED CONTENT (Critical): Flag ONLY when a test step references a specific UI element (menu, button, panel, dialog) that does NOT exist in the APPLICATION CONFIG ui_surfaces list AND is NOT mentioned in the story description or acceptance criteria. Generic terms like "dialog", "button", "checkbox" do not need to match the ui_surfaces list. Also flag any terms from the FORBIDDEN UI TERMS list.

3. LOGICAL CONTRADICTION (Major): Steps must not contradict each other or the acceptance criteria. Flag only clear logical impossibilities, not minor wording differences.

4. MISSING AC COVERAGE (Major): Flag if an acceptance criterion is NOT fully covered by actual test STEPS (not just title or objective text). Pay special attention to COMPOUND ACs that contain multiple distinct behaviors joined by semicolons or commas (e.g., "'Create' initializes a new canvas; 'Close' exits without creating" requires BOTH "Create" AND "Close" to have dedicated test steps). If a test title mentions both behaviors but steps only exercise one, that is STILL a gap — flag the missing part. Check the steps array, not the title.

5. DUPLICATE / OVERLAPPING TESTS (Minor): Flag only test cases with nearly identical step sequences. Different tests for the same feature from different angles are NOT duplicates.

6. MISSING SETUP / PRECONDITION (Minor): Flag only when a test performs object manipulation (rotate, move, delete, resize, transform, flip, mirror) WITHOUT any prior step that creates or selects an object. Do NOT flag if a setup step exists earlier in the sequence.

7. INCONSISTENT TERMINOLOGY (Minor): Flag only when the exact same UI element is called by different names across test cases (e.g., "Tools Menu" vs "Tool Menu"). Minor phrasing differences are acceptable.

8. INCONSISTENT STEP STRUCTURE (Major): All test cases must follow the same step pattern. Flag test cases that are missing standard steps that other tests consistently include. For example, if most tests have a "Pre-req" step, a "Launch" step, and a "Close" step, flag any test that skips the Launch step or combines multiple actions into one step (e.g., "Navigate to File → New" instead of separate "Launch app" + "Open File Menu" + "Select command" steps).

9. EMPTY EXPECTED RESULT (Minor): Flag middle steps (not step 1 Pre-req, not final Close step) that have an empty or missing expected result. Every action step between setup and teardown should describe what the tester observes.

CRITICAL: If a test case has NO real issues, do NOT invent issues. It is perfectly acceptable for all test cases to pass. An empty issues array is a valid result.

OUTPUT: Return ONLY valid JSON matching the schema provided. No markdown, no explanation, no preamble."""


JUDGE_FIX_SYSTEM_PROMPT = """You are a senior QA engineer fixing issues found during test case review. You receive the original test cases and a list of specific issues. Fix ONLY the identified issues — do not change anything else.

Rules:
- Replace forbidden words ('or', 'if', 'either') by splitting into separate deterministic steps
- Replace hallucinated UI names with the correct names from the app config
- Fix logical contradictions by correcting the step sequence
- For MISSING AC COVERAGE on compound ACs: if one part of a compound AC is already tested (e.g., "Create" is tested but "Close" is not), ADD the missing verification steps to the existing test case. For example, add steps to reopen the dialog, click "Close", and verify the dialog exits without creating. Do NOT add entirely new test cases — only expand existing ones.
- Remove duplicate test cases, keeping the more complete version
- Add missing setup steps (object creation, file creation) where needed
- Standardize terminology to match the app config and the MANDATORY STEP PATTERN
- Fix inconsistent step structure: expand combined steps into separate steps matching the MANDATORY STEP PATTERN (Pre-req → Launch → Navigate → Actions → Close)
- Fix inconsistent terminology: use the exact wording from other test cases (e.g., "File Menu opens." not "File menu should be displayed.")
- Add expected results to middle steps that have empty expected results

OUTPUT: Return ONLY valid JSON — an array of corrected test cases matching the original structure."""


def build_evaluation_prompt(
    test_cases: List[Dict],
    story_data: Dict,
    acceptance_criteria: List[str],
    app_config,
    rules,
) -> str:
    """Build the full evaluation prompt with all context."""

    # Story context
    story_section = f"""## STORY CONTEXT
- Story ID: {story_data.get('story_id', 'N/A')}
- Title: {story_data.get('title', 'N/A')}
- Description: {(story_data.get('description', '') or '')[:800]}"""

    # Acceptance criteria
    ac_lines = []
    for i, ac in enumerate(acceptance_criteria, 1):
        ac_lines.append(f"  {i}. {ac}")
    ac_section = "## ACCEPTANCE CRITERIA\n" + "\n".join(ac_lines)

    # App config
    ui_surfaces = getattr(app_config, 'main_ui_surfaces', [])
    entry_points = getattr(app_config, 'entry_point_mappings', {})
    forbidden_ui = getattr(app_config, 'forbidden_ui_terms', [])
    unavailable = getattr(app_config, 'unavailable_features', [])
    object_keywords = getattr(app_config, 'object_interaction_keywords', [])

    # Step templates for structure validation
    app_name = getattr(app_config, 'name', 'App')
    prereq = getattr(app_config, 'prereq_template', 'Pre-req: The {app_name} App is installed').format(app_name=app_name)
    launch = getattr(app_config, 'launch_step', 'Launch the {app_name} application.').format(app_name=app_name)
    launch_exp = getattr(app_config, 'launch_expected', '') or ''
    close = f"Close the {app_name} App"

    app_section = f"""## APPLICATION CONFIG
- App Name: {app_name}
- Valid UI Surfaces: {', '.join(ui_surfaces)}
- Valid Entry Points: {json.dumps(entry_points, indent=2)}
- FORBIDDEN UI Terms (do NOT exist in the app): {', '.join(forbidden_ui)}
- Unavailable Features (do NOT exist): {', '.join(unavailable)}
- Object Interaction Keywords (require setup): {', '.join(object_keywords)}

## MANDATORY STEP PATTERN (all tests must follow):
- Step 1: "{prereq}" (empty expected)
- Step 2: "{launch}" (expected: "{launch_exp}")
- Step 3+: Navigate to feature via separate steps (e.g., "Open the File Menu." then "Select the command.")
- Middle steps: Feature-specific actions with deterministic expected results (never empty)
- Last step: "{close}" (empty expected)
IMPORTANT: Steps must NOT combine multiple actions (e.g., "Navigate to File → New" should be separate Launch + Open Menu + Select command steps)."""

    # Rules
    forbidden_words = getattr(rules, 'forbidden_words', [])
    rules_section = f"""## RULES
- Forbidden Words in Steps: {', '.join(forbidden_words)}
- Additional forbidden: 'or', 'OR', 'if available', 'if supported', 'either', 'and/or', 'optionally'"""

    # Test cases
    tc_json = json.dumps(test_cases, indent=2)
    tc_section = f"""## TEST CASES TO REVIEW ({len(test_cases)} total)
```json
{tc_json}
```"""

    # Expected output
    output_section = """## EXPECTED OUTPUT
Return a JSON object with this exact structure:
```json
{
  "overall_pass": true/false,
  "issues": [
    {
      "test_case_id": "273167-AC1",
      "category": "forbidden_language|hallucinated_content|logical_contradiction|missing_ac_coverage|duplicate_overlap|missing_setup|inconsistent_terminology|inconsistent_step_structure|empty_expected_result",
      "severity": "critical|major|minor",
      "location": "step_3_action|step_2_expected|title|objective|set_level",
      "description": "Human-readable description of the issue",
      "violating_text": "The exact problematic text",
      "suggested_fix": "The corrected text"
    }
  ],
  "ac_coverage": {
    "1": true,
    "2": false
  },
  "duplicate_groups": [
    ["273167-010", "273167-015"]
  ]
}
```

Set "overall_pass" to true ONLY if there are zero critical and zero major issues.
For "ac_coverage", use the AC number (1-based index) as key, and true/false for whether it's covered.
For "duplicate_groups", list groups of test case IDs that overlap. Empty array if no duplicates.
If no issues found, return {"overall_pass": true, "issues": [], "ac_coverage": {...}, "duplicate_groups": []}."""

    return f"""{story_section}

{ac_section}

{app_section}

{rules_section}

{tc_section}

{output_section}"""


def build_fix_prompt(
    test_cases: List[Dict],
    issues: List[Dict],
    story_data: Dict,
    acceptance_criteria: List[str],
    app_config,
) -> str:
    """Build the fix prompt with issues and test cases."""

    # Compact story context with step templates for structure fixes
    prereq = getattr(app_config, 'prereq_template', 'Pre-req: The {app_name} App is installed').format(app_name=getattr(app_config, 'name', 'App'))
    launch = getattr(app_config, 'launch_step', 'Launch the {app_name} application.').format(app_name=getattr(app_config, 'name', 'App'))
    launch_exp = getattr(app_config, 'launch_expected', '') or ''
    close = getattr(app_config, 'close_step', 'Close the {app_name} App').format(app_name=getattr(app_config, 'name', 'App')) if hasattr(app_config, 'close_step') else f"Close the {getattr(app_config, 'name', 'App')} App"

    story_section = f"""## CONTEXT
- Story: {story_data.get('story_id', '')} - {story_data.get('title', '')}
- App: {getattr(app_config, 'name', 'N/A')}
- Valid UI Surfaces: {', '.join(getattr(app_config, 'main_ui_surfaces', []))}
- Forbidden UI Terms: {', '.join(getattr(app_config, 'forbidden_ui_terms', []))}

## MANDATORY STEP PATTERN (all tests must follow this):
- Step 1: "{prereq}" (empty expected)
- Step 2: "{launch}" (expected: "{launch_exp}")
- Step 3+: Navigate to the feature (separate steps for each action)
- Middle steps: Feature-specific actions with deterministic expected results
- Last step: "{close}" (empty expected)"""

    # AC for reference
    ac_lines = [f"  {i}. {ac}" for i, ac in enumerate(acceptance_criteria, 1)]
    ac_section = "## ACCEPTANCE CRITERIA\n" + "\n".join(ac_lines)

    # Issues to fix
    issues_json = json.dumps(issues, indent=2)
    issues_section = f"""## ISSUES TO FIX ({len(issues)} total)
```json
{issues_json}
```"""

    # Test cases
    tc_json = json.dumps(test_cases, indent=2)
    tc_section = f"""## TEST CASES TO CORRECT
```json
{tc_json}
```"""

    output_section = """## EXPECTED OUTPUT
Return a JSON object with a single key "test_cases" containing the corrected array:
```json
{
  "test_cases": [
    {
      "id": "...",
      "title": "...",
      "objective": "...",
      "steps": [
        {"action": "...", "expected": "..."},
        ...
      ]
    }
  ]
}
```

Rules:
- Fix ONLY the issues listed above. Do not change anything else.
- Preserve all test case IDs exactly as they are.
- For forbidden language: split "A or B" into separate steps, one per action.
- For hallucinated content: replace with correct names from the app config.
- For missing setup: add object creation/selection steps where needed.
- For duplicates: remove the less complete test case from the set.
- For inconsistent step structure: expand combined steps into separate steps following the MANDATORY STEP PATTERN above.
- For empty expected results: add specific, observable expected results for middle steps.
- Do NOT add new test cases. Only fix or remove existing ones."""

    return f"""{story_section}

{ac_section}

{issues_section}

{tc_section}

{output_section}"""
