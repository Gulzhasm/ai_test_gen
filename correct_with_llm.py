#!/usr/bin/env python3
"""
Hybrid Test Case Generator: Non-LLM Generation + LLM Correction

This script combines the best of both approaches:
1. Generate test cases using the fast, rule-based non-LLM generator (70% coverage)
2. Send to LLM for correction/enhancement only (cheaper & faster than full LLM generation)

LLM corrections include:
- Fix forbidden language ("or", "if available", etc.)
- Add missing edge cases identified from AC/QA Prep
- Ensure PRE-REQ and Close/Exit steps are present
- Validate deterministic language
- Add tablet functional test if missing
- Add accessibility tests if missing (Windows 11, iPad, Android)
- Validate ID sequence

Usage:
    python3 correct_with_llm.py --story-id 273167
    python3 correct_with_llm.py --story-id 273167 --skip-correction  # Generate without LLM
    python3 correct_with_llm.py --story-id 273167 --output-dir ./my_tests
"""
import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from infrastructure.ado import ADOStoryRepository
from infrastructure.export import CSVGenerator, ObjectiveGenerator
from core.services import GenericTestGenerator
from projects import get_project_manager
import config

# LLM correction imports
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


# Comprehensive correction prompt with all rules (based on approved 270479 patterns)
CORRECTION_SYSTEM_PROMPT = """You are a SENIOR QA TEST ENGINEER with 15+ years of experience. Your job is to CORRECT existing test cases AND ADD MISSING test cases to ensure comprehensive coverage.

## YOUR EXPERT QA RESPONSIBILITIES:
1. FIX any issues in existing test cases (formatting, language, structure)
2. ADD missing edge case tests
3. ADD missing negative tests
4. ADD missing boundary value tests
5. ADD missing error handling tests
6. ADD missing state transition tests
7. ENSURE complete test coverage for the feature

## A) TITLE RULES (CRITICAL)
Format: "<StoryID>-<ID>: <Feature> / <Area> / <Scenario>"

NOTE: Do NOT add platform suffixes like "(Windows 11)" or "(iPadOS/Android)" to regular test titles.
Platform configuration is handled separately in ADO. Only accessibility tests should specify platform.

ALLOWED Areas (behavior-based categories):
- Tool Availability (for AC1 availability tests)
- Tool Activation (for tool selection, cursor changes)
- Drawing Behavior (for creating shapes/objects)
- Editing Behavior (for modifying existing shapes)
- Edge Cases (for edge case tests)
- Negative Testing (for negative/error tests)
- Boundary Testing (for boundary value tests)
- Accessibility (ONLY for accessibility-specific tests)
- WCAG Compliance (for accessibility tests)

ALSO ALLOWED (concrete UI surfaces when behavior doesn't fit):
- Left Toolbar, Top Menu → Draw, Top Action Toolbar
- Properties Panel, Dimensions Panel, Canvas
- File Menu, Edit Menu, Tools Menu, View Menu, Help Menu
- Dialog Window, Modal Window, Settings, Undo/Redo

FORBIDDEN Areas (never use):
- Functionality, Behavior (alone), Validation, General, System

Scenario Rules:
- AC1: Use descriptive availability scenario like "Shape Tools Visible in Left Toolbar and Top Menu → Draw"
- Include entry point in scenario when relevant
- Must be specific: ACTION + TARGET + OUTCOME
- BAD: "Verify selected object", "Enable feature"
- GOOD: "Selecting a Shape Tool Updates Cursor to Crosshair", "Empty input field shows validation error"

## B) EXPECTED RESULT RULES (CRITICAL)
Steps that MUST have EMPTY expected results:
- PRE-REQ steps
- Close/Exit the application

Steps where expected is OPTIONAL (can be empty or brief):
- Launch application (can have: "Model space(Gray) and Canvas(white) space should be displayed")
- Select tool from toolbar (can be empty or brief state change)
- Move cursor to position
- Press and hold mouse button
- Simple action steps without verification intent

Steps that MUST have expected results:
- Observation steps ("Observe the Left Toolbar")
- Verification steps ("Verify...", "Check...")
- Action steps with observable outcome (drag, release with visual result)
- Expected must be SPECIFIC and OBSERVABLE

## C) FORBIDDEN LANGUAGE (HARD FAIL)
Remove from ALL step actions and expected results:
- "or" / "OR" as alternatives (split into separate steps or pick one)
- "if available", "if supported", "if applicable"
- "e.g., X or Y" patterns with alternatives
- Optional/conditional phrasing

## D) STEP STRUCTURE
1. First step: Pre-requisite step (empty expected) - typically "Pre-req: The application is installed" or similar
2. Second step: Launch/Navigate step with application-specific expected result
3. Last step: Close/Exit/Log out step (empty expected)

## E) ID SEQUENCE
- AC1 for first test (availability)
- Then increment by 5: 005, 010, 015, 020...

## F) MANDATORY TEST COVERAGE - ADD MISSING TESTS

### F1) EDGE CASE TESTS (ADD 3-5 edge case tests)
Think like an expert QA - what unusual but valid scenarios could break this feature?
- Empty states (no objects selected, empty canvas, empty input)
- Single item vs multiple items
- Maximum allowed items/values
- Minimum allowed items/values
- Special characters in text inputs
- Very long text/names
- Rapid repeated actions (double-click, triple-click)
- Action during loading/processing
- Interrupted operations (cancel mid-action)
- Session persistence (does state survive app restart?)

### F2) NEGATIVE TESTS (ADD 2-4 negative tests)
What should NOT work? Test invalid operations:
- Invalid input types (text where number expected)
- Out-of-range values
- Unsupported file formats
- Actions on wrong object types
- Actions without required selection
- Exceeding limits (max file size, max objects)
- Permission/access denied scenarios
- Network failure scenarios (if applicable)

### F3) BOUNDARY VALUE TESTS (ADD 2-3 boundary tests)
Test at the exact boundaries:
- Minimum value (0, 1, or defined minimum)
- Maximum value (defined maximum)
- Just below minimum (minimum - 1)
- Just above maximum (maximum + 1)
- Empty/null values
- Whitespace-only values

### F4) STATE TRANSITION TESTS (ADD 1-2 state tests)
Test state changes and persistence:
- Undo after action
- Redo after undo
- State after save/load
- State after switching tools
- State after deselect/reselect

### F5) ERROR HANDLING TESTS (ADD 1-2 error tests)
How does the app handle errors gracefully?
- Clear error messages displayed
- App doesn't crash on invalid input
- Recovery from error state
- Data not corrupted after error

## G) MANDATORY ACCESSIBILITY TESTS (at end, with platform in title)
These are the ONLY tests that should have platform specified:
1. Windows 11 Accessibility: keyboard + Accessibility Insights - title ends with "(Windows 11)"
2. iPad Accessibility: VoiceOver + touch (NO keyboard) - title ends with "(iPad)"
3. Android Tablet Accessibility: Accessibility Scanner + touch (NO keyboard) - title ends with "(Android Tablet)"

## H) CRITICAL: FEATURE-SPECIFIC CONTENT (FIX HARDCODED REFERENCES)
- NEVER reference "Diameter", "ellipse", "Dimensions Menu" in tests for unrelated features
- All tests MUST reference the actual feature being tested
- Replace hardcoded references with the actual feature name from the story

## I) OBJECTIVE FIELD FORMAT
Each test case MUST have an "objective" field that:
- Starts with "Verify that" (will be formatted as "<b>Objective:</b> Verify that...")
- Is specific and measurable
- Describes what the test validates
- Example: "Verify that the Rotate tool rotates selected objects 90 degrees clockwise"

## FINAL CHECKLIST BEFORE OUTPUT:
1. ✓ All existing tests corrected for formatting/language issues
2. ✓ At least 3-5 edge case tests added
3. ✓ At least 2-4 negative tests added
4. ✓ At least 2-3 boundary value tests added
5. ✓ At least 1-2 state/undo-redo tests included
6. ✓ At least 1-2 error handling tests added
7. ✓ 3 accessibility tests at the end (Windows, iPad, Android)
8. ✓ All tests have proper objective field
9. ✓ No forbidden language used
10. ✓ ID sequence is correct (AC1, then 005, 010, 015...)

Output corrected and enhanced JSON only: {"test_cases": [...]}"""


class LLMCorrector:
    """Corrects and enhances test cases using LLM."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini", app_config=None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self._client: Optional[OpenAI] = None
        self._app_config = app_config

        # Default step templates (can be overridden by app_config)
        self._app_name = "Application"
        self._prereq = "Pre-req: The application is installed"
        self._launch_expected = ""
        self._close = "Close the application"

        if app_config:
            self._app_name = getattr(app_config, 'name', self._app_name)
            if hasattr(app_config, 'get_prereq_step'):
                self._prereq = app_config.get_prereq_step()
            if hasattr(app_config, 'launch_expected'):
                self._launch_expected = app_config.launch_expected or ""
            if hasattr(app_config, 'get_close_step'):
                self._close = app_config.get_close_step()

    @property
    def client(self) -> Optional[OpenAI]:
        if self._client is None and OPENAI_AVAILABLE and self.api_key:
            self._client = OpenAI(api_key=self.api_key, timeout=90)
        return self._client

    def correct_test_cases(
        self,
        test_cases: List[Dict],
        story_id: str,
        feature_name: str,
        acceptance_criteria: List[str],
        qa_prep: str
    ) -> List[Dict]:
        """
        Send test cases to LLM for correction and enhancement.

        This is much cheaper than full generation because:
        - Smaller input (just test cases, not full rules)
        - Smaller output (corrections only, not full generation)
        - Faster response time
        """
        if not self.client:
            print("  ⚠ OpenAI client not available, skipping LLM correction")
            return test_cases

        # Format test cases for LLM
        tc_json = json.dumps({"test_cases": test_cases}, indent=2)

        # Format AC for context
        ac_text = "\n".join([f"{i+1}. {ac}" for i, ac in enumerate(acceptance_criteria)])

        user_prompt = f"""You are a SENIOR QA ENGINEER. Review, correct, and ENHANCE these test cases for Story {story_id}: {feature_name}

## FEATURE CONTEXT
Acceptance Criteria:
{ac_text}

QA Prep Summary:
{qa_prep[:1500] if qa_prep else "Not provided"}

## CURRENT TEST CASES (rule-based, needs expert enhancement):
{tc_json}

## YOUR TASKS AS EXPERT QA:

### TASK 1: FIX EXISTING TESTS
- Fix forbidden language ("or", "if available", etc.)
- Fix title format issues
- Add missing expected results to verification steps
- Ensure PRE-REQ first, Close/Exit last (both empty expected)

### TASK 2: ADD EDGE CASE TESTS (add 3-5 tests)
Think: What unusual but valid scenarios could break this feature?
- No selection / empty state behavior
- Single vs multiple object selection
- Rapid repeated actions (double-click behavior)
- Action interrupted mid-operation
- Maximum/minimum allowed values
- Special characters or very long inputs

### TASK 3: ADD NEGATIVE TESTS (add 2-4 tests)
Think: What SHOULD fail or be prevented?
- Action on wrong object type (e.g., rotate on locked object)
- Action without required preconditions
- Invalid input values
- Exceeding limits

### TASK 4: ADD BOUNDARY VALUE TESTS (add 2-3 tests)
Think: What happens at exact limits?
- Minimum value (0, 1, or defined min)
- Maximum value (defined max)
- Just outside valid range

### TASK 5: ADD STATE/PERSISTENCE TESTS (add 1-2 tests)
- Undo/Redo behavior for this feature
- State persistence after tool switch
- State after save and reload

### TASK 6: ENSURE ACCESSIBILITY TESTS (3 tests at end)
- Windows 11: keyboard navigation + Accessibility Insights
- iPad: VoiceOver + touch (NO keyboard)
- Android Tablet: Accessibility Scanner + touch

## OBJECTIVE FIELD REQUIREMENT
Each test MUST have an "objective" field starting with "Verify that..." describing what the test validates.

## OUTPUT
Return enhanced JSON with ALL original tests (fixed) PLUS new tests added: {{"test_cases": [...]}}
Expected total: 15-25 comprehensive test cases."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": CORRECTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,  # Slightly higher for creative edge case generation
                max_tokens=16000,  # Increased for comprehensive test coverage
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            result = json.loads(content)

            corrected = result.get("test_cases", test_cases)

            # Post-process to ensure correct structure
            corrected = self._post_process_corrections(corrected, story_id)

            print(f"  ✓ LLM corrected {len(test_cases)} → {len(corrected)} test cases")

            return corrected

        except Exception as e:
            print(f"  ⚠ LLM correction failed: {e}")
            return test_cases

    def _post_process_corrections(self, test_cases: List[Dict], story_id: str) -> List[Dict]:
        """Post-process LLM corrections to ensure structure compliance."""
        for tc in test_cases:
            steps = tc.get('steps', [])

            # Ensure first step is PRE-REQ (using configured template)
            if steps and 'pre-req' not in steps[0].get('action', '').lower():
                steps.insert(0, {
                    'step': 1,
                    'action': self._prereq,
                    'expected': ''
                })
            elif steps:
                # Standardize PRE-REQ format
                steps[0]['action'] = self._prereq
                steps[0]['expected'] = ''

            # Ensure second step is Launch with configured expected
            if len(steps) >= 2:
                action_lower = steps[1].get('action', '').lower()
                if 'launch' in action_lower or 'navigate' in action_lower:
                    if self._launch_expected:
                        steps[1]['expected'] = self._launch_expected

            # Ensure last step is Close with empty expected (using configured template)
            if steps:
                last_step = steps[-1]
                if 'close' not in last_step.get('action', '').lower() and 'exit' not in last_step.get('action', '').lower() and 'log out' not in last_step.get('action', '').lower():
                    steps.append({
                        'step': len(steps) + 1,
                        'action': self._close,
                        'expected': ''
                    })
                else:
                    # Standardize close step format
                    last_step['action'] = self._close
                    last_step['expected'] = ''

            # Clear expected for routine steps (PRE-REQ and Close only mandatory empty)
            for step in steps:
                action_lower = step.get('action', '').lower()
                # Only force empty for PRE-REQ and Close
                if 'pre-req' in action_lower:
                    step['expected'] = ''
                elif 'close' in action_lower or 'exit' in action_lower or 'log out' in action_lower:
                    step['expected'] = ''

            # Renumber steps
            for i, step in enumerate(steps, 1):
                step['step'] = i

            tc['steps'] = steps

        return test_cases


def generate_and_correct(
    story_id: int,
    output_dir: str = "output",
    skip_correction: bool = False
) -> bool:
    """
    Generate test cases using non-LLM generator, then correct with LLM.

    Args:
        story_id: ADO story ID
        output_dir: Output directory
        skip_correction: If True, skip LLM correction step

    Returns:
        True if successful
    """
    print(f"\n{'='*60}")
    print(f"Hybrid Test Generation for Story {story_id}")
    print(f"Mode: {'Non-LLM Only' if skip_correction else 'Non-LLM + LLM Correction'}")
    print(f"{'='*60}\n")

    # Step 1: Fetch story data from ADO
    print("Step 1: Fetching story data from ADO...")
    try:
        # Get project configuration
        project_manager = get_project_manager()
        project_manager.load_from_directory()
        project_config = project_manager.get_or_create_default()

        # Ensure PAT is set
        if not project_config.ado.pat:
            import os
            project_config.ado.pat = os.getenv('ADO_PAT')

        story_repo = ADOStoryRepository(project_config.ado)
        story = story_repo.get_story(story_id)
        if not story:
            print(f"ERROR: Failed to fetch story {story_id}")
            return False
        qa_prep = story_repo.get_qa_prep(story_id) or ''
    except Exception as e:
        print(f"ERROR: Failed to fetch story: {e}")
        return False

    title = story.title
    description = story.description
    acceptance_criteria = story.acceptance_criteria

    print(f"  Title: {title}")
    print(f"  Description: {len(description)} chars")
    print(f"  Acceptance Criteria: {len(acceptance_criteria)} bullets")
    print(f"  QA Prep: {len(qa_prep)} chars")

    if not acceptance_criteria:
        print("ERROR: No acceptance criteria found")
        return False

    # Step 2: Generate test cases with non-LLM generator
    print("\nStep 2: Generating test cases (rule-based)...")
    generator = GenericTestGenerator(project_config)
    test_cases = generator.generate_test_cases(
        story_data={'story_id': story_id, 'title': title},
        criteria=acceptance_criteria,
        qa_prep_content=qa_prep
    )

    print(f"  Generated {len(test_cases)} test cases")

    # Step 3: Correct with LLM (optional)
    if not skip_correction:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "your-api-key-here":
            print("\n  ⚠ OPENAI_API_KEY not configured, skipping LLM correction")
        else:
            print("\nStep 3: Correcting test cases with LLM...")
            corrector = LLMCorrector(
                api_key=api_key,
                model=config.LLM_MODEL,
                app_config=project_config.application
            )
            test_cases = corrector.correct_test_cases(
                test_cases=test_cases,
                story_id=str(story_id),
                feature_name=title,
                acceptance_criteria=acceptance_criteria,
                qa_prep=qa_prep
            )
    else:
        print("\nStep 3: Skipped LLM correction (--skip-correction)")

    # Step 4: Save outputs
    print("\nStep 4: Saving outputs...")
    os.makedirs(output_dir, exist_ok=True)

    # Clean title for filename
    safe_title = "".join(c if c.isalnum() or c in ' _-' else '_' for c in title)
    safe_title = safe_title.replace(' ', '_')[:50]

    # Determine suffix based on mode
    suffix = "HYBRID" if not skip_correction else "RULE_BASED"

    # Save CSV
    csv_filename = f"{story_id}_{safe_title}_{suffix}_TESTS.csv"
    csv_path = os.path.join(output_dir, csv_filename)

    csv_gen = CSVGenerator()
    csv_gen.generate_csv(test_cases=test_cases, output_file=csv_path)
    print(f"  CSV saved: {csv_path}")

    # Save objectives
    obj_gen = ObjectiveGenerator()
    obj_filename = f"{story_id}_{safe_title}_{suffix}_OBJECTIVES.txt"
    obj_path = os.path.join(output_dir, obj_filename)
    obj_gen.generate_objectives_file(test_cases, obj_path)
    print(f"  Objectives saved: {obj_path}")

    # Save debug JSON
    json_filename = f"{story_id}_{safe_title}_{suffix}_DEBUG.json"
    json_path = os.path.join(output_dir, json_filename)

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'story_id': story_id,
            'title': title,
            'acceptance_criteria': acceptance_criteria,
            'test_cases': test_cases,
            'mode': 'hybrid' if not skip_correction else 'rule_based'
        }, f, indent=2)
    print(f"  Debug JSON saved: {json_path}")

    # Summary
    print(f"\n{'='*60}")
    print("GENERATION COMPLETE")
    print(f"{'='*60}")
    print(f"  Story: {story_id} - {title}")
    print(f"  Test cases generated: {len(test_cases)}")
    print(f"  Output directory: {output_dir}")
    print(f"\nFiles created:")
    print(f"  - {csv_filename}")
    print(f"  - {obj_filename}")
    print(f"  - {json_filename}")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Hybrid Test Generator: Non-LLM + LLM Correction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 correct_with_llm.py --story-id 273167
  python3 correct_with_llm.py --story-id 273167 --skip-correction
  python3 correct_with_llm.py --story-id 273167 --output-dir ./my_tests

This approach is more cost-effective than full LLM generation:
  - Rule-based generator provides 70% coverage fast
  - LLM only corrects/enhances (smaller prompt, faster response)
  - Estimated 50% cost reduction vs full LLM generation
        """
    )

    parser.add_argument(
        '--story-id',
        type=int,
        required=True,
        help='ADO Story ID to generate tests for'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        default='output',
        help='Output directory for generated files (default: output)'
    )

    parser.add_argument(
        '--skip-correction',
        action='store_true',
        help='Skip LLM correction step (use non-LLM only)'
    )

    args = parser.parse_args()

    success = generate_and_correct(
        story_id=args.story_id,
        output_dir=args.output_dir,
        skip_correction=args.skip_correction
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
