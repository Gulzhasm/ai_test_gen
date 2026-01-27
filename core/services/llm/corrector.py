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
- Add accessibility tests if missing (based on project platforms)
- Validate ID sequence

The framework is PROJECT-AGNOSTIC - it dynamically builds prompts based on
project configuration, making it adaptable to any application.

Usage:
    python3 correct_with_llm.py --story-id 273167
    python3 correct_with_llm.py --story-id 273167 --skip-correction  # Generate without LLM
    python3 correct_with_llm.py --story-id 273167 --output-dir ./my_tests
    python3 correct_with_llm.py --story-id 273167 --upload-existing  # Upload existing tests to ADO
    python3 correct_with_llm.py --story-id 273167 --use-existing     # Use existing tests if found
"""
import argparse
import csv
import glob
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
from core.config import environment as config

# LLM correction imports
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Import the dynamic prompt builder for project-agnostic prompts
try:
    from .prompt_builder import PromptBuilder, build_prompts_for_project
    PROMPT_BUILDER_AVAILABLE = True
except ImportError:
    PROMPT_BUILDER_AVAILABLE = False


def find_existing_test_files(story_id: int, output_dir: str = "output") -> Dict[str, str]:
    """
    Find existing test case files for a story.

    Args:
        story_id: The story ID to search for
        output_dir: Directory to search in

    Returns:
        Dict with keys 'json', 'csv', 'objectives' pointing to file paths if found
    """
    found_files = {}

    if not os.path.exists(output_dir):
        return found_files

    # Search patterns for different file types
    patterns = {
        'json': f"{output_dir}/{story_id}_*DEBUG.json",
        'csv': f"{output_dir}/{story_id}_*TESTS.csv",
        'objectives': f"{output_dir}/{story_id}_*OBJECTIVES.txt"
    }

    for file_type, pattern in patterns.items():
        matches = glob.glob(pattern)
        if matches:
            # Get the most recent file if multiple exist
            found_files[file_type] = max(matches, key=os.path.getmtime)

    return found_files


def load_existing_test_cases(json_file: str) -> Optional[List[Dict]]:
    """
    Load test cases from an existing JSON file.

    Args:
        json_file: Path to the JSON file

    Returns:
        List of test case dictionaries or None if loading fails
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('test_cases', [])
    except Exception as e:
        print(f"  ⚠ Failed to load existing tests: {e}")
        return None


def upload_tests_to_ado(
    test_cases: List[Dict],
    story_id: int,
    project_config
) -> bool:
    """
    Upload test cases to Azure DevOps.

    Args:
        test_cases: List of test case dictionaries
        story_id: The story ID
        project_config: Project configuration

    Returns:
        True if successful
    """
    from infrastructure.ado import ADOTestCaseRepository, ADOTestSuiteRepository, ADOStoryRepository

    print(f"\n{'='*60}")
    print(f"Uploading {len(test_cases)} test cases to ADO")
    print(f"{'='*60}\n")

    try:
        # Initialize repositories
        test_case_repo = ADOTestCaseRepository(project_config.ado)
        suite_repo = ADOTestSuiteRepository(project_config.ado)
        story_repo = ADOStoryRepository(project_config.ado)

        # Get story title for suite name
        story = story_repo.get_story(story_id)
        if not story:
            print(f"  ⚠ Could not fetch story {story_id}")
            return False

        # Find or create test suite
        suite = suite_repo.find_suite_by_story_id(story_id)
        if not suite:
            print(f"  Creating test suite for story {story_id}...")
            # Need to find a test plan first - use the first available
            # This is a simplified approach; production code should handle this better
            print(f"  ⚠ Test suite not found. Please create a test suite manually.")
            return False

        print(f"  Found test suite: {suite['name']} (ID: {suite['id']})")

        # Upload each test case
        created_count = 0
        for tc in test_cases:
            title = tc.get('title', '')
            steps = tc.get('steps', [])
            objective = tc.get('objective', '')

            # Create test case in ADO
            tc_id = test_case_repo.create_test_case(
                title=title,
                steps=steps,
                objective=objective,
                area_path=project_config.ado.area_path,
                assigned_to=project_config.ado.assigned_to,
                state=project_config.ado.default_state
            )

            if tc_id:
                # Add to test suite
                suite_repo.add_test_case_to_suite(
                    plan_id=suite['plan_id'],
                    suite_id=suite['id'],
                    test_case_id=tc_id
                )
                created_count += 1
                print(f"  ✓ Created: {title[:60]}... (ID: {tc_id})")
            else:
                print(f"  ✗ Failed: {title[:60]}...")

        print(f"\n{'='*60}")
        print(f"Upload Complete: {created_count}/{len(test_cases)} test cases created")
        print(f"{'='*60}")

        return created_count > 0

    except Exception as e:
        print(f"  ⚠ Upload failed: {e}")
        return False


class LLMCorrector:
    """
    Corrects and enhances test cases using LLM.

    This class is PROJECT-AGNOSTIC - it uses dynamic prompts built from
    project configuration, making it adaptable to any application.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        app_config=None,
        project_config=None  # Full project config for dynamic prompts
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self._client: Optional[OpenAI] = None
        self._app_config = app_config
        self._project_config = project_config

        # Default step templates (can be overridden by app_config or project_config)
        self._app_name = "Application"
        self._prereq = "Pre-req: The application is installed"
        self._launch_expected = ""
        self._close = "Close the application"

        # Use project_config if available, otherwise fall back to app_config
        if project_config:
            self._app_config = project_config.application
            app_config = project_config.application

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

        Uses dynamic prompts built from project configuration, making this
        method adaptable to any application without hardcoded references.

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

        # Build dynamic prompts based on project configuration
        if PROMPT_BUILDER_AVAILABLE and self._project_config:
            # Use the dynamic prompt builder for project-agnostic prompts
            builder = PromptBuilder.from_project_config(
                config=self._project_config,
                story_id=story_id,
                feature_name=feature_name,
                acceptance_criteria=acceptance_criteria,
                qa_prep=qa_prep
            )
            system_prompt = builder.build_system_prompt()
            user_prompt = builder.build_user_prompt(tc_json)
            print(f"  Using dynamic prompts for {self._app_name}")

            # DEBUG: Print prompts to output file
            debug_prompt_path = os.path.join("output", f"{story_id}_PROMPTS_DEBUG.txt")
            os.makedirs("output", exist_ok=True)
            with open(debug_prompt_path, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("SYSTEM PROMPT\n")
                f.write("=" * 80 + "\n\n")
                f.write(system_prompt)
                f.write("\n\n")
                f.write("=" * 80 + "\n")
                f.write("USER PROMPT\n")
                f.write("=" * 80 + "\n\n")
                f.write(user_prompt)
            print(f"  DEBUG: Prompts saved to {debug_prompt_path}")
        else:
            # Fallback to basic prompts if prompt builder not available
            system_prompt, user_prompt = self._build_fallback_prompts(
                story_id, feature_name, acceptance_criteria, qa_prep, tc_json
            )
            print(f"  Using fallback prompts for {self._app_name}")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
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

            # Ensure all required accessibility tests are present
            corrected = self._ensure_accessibility_tests(corrected, story_id, feature_name)

            print(f"  ✓ LLM corrected {len(test_cases)} → {len(corrected)} test cases")

            return corrected

        except Exception as e:
            print(f"  ⚠ LLM correction failed: {e}")
            return test_cases

    def _build_fallback_prompts(
        self,
        story_id: str,
        feature_name: str,
        acceptance_criteria: List[str],
        qa_prep: str,
        tc_json: str
    ) -> tuple:
        """
        Build fallback prompts when project config is not available.

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        ac_text = "\n".join([f"{i+1}. {ac}" for i, ac in enumerate(acceptance_criteria)])

        system_prompt = f'''You are a SENIOR QA TEST ENGINEER with 15+ years of experience writing production-quality test cases for {self._app_name}.

## YOUR EXPERT QA MINDSET
Think like a human QA expert reviewing test cases:
- "What edge cases would I naturally think of?"
- "What could go wrong that a developer might miss?"
- "What boundary conditions need explicit testing?"
- "How would a real user potentially break this feature?"

## YOUR RESPONSIBILITIES
1. CORRECT existing test cases (formatting, language, structure)
2. ADD comprehensive edge case tests
3. ADD negative tests for invalid operations
4. ADD boundary value tests at exact limits
5. ADD error handling and recovery tests
6. ADD state transition and persistence tests
7. WRITE tests as if a human expert QA engineer wrote them

## TITLE RULES
Format: "<StoryID>-<ID>: <Feature> / <Area> / <Scenario>"

## STEP STRUCTURE
1. First step: Pre-requisite step (empty expected)
   Action: "{self._prereq}"
2. Second step: Launch/Navigate step
3. Last step: Close/Exit step (empty expected)
   Action: "{self._close}"

## FORBIDDEN LANGUAGE
Remove: "or", "if available", "if supported", "if applicable", "e.g., X or Y"

## ID SEQUENCE
- AC1 for first test
- Then increment by 5: 005, 010, 015, 020...

## OBJECTIVE FIELD
Each test MUST have an "objective" field starting with "Verify that..."

Output corrected and enhanced JSON only: {{"test_cases": [...]}}'''

        user_prompt = f'''Review and ENHANCE these test cases for Story {story_id}: {feature_name}

## APPLICATION: {self._app_name}

## FEATURE CONTEXT
Acceptance Criteria:
{ac_text}

QA Prep Summary:
{qa_prep[:2000] if qa_prep else "Not provided - generate based on AC"}

## CURRENT TEST CASES:
{tc_json}

## YOUR TASKS:
1. FIX existing tests (forbidden language, title format, expected results)
2. ADD 3-5 edge case tests
3. ADD 2-4 negative tests
4. ADD 2-3 boundary value tests
5. ADD 1-2 state/persistence tests
6. ADD accessibility tests for supported platforms

## OUTPUT
Return enhanced JSON: {{"test_cases": [...]}}
Expected total: 15-25 comprehensive test cases.'''

        return system_prompt, user_prompt

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

    def _ensure_accessibility_tests(
        self,
        test_cases: List[Dict],
        story_id: str,
        feature_name: str
    ) -> List[Dict]:
        """
        Ensure all required platform accessibility tests are present.
        If missing, add them programmatically.
        """
        if not self._project_config:
            return test_cases

        # Get required platforms from config (attribute is 'supported_platforms')
        platforms = getattr(self._project_config.application, 'supported_platforms', [])
        if not platforms:
            return test_cases

        # Check which platforms have accessibility tests
        existing_platforms = set()
        for tc in test_cases:
            title_lower = tc.get('title', '').lower()
            # Check if this is an accessibility test
            if 'accessibility' in title_lower or 'voiceover' in title_lower or 'keyboard navigation' in title_lower:
                for platform in platforms:
                    if platform.lower() in title_lower:
                        existing_platforms.add(platform)

        # Find missing platforms
        missing_platforms = [p for p in platforms if p not in existing_platforms]

        if not missing_platforms:
            return test_cases

        print(f"  ⚠ Missing accessibility tests for: {', '.join(missing_platforms)}")
        print(f"  → Adding {len(missing_platforms)} missing accessibility test(s)...")

        # Get the highest test ID to continue numbering
        max_id = 0
        for tc in test_cases:
            tc_id = tc.get('id', '')
            if '-' in tc_id:
                try:
                    num_part = tc_id.split('-')[-1]
                    if num_part.isdigit():
                        max_id = max(max_id, int(num_part))
                except:
                    pass

        # Generate missing accessibility tests
        for platform in missing_platforms:
            max_id += 5  # Increment by 5 following the pattern
            new_test = self._generate_accessibility_test(
                story_id, feature_name, platform, max_id
            )
            test_cases.append(new_test)
            print(f"    + Added: {new_test['title'][:70]}...")

        return test_cases

    def _generate_accessibility_test(
        self,
        story_id: str,
        feature_name: str,
        platform: str,
        test_num: int
    ) -> Dict:
        """Generate an accessibility test for a specific platform."""
        platform_lower = platform.lower()

        # Determine test specifics based on platform
        if 'windows' in platform_lower:
            prereq_tool = "Pre-req: Accessibility Insights for Windows is installed"
            nav_action = "Navigate to View Menu using keyboard."
            verify_action = f"Verify the {feature_name} controls are keyboard accessible."
            verify_expected = f"Keyboard focus moves to {feature_name} controls with visible focus indicator."
            tool_action = f"Verify {feature_name} controls expose meaningful labels in Accessibility Insights."
            tool_expected = "Controls expose correct accessible name and role."
            test_type = "Keyboard navigation and labels"
        elif 'ipad' in platform_lower or 'ios' in platform_lower:
            prereq_tool = "Pre-req: VoiceOver is enabled"
            nav_action = "Navigate to View Menu using VoiceOver swipe gestures."
            verify_action = f"Verify the {feature_name} controls are announced with meaningful labels."
            verify_expected = f"VoiceOver announces {feature_name} controls with meaningful labels and roles."
            tool_action = "Verify reading order is logical."
            tool_expected = "VoiceOver announces controls in logical order."
            test_type = "VoiceOver navigation"
        elif 'android' in platform_lower:
            prereq_tool = "Pre-req: Accessibility Scanner for Android is installed"
            nav_action = "Navigate to View Menu using touch gestures."
            verify_action = f"Verify the {feature_name} controls are accessible via touch."
            verify_expected = f"{feature_name} controls respond correctly to touch gestures."
            tool_action = f"Run Accessibility Scanner on the {feature_name} screen."
            tool_expected = "No critical accessibility issues are reported by Accessibility Scanner."
            test_type = "TalkBack and Accessibility Scanner"
        else:
            prereq_tool = f"Pre-req: Accessibility tools for {platform} are available"
            nav_action = "Navigate to View Menu."
            verify_action = f"Verify the {feature_name} controls are accessible."
            verify_expected = f"{feature_name} controls are accessible."
            tool_action = "Verify accessibility compliance."
            tool_expected = "Controls meet accessibility standards."
            test_type = "Accessibility"

        test_id = f"{story_id}-{test_num:03d}"

        return {
            'id': test_id,
            'title': f"{test_id}: {feature_name} / Accessibility / {test_type} ({platform})",
            'objective': f"Verify that <b>{feature_name}</b> controls meet <b>WCAG 2.1 AA</b> standards on <b>{platform}</b>",
            'steps': [
                {'step': 1, 'action': self._prereq, 'expected': ''},
                {'step': 2, 'action': prereq_tool, 'expected': ''},
                {'step': 3, 'action': f"Launch the {self._app_name} application.", 'expected': self._launch_expected},
                {'step': 4, 'action': nav_action, 'expected': ''},
                {'step': 5, 'action': verify_action, 'expected': verify_expected},
                {'step': 6, 'action': tool_action, 'expected': tool_expected},
                {'step': 7, 'action': self._close, 'expected': ''}
            ]
        }


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
                project_config=project_config  # Pass full project config for dynamic prompts
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

    # Save CSV - pass config with area_path and assigned_to
    from infrastructure.export.csv_generator import CSVConfig
    csv_config = CSVConfig(
        area_path=project_config.ado.area_path,
        assigned_to=project_config.ado.assigned_to,
        default_state=project_config.ado.default_state
    )
    csv_filename = f"{story_id}_{safe_title}_{suffix}_TESTS.csv"
    csv_path = os.path.join(output_dir, csv_filename)

    csv_gen = CSVGenerator(config=csv_config)
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
  python3 correct_with_llm.py --story-id 273167 --upload-existing
  python3 correct_with_llm.py --story-id 273167 --use-existing

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

    parser.add_argument(
        '--upload-existing',
        action='store_true',
        help='Upload existing test cases to ADO (skip generation)'
    )

    parser.add_argument(
        '--use-existing',
        action='store_true',
        help='Use existing test cases if found, otherwise generate new ones'
    )

    parser.add_argument(
        '--upload',
        action='store_true',
        help='Upload generated test cases to ADO after generation'
    )

    args = parser.parse_args()

    # Handle upload-existing mode
    if args.upload_existing:
        existing_files = find_existing_test_files(args.story_id, args.output_dir)
        if not existing_files.get('json'):
            print(f"ERROR: No existing test files found for story {args.story_id}")
            print(f"Searched in: {args.output_dir}")
            sys.exit(1)

        print(f"Found existing test file: {existing_files['json']}")
        test_cases = load_existing_test_cases(existing_files['json'])

        if not test_cases:
            print("ERROR: Failed to load test cases from file")
            sys.exit(1)

        print(f"Loaded {len(test_cases)} test cases")

        # Get project config
        project_manager = get_project_manager()
        project_manager.load_from_directory()
        project_config = project_manager.get_or_create_default()

        if not project_config.ado.pat:
            project_config.ado.pat = os.getenv('ADO_PAT')

        success = upload_tests_to_ado(test_cases, args.story_id, project_config)
        sys.exit(0 if success else 1)

    # Handle use-existing mode
    if args.use_existing:
        existing_files = find_existing_test_files(args.story_id, args.output_dir)
        if existing_files.get('json'):
            print(f"Found existing test file: {existing_files['json']}")
            test_cases = load_existing_test_cases(existing_files['json'])

            if test_cases:
                print(f"Using {len(test_cases)} existing test cases (skipping generation)")

                if args.upload:
                    project_manager = get_project_manager()
                    project_manager.load_from_directory()
                    project_config = project_manager.get_or_create_default()

                    if not project_config.ado.pat:
                        project_config.ado.pat = os.getenv('ADO_PAT')

                    success = upload_tests_to_ado(test_cases, args.story_id, project_config)
                    sys.exit(0 if success else 1)
                else:
                    print("\nExisting test files:")
                    for file_type, path in existing_files.items():
                        print(f"  - {file_type}: {path}")
                    sys.exit(0)
        else:
            print(f"No existing tests found for story {args.story_id}, generating new tests...")

    # Standard generation flow
    success = generate_and_correct(
        story_id=args.story_id,
        output_dir=args.output_dir,
        skip_correction=args.skip_correction
    )

    # Upload if requested
    if success and args.upload:
        existing_files = find_existing_test_files(args.story_id, args.output_dir)
        if existing_files.get('json'):
            test_cases = load_existing_test_cases(existing_files['json'])
            if test_cases:
                project_manager = get_project_manager()
                project_manager.load_from_directory()
                project_config = project_manager.get_or_create_default()

                if not project_config.ado.pat:
                    project_config.ado.pat = os.getenv('ADO_PAT')

                success = upload_tests_to_ado(test_cases, args.story_id, project_config)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
