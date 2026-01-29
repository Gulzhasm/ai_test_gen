"""
LLM-Powered Test Case Generator
Uses OpenAI to generate comprehensive, rule-compliant test cases.
"""
import json
import os
from typing import Optional, Dict, List, Any

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


SYSTEM_PROMPT = """You are a QA Test Case Generator for Azure DevOps. Your output must be deterministic, comprehensive, and strictly rule-compliant. You must not invent requirements. You must rely only on the provided: Description, Acceptance Criteria, and QA Prep text.

You MUST follow these constraints:

A) Coverage & Ordering
- Generate test cases top-to-bottom in the exact order of Acceptance Criteria bullets.
- AC1 is mandatory and acceptance-level only (availability/entry point only).
- After AC1, IDs increment by 5: 005, 010, 015, ...
- One PRIMARY test case per acceptance bullet covering the main/positive scenario.
- ADDITIONAL test cases for edge cases, negative scenarios, and boundary conditions derived from AC and QA Prep.
- Edge case test cases should immediately follow their parent AC test case before moving to the next AC bullet.
- Edge case IDs continue the increment sequence (e.g., AC bullet 2 primary = 005, edge case = 010, AC bullet 3 primary = 015).

B) Deterministic Language (Strict) - CRITICAL
Forbidden anywhere in Step Action / Step Expected:
- "or", "OR" as alternatives (e.g., "click or tap" is FORBIDDEN)
- "if available"
- "if supported"
- optional/conditional phrasing
- ambiguous alternatives

EXCEPTION: "/" used in menu item names like "Show Grid / Hide Grid" is allowed because it's the actual UI label.

MANDATORY HANDLING OF ALTERNATIVES:
When you encounter alternatives in acceptance criteria (e.g., "user can drag or resize"):
1. NEVER write "drag or resize" in a single step
2. ALWAYS split into SEPARATE SEQUENTIAL STEPS:
   - Step N: "Drag the label to a new position" → Expected: "Label moves to the new position"
   - Step N+1: "Resize the label using corner handles" → Expected: "Label resizes accordingly"
3. Each alternative action gets its own step with its own expected result
4. This ensures deterministic, unambiguous test execution

Examples of FORBIDDEN vs CORRECT:
FORBIDDEN: "Click or tap the button"
CORRECT: Split into two steps - "Click the button" AND "Tap the button"

FORBIDDEN: "Label repositions automatically or manually"
CORRECT: Two separate steps testing automatic AND manual repositioning

FORBIDDEN: "Object snaps to grid or stays in place"
CORRECT: Two separate verification steps for each behavior

C) Object Setup Rule (No Assumptions)
If a test requires an object:
- Do not assume an object exists.
- Add setup steps to create it: "Draw a shape (e.g., rectangle) on the Canvas." Then "Select the created object."
- Never assume an object exists.

D) Step Rules (Mandatory)
Every test case MUST:
- Start with Step 1: "PRE-REQ: ENV QuickDraw application is installed"
- End with final step: "Close/Exit the QuickDraw application"
- Final step must have NO expected result.
Do NOT add expected results for routine steps:
- PRE-REQ
- Launch app
- Enable accessibility tools
- Close/Exit app
Expected results only for verification/validation/error handling steps.
All verification steps MUST have expected results that are specific, observable, and unambiguous.

E) Titles (Balanced, Reviewer-Proof)
Use exact title format: <StoryID>-XXX: <FeatureName> / <Area> / <Scenario>
- Area must be a specific UI surface: Canvas, View Menu, Edit Menu, File Menu, Properties Panel, Dimensions Panel, Dialog, Window Menu, Top Action Toolbar
- DO NOT use the ADO Area Path (like "Env\\ENV Kanda") as the Area - use UI surface names instead
- Scenario must be specific (what + where + outcome) without being too long.
- Device suffix ONLY for accessibility tests: (Windows 11), (iPad), (Android Tablet)

F) Accessibility Tests
Accessibility tests must be separate test cases and include device in title.
Tool PRE-REQs are mandatory:
- Windows 11: "PRE-REQ: Accessibility Insights for Windows tool is installed"
- iPad: "PRE-REQ: Apple built-in accessibility tools are available and enabled (VoiceOver)"
- Android Tablet: "PRE-REQ: Accessibility Scanner (Google) Free tool is installed"

Accessibility validations must include:
- focus visibility + focus order
- readable labels + control roles
- keyboard navigation ONLY for Windows 11
- touch/assistive gestures for tablets (no keyboard wording for tablets)

G) Edge-Case & Determinism Enhancer (MANDATORY)

1. Toggle/Stateful Features:
   If an acceptance bullet describes a toggle, you MUST verify:
   - The visible UI outcome (on/off effect), AND
   - The menu/state label changes to reflect the current state (e.g., "Show Grid" becomes "Hide Grid" after enabling).
   Do NOT assume a toggle exists outside the described entry point.

2. "Does not affect" / "does not change behavior" Constraints:
   For any acceptance bullet that says the feature does NOT affect objects, snapping, movement, behavior, or drawing:
   - Add deterministic steps that demonstrate normal behavior with measurable/observable outcomes.
   - Replace ambiguous verbs like "attempt to snap" with defined actions:
     Example: "Drag the object slowly across multiple grid intersections."
     Expected: "Movement is continuous; object does not jump or align automatically."

3. Persistence Scope Discipline:
   - "Session-based persistence" means: state persists while the application remains open.
   - Do NOT test persistence across application restart unless the acceptance criteria explicitly states it persists after restart.
   - Use same-session transitions to validate persistence:
     * Open/close project
     * Create new drawing
     * Switch between drawings
     * Return to home screen (if applicable)
   - Do NOT relaunch the app unless explicitly required.

4. Edge Case Test Cases (SEPARATE TEST CASES):
   Create SEPARATE test cases (not just extra steps) for:
   - Boundary states (already on/off, minimum/maximum values, empty states)
   - Negative scenarios (invalid input, error conditions, cancel operations)
   - Repeated action stability (toggle on/off multiple times)
   - State transitions (switching between states rapidly)
   - Persistence verification (state maintained across navigation)
   - No side-effects verification (other elements unchanged)

   Each edge case test case must:
   - Have its own unique ID in the sequence
   - Have a descriptive title indicating the edge case scenario
   - Follow immediately after the primary AC test case it relates to

H) Output Format
Return ONLY valid JSON matching the schema. No markdown. No commentary.

I) Final Self-Validation Before Returning JSON (MANDATORY)
Before returning output, re-check every test case:
1. AC1 only checks entry-point availability.
2. IDs: AC1 then increment by 5.
3. Every test begins with PRE-REQ step and ends with Close/Exit (no expected on final step).
4. No forbidden words appear anywhere in Step Action/Expected.
5. Toggle tests include BOTH visible effect and menu label/state change verification.
6. "Does not affect" bullets include at least one deterministic interaction proof (drag/draw) with a measurable expected result.
7. "Session-based persistence" tests do NOT include application restart unless explicitly required.
8. Accessibility tests: device split + correct tool PRE-REQ + device-appropriate interaction language (no keyboard navigation wording for tablets).
9. Title Area field is a UI surface (Canvas, View Menu, etc.), NOT the ADO Area Path.

If any violation exists, correct it before returning JSON.
Return JSON only."""


class LLMTestGenerator:
    """Generates test cases using OpenAI LLM."""

    # Generation modes
    MODE_STANDARD = "standard"      # Minimal steps, meets AC
    MODE_COMPREHENSIVE = "comprehensive"  # Adds deterministic edge checks within each AC scope

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.2,
        mode: str = "comprehensive"  # Default to comprehensive mode
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.temperature = temperature
        self.mode = mode
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> Optional[OpenAI]:
        if self._client is None and OPENAI_AVAILABLE and self.api_key:
            self._client = OpenAI(api_key=self.api_key, timeout=120)
        return self._client

    def generate_test_cases(
        self,
        story_id: str,
        feature_name: str,
        description: str,
        acceptance_criteria: List[str],
        qa_prep: str,
        area_path: str = "Env\\ENV Kanda",
        assigned_to: str = "gulzhas.mailybayeva@kandasoft.com"
    ) -> Optional[Dict[str, Any]]:
        """Generate test cases from story data using LLM.

        Generation mode affects output:
        - "standard": Minimal steps that meet AC requirements
        - "comprehensive": Adds deterministic edge checks within each AC scope (default)
        """

        if not self.client:
            print("OpenAI client not available. Check API key.")
            return None

        # Format acceptance criteria as numbered list
        ac_formatted = "\n".join([f"{i+1}. {ac}" for i, ac in enumerate(acceptance_criteria)])

        # Mode-specific instructions
        mode_instructions = ""
        if self.mode == self.MODE_COMPREHENSIVE:
            mode_instructions = """
GENERATION MODE: COMPREHENSIVE

For EACH AC bullet, create: 1 PRIMARY test + 1-2 EDGE CASE tests (separate test cases, not extra steps).
Target: ~2x the number of AC bullets in total test cases.

Edge cases (as SEPARATE test cases): boundary states, negative scenarios, repeated actions, persistence, empty state, multiple objects.
"""
        else:
            mode_instructions = """
GENERATION MODE: STANDARD
- One test case per acceptance bullet (primary scenario only)
- Minimal steps that meet AC requirements
- Focus on primary acceptance verification only
- No separate edge case test cases
"""

        user_prompt = f"""Generate test cases for the following ADO work item.
{mode_instructions}

Story ID: {story_id}
Feature Name (must match exactly in titles): {feature_name}
Area Path: {area_path}
Assigned To: {assigned_to}
State: Design

User Story Description:
{description}

Acceptance Criteria (ordered):
{ac_formatted}

QA Prep Subtask Text (Human QA Planning Summary / Notes):
{qa_prep}

Output required - Return JSON only, matching this schema:
{{
  "test_cases": [
    {{
      "id_suffix": "AC1" | "005" | "010" | ...,
      "title": "<StoryID>-<id_suffix>: <FeatureName> / <Area> / <Scenario>",
      "work_item_type": "Test Case",
      "area_path": "{area_path}",
      "assigned_to": "{assigned_to}",
      "state": "Design",
      "steps": [
        {{ "step": 1, "action": "PRE-REQ: ENV QuickDraw application is installed", "expected": "" }},
        ...
        {{ "step": N, "action": "Close/Exit the QuickDraw application", "expected": "" }}
      ]
    }}
  ]
}}

IMPORTANT REMINDERS:
- AC1 must verify entry point/availability only (View Menu toggle is visible and accessible).
- After AC1, id_suffix increments by 5: 005, 010, 015...
- One PRIMARY test case per acceptance criterion bullet for the main/positive scenario.
- Create ADDITIONAL SEPARATE test cases for edge cases derived from AC and QA Prep (each with unique ID).
- Edge case test cases follow immediately after their related primary AC test case.
- Include specific, actionable steps - NOT generic "Perform action as described in AC".
- Expected results only for verification steps.
- NO usage of "or", "OR", "if available", "if supported" anywhere.
- For toggle features: test the toggle state change and verify label updates.
- For "does not affect" criteria: use deterministic actions like "Drag the object slowly across grid intersections" with measurable outcomes.
- Session-based persistence: test within same session (create new drawing, switch drawings) - do NOT restart the app.
- Analyze QA Prep text carefully for additional test scenarios that should become separate test cases.

MANDATORY FINAL TESTS (in this order, at the end):
1. Tablet Functional Test (if canvas/touch interaction): ONE test covering iPad+Android touch gestures (tap, drag, pinch). Title: "...(Tablet)"
2. Windows 11 Accessibility: keyboard navigation + Accessibility Insights
3. iPad Accessibility: VoiceOver + touch (NO keyboard)
4. Android Accessibility: Accessibility Scanner + touch (NO keyboard)

Return JSON only."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                max_tokens=10000,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            result = json.loads(content)

            # Post-process validation
            result = self._validate_and_fix(result, story_id, feature_name)

            return result

        except Exception as e:
            print(f"LLM test generation error: {e}")
            return None

    def generate_objectives(
        self,
        test_cases: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Generate objectives for test cases."""

        if not self.client:
            return None

        # Format test case list
        tc_list = "\n".join([
            f"- {tc.get('id_suffix', 'XX')}: {tc.get('title', 'Unknown')}"
            for tc in test_cases
        ])

        user_prompt = f"""Generate test objectives mapped 1:1 to the following test cases.

Rules:
- Exactly one objective per test case.
- Start every objective with: "Objective: Verify that..."
- Use QA validation language focused on intent, not steps.
- Do not repeat full acceptance criteria verbatim.
- Add bold emphasis using <b>...</b> around key terms.
- Accessibility objectives must mention the device and tool used.

Test cases (IDs + Titles):
{tc_list}

Output required (JSON only):
{{
  "objectives": [
    {{
      "test_case_id": "<ID>",
      "title": "<Title>",
      "objective": "Objective: Verify that ... with <b>bold</b> highlights"
    }}
  ]
}}

Return JSON only."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You generate test objectives for QA test cases. Output JSON only."},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            return json.loads(content)

        except Exception as e:
            print(f"LLM objectives generation error: {e}")
            return None

    def _validate_and_fix(
        self,
        result: Dict[str, Any],
        story_id: str,
        feature_name: str
    ) -> Dict[str, Any]:
        """Validate and fix common issues in generated test cases.

        Performs comprehensive validation including:
        - PRE-REQ and Close/Exit step enforcement
        - Forbidden pattern detection
        - ID sequence validation
        - Accessibility test validation
        - Expected result balancing
        """

        test_cases = result.get("test_cases", [])
        validation_issues = []

        # Check for actual forbidden patterns, not "/" in menu names
        forbidden_patterns = [
            " or ",  # "or" with spaces (alternative)
            " OR ",  # "OR" with spaces
            "if available",
            "if supported",
            "if applicable"
        ]

        # Validate ID sequence
        expected_ids = ["AC1"]
        for i in range(1, 50):  # Up to 50 test cases
            expected_ids.append(f"{i*5:03d}")

        has_ac1 = False
        id_sequence_valid = True

        for idx, tc in enumerate(test_cases):
            tc_id = tc.get("id_suffix", "")
            title = tc.get("title", "")
            steps = tc.get("steps", [])

            # Check AC1 exists
            if tc_id == "AC1":
                has_ac1 = True

            # Validate ID sequence
            if idx < len(expected_ids) and tc_id != expected_ids[idx]:
                if idx == 0 and tc_id != "AC1":
                    validation_issues.append(f"First test case should be AC1, got {tc_id}")
                    id_sequence_valid = False

            # Ensure first step is PRE-REQ
            if steps and "PRE-REQ" not in steps[0].get("action", ""):
                steps.insert(0, {
                    "step": 1,
                    "action": "PRE-REQ: ENV QuickDraw application is installed",
                    "expected": ""
                })

            # Ensure last step is Close/Exit with no expected
            if steps:
                last_step = steps[-1]
                if "Close" not in last_step.get("action", "") and "Exit" not in last_step.get("action", ""):
                    steps.append({
                        "step": len(steps) + 1,
                        "action": "Close/Exit the QuickDraw application",
                        "expected": ""
                    })
                else:
                    last_step["expected"] = ""

            # Renumber steps
            for i, step in enumerate(steps):
                step["step"] = i + 1

            # Clear expected for routine steps (PRE-REQ, Launch, Close, Enable tools)
            routine_keywords = ["pre-req", "launch", "close/exit", "close the", "exit the", "enable accessibility", "enable voiceover", "enable talkback"]
            for step in steps:
                action = step.get("action", "").lower()
                if any(kw in action for kw in routine_keywords):
                    step["expected"] = ""

            # Check for forbidden patterns
            for step in steps:
                action = step.get("action", "")
                expected = step.get("expected", "")
                for pattern in forbidden_patterns:
                    if pattern.lower() in action.lower():
                        validation_issues.append(f"Forbidden pattern '{pattern.strip()}' in action: {action[:50]}")
                    if pattern.lower() in expected.lower():
                        validation_issues.append(f"Forbidden pattern '{pattern.strip()}' in expected: {expected[:50]}")

            # Validate accessibility tests
            title_lower = title.lower()
            if "accessibility" in title_lower or "windows 11" in title_lower or "ipad" in title_lower or "android" in title_lower:
                # Check for correct tool PRE-REQ
                has_tool_prereq = False
                has_keyboard_for_tablet = False

                for step in steps:
                    action = step.get("action", "")
                    action_lower = action.lower()

                    if "accessibility insights" in action_lower or "voiceover" in action_lower or "accessibility scanner" in action_lower:
                        has_tool_prereq = True

                    # Check for keyboard navigation in tablet tests
                    if ("ipad" in title_lower or "android" in title_lower) and "keyboard" in action_lower:
                        has_keyboard_for_tablet = True

                if has_keyboard_for_tablet:
                    validation_issues.append(f"Tablet test has keyboard navigation: {title[:50]}")

            tc["steps"] = steps

        # Validation summary
        if not has_ac1:
            validation_issues.append("Missing AC1 test case")

        if validation_issues:
            print(f"\nValidation Issues Found ({len(validation_issues)}):")
            for issue in validation_issues[:10]:  # Show first 10
                print(f"  - {issue}")
            if len(validation_issues) > 10:
                print(f"  ... and {len(validation_issues) - 10} more")

        result["test_cases"] = test_cases
        result["_validation_issues"] = validation_issues

        # If there are "or" violations, attempt to fix them using LLM
        or_violations = [v for v in validation_issues if "'or'" in v.lower()]
        if or_violations and self.client:
            print(f"\n  Attempting to fix {len(or_violations)} 'or' violation(s) using LLM...")
            result = self._fix_or_violations(result)

        return result

    def _fix_or_violations(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Use LLM to fix steps containing 'or' by splitting into separate steps."""

        test_cases = result.get("test_cases", [])
        steps_to_fix = []

        # Find all steps with "or" violations
        for tc_idx, tc in enumerate(test_cases):
            for step_idx, step in enumerate(tc.get("steps", [])):
                action = step.get("action", "")
                expected = step.get("expected", "")
                if " or " in action.lower() or " or " in expected.lower():
                    steps_to_fix.append({
                        "tc_idx": tc_idx,
                        "step_idx": step_idx,
                        "tc_id": tc.get("id_suffix", ""),
                        "action": action,
                        "expected": expected
                    })

        if not steps_to_fix:
            return result

        # Build prompt to fix the violations
        violations_text = "\n".join([
            f"Test {s['tc_id']} Step {s['step_idx']+1}:\n  Action: {s['action']}\n  Expected: {s['expected']}"
            for s in steps_to_fix
        ])

        fix_prompt = f"""Fix the following test steps that contain the forbidden word "or".

RULE: Split each step containing "or" into MULTIPLE SEPARATE STEPS.
Each alternative action must be its own step with its own expected result.

Steps to fix:
{violations_text}

Return JSON with fixed steps for each violation:
{{
  "fixes": [
    {{
      "tc_id": "<test case id>",
      "original_step_idx": <original step index>,
      "replacement_steps": [
        {{"action": "<action 1 without or>", "expected": "<expected 1>"}},
        {{"action": "<action 2 without or>", "expected": "<expected 2>"}}
      ]
    }}
  ]
}}

IMPORTANT:
- Each replacement step must NOT contain "or" or "OR"
- Split alternatives into separate sequential steps
- Preserve the meaning and intent of the original step
- Each step must have a specific, deterministic expected result

Return JSON only."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You fix test steps by splitting 'or' alternatives into separate steps. Output JSON only."},
                    {"role": "user", "content": fix_prompt}
                ],
                temperature=0.1,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            fixes = json.loads(content)

            # Apply fixes (in reverse order to maintain step indices)
            for fix in reversed(fixes.get("fixes", [])):
                tc_id = fix.get("tc_id", "")
                original_idx = fix.get("original_step_idx", 0)
                replacement_steps = fix.get("replacement_steps", [])

                # Find the test case
                for tc in test_cases:
                    if tc.get("id_suffix") == tc_id:
                        steps = tc.get("steps", [])
                        if 0 <= original_idx < len(steps):
                            # Remove original step and insert replacements
                            steps.pop(original_idx)
                            for i, new_step in enumerate(replacement_steps):
                                steps.insert(original_idx + i, {
                                    "step": original_idx + i + 1,
                                    "action": new_step.get("action", ""),
                                    "expected": new_step.get("expected", "")
                                })

                            # Renumber all steps
                            for i, step in enumerate(steps):
                                step["step"] = i + 1

                            tc["steps"] = steps
                        break

            # Clear validation issues related to "or"
            result["_validation_issues"] = [
                v for v in result.get("_validation_issues", [])
                if "'or'" not in v.lower()
            ]

            print(f"  Fixed {len(fixes.get('fixes', []))} 'or' violation(s)")

        except Exception as e:
            print(f"  Warning: Could not auto-fix 'or' violations: {e}")

        result["test_cases"] = test_cases
        return result


def convert_to_csv_format(test_cases: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Convert LLM output to ADO CSV format."""
    rows = []

    for tc in test_cases:
        title = tc.get("title", "")
        area_path = tc.get("area_path", "Env\\ENV Kanda")
        assigned_to = tc.get("assigned_to", "")
        state = tc.get("state", "Design")
        steps = tc.get("steps", [])

        # First row: test case header
        rows.append({
            "ID": "",
            "Work Item Type": "Test Case",
            "Title": title,
            "TestStep": "",
            "Step Action": "",
            "Step Expected": "",
            "Area Path": area_path,
            "AssignedTo": assigned_to,
            "State": state
        })

        # Step rows
        for step in steps:
            rows.append({
                "ID": "",
                "Work Item Type": "",
                "Title": "",
                "TestStep": str(step.get("step", "")),
                "Step Action": step.get("action", ""),
                "Step Expected": step.get("expected", ""),
                "Area Path": "",
                "AssignedTo": "",
                "State": ""
            })

    return rows
