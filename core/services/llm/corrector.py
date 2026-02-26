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

from infrastructure.repository_factory import get_story_repository, get_test_repositories
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

# Stop words excluded from AC keyword matching (common words with no signal)
AC_STOP_WORDS = {
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'shall', 'can', 'need', 'must',
    'that', 'this', 'these', 'those', 'it', 'its',
    'and', 'but', 'or', 'nor', 'not', 'no', 'so', 'if', 'then',
    'of', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'from',
    'up', 'out', 'off', 'over', 'under', 'again', 'further',
    'when', 'where', 'how', 'what', 'which', 'who', 'whom',
    'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other',
    'some', 'such', 'only', 'own', 'same', 'than', 'too', 'very',
    'user', 'able', 'also', 'new', 'any', 'into', 'about', 'after',
    'before', 'between', 'during', 'through', 'above', 'below',
}

# Patterns that indicate a "meta-AC" — vague catch-all acceptance criteria
# that should NOT trigger gap-fill test generation. These ACs are
# compliance-level statements, not testable behaviors.
META_AC_PATTERNS = [
    r'comply with.*specifications',
    r'comply with.*details described',
    r'as per the requirements',
    r'as described in the user story',
    r'described in the user story',
    r'according to.*specifications',
    r'all behavior.*must.*comply',
    r'all functionality.*must.*comply',
    r'meets? the requirements',
    r'adhere to.*specifications',
    r'consistent with.*design',
    r'per the design spec',
    r'as specified in the',
    r'follow.*specifications',
]


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
        print(f"  Warning: Failed to load existing tests: {e}")
        return None


def upload_tests_to_platform(
    test_cases: List[Dict],
    story_id: int,
    project_config
) -> bool:
    """
    Upload test cases to target platform (ADO or TestRail).

    Args:
        test_cases: List of test case dictionaries
        story_id: The story ID
        project_config: Project configuration

    Returns:
        True if successful
    """
    target_platform = project_config.target_platform.upper()
    print(f"\nUploading {len(test_cases)} test cases to {target_platform}\n")

    try:
        # Use repository factory for platform-agnostic operations
        story_repo = get_story_repository(project_config)
        suite_repo, case_repo = get_test_repositories(project_config)

        # Get story title for suite name
        story = story_repo.get_story(story_id)
        if not story:
            print(f"  Warning: Could not fetch story {story_id}")
            return False

        # Find or create test suite
        suite = suite_repo.find_suite_by_story_id(story_id)
        if not suite:
            print(f"  Creating test suite for story {story_id}...")
            print(f"  Warning: Test suite not found. Please create a test suite manually.")
            return False

        print(f"  Found test suite: {suite['name']} (ID: {suite['id']})")

        # Upload each test case
        created_count = 0
        plan_id = suite.get('plan_id', 0)
        suite_id = suite['id']

        for tc in test_cases:
            title = tc.get('title', '')
            steps = tc.get('steps', [])
            objective = tc.get('objective', '')

            # Create test case using repository (platform-agnostic)
            tc_id = case_repo.create_test_case(
                title=title,
                steps=steps,
                objective=objective,
                section_id=suite_id
            )

            if tc_id:
                # Add to test suite
                suite_repo.add_test_case_to_suite(plan_id, suite_id, tc_id)
                created_count += 1
                print(f"  Created: {title[:60]}... (ID: {tc_id})")
            else:
                print(f"  Failed: {title[:60]}...")

        print(f"\nUpload complete: {created_count}/{len(test_cases)} test cases created")

        return created_count > 0

    except Exception as e:
        print(f"  Upload failed: {e}")
        return False


# Backward compatibility alias
upload_tests_to_ado = upload_tests_to_platform


class LLMCorrector:
    """
    Corrects and enhances test cases using LLM.

    This class is PROJECT-AGNOSTIC - it uses dynamic prompts built from
    project configuration, making it adaptable to any application.

    Supports multiple LLM providers via the factory pattern:
    OpenAI, Gemini, Anthropic, Ollama.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        app_config=None,
        project_config=None,  # Full project config for dynamic prompts
        provider_type: Optional[str] = None  # Override provider type
    ):
        # Determine provider from project_config, explicit param, or env
        self._provider_type = (
            provider_type
            or (getattr(project_config, 'llm_provider', None) if project_config else None)
            or os.getenv("LLM_PROVIDER", "openai")
        ).lower()

        self.model = model
        self._provider = None
        self._api_key = api_key
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
    def provider(self):
        """Lazy initialization of LLM provider via factory."""
        if self._provider is None:
            from .factory import create_llm_provider
            self._provider = create_llm_provider(
                provider_type=self._provider_type,
                model=self.model,
                timeout=90,
                max_retries=1,
                api_key=self._api_key
            )
            if self._provider:
                print(f"  LLM provider: {self._provider_type} ({self.model})")
        return self._provider

    @property
    def client(self):
        """Backward compatibility - returns provider for OpenAI or the provider itself."""
        if self._provider_type == "openai":
            provider = self.provider
            return provider.client if provider else None
        return self.provider

    def correct_test_cases(
        self,
        test_cases: List[Dict],
        story_id: str,
        feature_name: str,
        acceptance_criteria: List[str],
        qa_prep: str,
        reference_steps: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """
        Send test cases to LLM for correction and enhancement.

        Uses dynamic prompts built from project configuration, making this
        method adaptable to any application without hardcoded references.

        Supports multiple LLM providers (OpenAI, Gemini, Anthropic, Ollama)
        via the factory pattern.
        """
        if not self.provider:
            print(f"  Warning: LLM provider ({self._provider_type}) not available, skipping correction")
            # Still apply post-processing even without LLM
            test_cases = self._post_process_corrections(test_cases, story_id)
            test_cases = self._ensure_accessibility_tests(test_cases, story_id, feature_name)
            return test_cases

        # Store for use in _get_minimum_test_count and _ensure_accessibility_tests
        self._current_feature_name = feature_name
        self._current_acceptance_criteria = acceptance_criteria

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

            if reference_steps:
                ref_section = "\n\n## REFERENCE STEPS (Use consistent wording)\n"
                ref_section += "These steps exist in other tests. Use similar phrasing:\n"
                for step in reference_steps[:10]:  # Limit to 10
                    ref_section += f"- {step}\n"
                user_prompt = user_prompt + ref_section

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
            result = self._call_llm(system_prompt, user_prompt)

            corrected = result.get("test_cases", test_cases)

            # Post-process to ensure correct structure
            corrected = self._post_process_corrections(corrected, story_id)

            # Ensure all required accessibility tests are present
            corrected = self._ensure_accessibility_tests(corrected, story_id, feature_name)

            # Remove duplicate/overlapping test cases
            corrected = self._remove_duplicate_tests(corrected, story_id)

            # Ensure every AC has at least one test covering it
            corrected = self._ensure_ac_coverage(
                corrected, story_id, feature_name, acceptance_criteria, qa_prep
            )

            # Second dedup pass — gap-filling and retry may introduce duplicates
            corrected = self._remove_duplicate_tests(corrected, story_id)

            # Enforce minimum test count — retry if under minimum
            min_tests = self._get_minimum_test_count(acceptance_criteria)
            if len(corrected) < min_tests:
                print(f"  Warning: {len(corrected)} tests < minimum {min_tests}, retrying for more coverage...")
                corrected = self._retry_for_minimum_count(
                    corrected, story_id, feature_name,
                    acceptance_criteria, qa_prep, min_tests
                )
                corrected = self._ensure_accessibility_tests(corrected, story_id, feature_name)
                corrected = self._remove_duplicate_tests(corrected, story_id)

            print(f"  OK: LLM corrected {len(test_cases)} → {len(corrected)} test cases")

            return corrected

        except Exception as e:
            print(f"  Warning: LLM correction failed: {e}")
            # Still apply post-processing and accessibility checks even without LLM
            test_cases = self._post_process_corrections(test_cases, story_id)
            test_cases = self._ensure_accessibility_tests(test_cases, story_id, feature_name)
            # Still check AC coverage (will attempt LLM gap-fill if provider available)
            test_cases = self._ensure_ac_coverage(
                test_cases, story_id, feature_name, acceptance_criteria, qa_prep
            )
            print(f"  Applied post-processing to {len(test_cases)} uncorrected test cases")
            return test_cases

    def _call_llm(self, system_prompt: str, user_prompt: str) -> Dict:
        """Call the LLM provider and return parsed JSON result.

        Works with any provider (OpenAI, Gemini, Anthropic, Ollama).
        """
        provider = self.provider

        # For providers with generate_json (Gemini, etc.)
        if self._provider_type in ("gemini", "google"):
            combined_prompt = f"{user_prompt}"
            result = provider.generate_json(
                prompt=combined_prompt,
                system_prompt=system_prompt,
                temperature=0.2,
                max_tokens=16000
            )
            if result is None:
                raise RuntimeError("Gemini returned no result")
            return result

        # For OpenAI - use chat completions with JSON mode
        if self._provider_type == "openai" and hasattr(provider, 'client') and provider.client:
            response = provider.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=16000,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            return json.loads(content)

        # For Anthropic / Ollama - use generate_json
        if hasattr(provider, 'generate_json'):
            result = provider.generate_json(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.2,
                max_tokens=16000
            )
            if result is None:
                raise RuntimeError(f"{self._provider_type} returned no result")
            return result

        raise RuntimeError(f"Provider {self._provider_type} does not support JSON generation")

    def _get_minimum_test_count(self, acceptance_criteria: List[str]) -> int:
        """Calculate the minimum required test count based on story complexity."""
        try:
            from .prompt_builder import (
                calculate_test_requirements,
                detect_feature_types,
                extract_boundary_entities,
                extract_comprehensive_workflows,
                detect_format_variations,
                clean_acceptance_criteria,
                split_scope
            )

            # Clean ACs first
            cleaned_acs = clean_acceptance_criteria(acceptance_criteria)
            in_scope, _ = split_scope(cleaned_acs)

            # Get config values
            platform_count = len(getattr(self._project_config.application, 'supported_platforms', [])) if self._project_config else 3

            # Detect feature types
            feature_name = getattr(self, '_current_feature_name', 'Feature')
            feature_types = detect_feature_types(feature_name, in_scope)

            # Extract complexity indicators
            boundary_entities = extract_boundary_entities(in_scope)
            comprehensive_workflows = extract_comprehensive_workflows(boundary_entities, in_scope)
            format_variations = detect_format_variations(in_scope)

            # Calculate using the same logic as prompt_builder
            reqs = calculate_test_requirements(
                ac_count=len(in_scope),
                feature_types=feature_types,
                boundary_entities=boundary_entities,
                comprehensive_workflows=comprehensive_workflows,
                format_variations=format_variations,
                platform_count=platform_count,
                qa_prep=""
            )

            return reqs.min_total

        except ImportError:
            # Fallback if prompt_builder not available
            ac_count = len(acceptance_criteria)
            platform_count = len(getattr(self._project_config.application, 'supported_platforms', [])) if self._project_config else 3
            return max(ac_count, 3) + 5 + platform_count  # Simple fallback

    def _retry_for_minimum_count(
        self,
        current_tests: List[Dict],
        story_id: str,
        feature_name: str,
        acceptance_criteria: List[str],
        qa_prep: str,
        min_tests: int
    ) -> List[Dict]:
        """Retry LLM call with stronger emphasis on meeting minimum count."""
        if not self.provider:
            return current_tests

        shortage = min_tests - len(current_tests)

        retry_prompt = f'''CRITICAL: The previous response returned only {len(current_tests)} test cases.
The MINIMUM required is {min_tests} tests. You are SHORT by {shortage} tests.

Current test cases (DO NOT reduce these):
{json.dumps({"test_cases": current_tests}, indent=2)}

## MANDATORY ADDITIONS (add {shortage}+ more tests):
Think like a senior QA engineer. For each AC, consider:
- **Variations**: Can the same AC be tested in a different state or context?
  (e.g., "zoom in" → test from default zoom, test from already zoomed state)
- **Boundary conditions**: What are the natural limits of this feature?
  (e.g., maximum zoom, minimum zoom, rapid repeated actions)
- **Combined workflows**: How do multiple ACs interact together?
  (e.g., zoom in multiple times → reset → verify back to 100%)
- **Different input methods**: Does the feature work via multiple controls?
  (e.g., keyboard shortcut + menu command + mouse action)

Every test must still relate to the feature described in the ACs.
Do NOT invent features or UI elements not mentioned in the ACs.

Story: {story_id} - {feature_name}
ACs: {json.dumps(acceptance_criteria)}

Return the COMPLETE list of {min_tests}+ test cases in JSON format.
DO NOT remove any existing tests. Only ADD new tests.
Continue the ID sequence from the last non-accessibility test ID.
'''

        system_prompt = "You are a QA test generator. Return JSON only with test_cases array."

        try:
            result = self._call_llm(system_prompt, retry_prompt)
            new_tests = result.get("test_cases", current_tests)

            # Ensure we didn't lose tests
            if len(new_tests) >= len(current_tests):
                new_tests = self._post_process_corrections(new_tests, story_id)
                print(f"  → Retry successful: {len(current_tests)} → {len(new_tests)} tests")
                return new_tests
            else:
                print(f"  → Retry returned fewer tests, keeping original")
                return current_tests

        except Exception as e:
            print(f"  → Retry failed: {e}")
            return current_tests

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
- EXACTLY 3 segments after the ID prefix. NEVER use 4+ segments.
- Scenario (last segment) must describe behavior, NOT start with "Verify"
- Scenario MUST be in Title Case (capitalize first letter of every word)
- BAD: "Show Design Panel / Verify Design Panel visibility" (4 segments, starts with Verify)
- BAD: "Show and hide Design Panel" (not Title Case)
- GOOD: "Show And Hide Design Panel" (3 segments, Title Case, describes action)

## STEP STRUCTURE
1. First step: Pre-requisite step (empty expected)
   Action: "{self._prereq}"
2. Second step: Launch/Navigate step
3. Last step: Close/Exit step (empty expected)
   Action: "{self._close}"

## FORBIDDEN LANGUAGE
Remove: "or", "if available", "if supported", "if applicable", "e.g., X or Y"
NEVER start a step with "If" — steps must be deterministic, not conditional.
NEVER use "or" in expected results — each expected must describe ONE specific outcome.
ONE action per step — never combine two toggle operations into a single step.
BAD: "If 'Show X' is unchecked, select it to check it." → GOOD: First uncheck, then check in separate steps.
BAD expected: "shown or hidden based on its previous state" → GOOD: "The Design Panel is now visible."

## ID SEQUENCE & AC1 RULE
- AC1 must be an OVERALL ACCEPTANCE TEST — NOT just "verify command appears in menu"
  AC1 must: navigate to entry point → EXECUTE the feature → VERIFY the core behavior works
  BAD AC1: "Verify command appears in menu" (just availability)
  GOOD AC1: Open menu → Execute feature → Verify primary behavior → Close
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

    def _renumber_test_ids(self, test_cases: List[Dict], story_id: str) -> List[Dict]:
        """
        Renumber test case IDs to ensure proper sequence.

        Sequence: AC1, 005, 010, 015, 020, 025, ...
        Uses test_id_increment from project config (default: 5)
        """
        if not test_cases:
            return test_cases

        # Get increment from config or default to 5
        increment = 5
        if self._project_config:
            increment = getattr(self._project_config.rules, 'test_id_increment', 5)

        first_test_id = "AC1"
        if self._project_config:
            first_test_id = getattr(self._project_config.rules, 'first_test_id', 'AC1')

        current_num = increment  # Start at 005 for second test

        for idx, tc in enumerate(test_cases):
            if idx == 0:
                # First test is always AC1
                new_id = f"{story_id}-{first_test_id}"
            else:
                # Subsequent tests use numeric IDs
                new_id = f"{story_id}-{current_num:03d}"
                current_num += increment

            # Update ID in test case
            old_id = tc.get('id', '')
            tc['id'] = new_id

            # Update ID in title if present
            old_title = tc.get('title', '')
            if old_id and old_id in old_title:
                tc['title'] = old_title.replace(old_id, new_id, 1)
            elif old_title and ':' in old_title:
                # Replace the ID portion before the first colon
                parts = old_title.split(':', 1)
                tc['title'] = f"{new_id}:{parts[1]}" if len(parts) > 1 else f"{new_id}: {old_title}"

        return test_cases

    @staticmethod
    def _title_case_scenario(title: str) -> str:
        """Convert the scenario (last segment after '/') in a title to Title Case."""
        # Title format: "{story_id}-{id}: {Feature} / {Area} / {Scenario}"
        if '/' not in title:
            return title

        # Split on '/' keeping all parts
        parts = title.split('/')
        # Title Case the last segment (scenario)
        scenario = parts[-1].strip()
        scenario_title_cased = scenario.title()
        parts[-1] = f" {scenario_title_cased}"

        return '/'.join(parts)

    @staticmethod
    def _clean_forbidden_language(text: str) -> str:
        """Remove forbidden language patterns from step text.

        Cleans: 'e.g.', 'i.e.', 'if available', 'if supported', 'if applicable'
        """
        import re
        if not text:
            return text
        # Remove "e.g., ..." patterns (e.g., '1" = 10 ft') -> ('1" = 10 ft')
        text = re.sub(r'\be\.?g\.?,?\s*', '', text)
        # Remove "i.e., ..." patterns
        text = re.sub(r'\bi\.?e\.?,?\s*', '', text)
        # Remove "if available/supported/applicable"
        text = re.sub(r'\bif\s+(?:available|supported|applicable)\b,?\s*', '', text, flags=re.IGNORECASE)
        # Clean up double spaces left behind
        text = re.sub(r'  +', ' ', text).strip()
        return text

    def _post_process_corrections(self, test_cases: List[Dict], story_id: str) -> List[Dict]:
        """Post-process LLM corrections to ensure structure compliance."""
        # First, renumber test IDs to ensure proper sequence (AC1, 005, 010, 015, ...)
        test_cases = self._renumber_test_ids(test_cases, story_id)

        for tc in test_cases:
            # Enforce Title Case on the scenario part of titles
            if 'title' in tc:
                tc['title'] = self._title_case_scenario(tc['title'])
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

            # Clean forbidden language from all steps
            for step in steps:
                step['action'] = self._clean_forbidden_language(step.get('action', ''))
                step['expected'] = self._clean_forbidden_language(step.get('expected', ''))

            # Renumber steps
            for i, step in enumerate(steps, 1):
                step['step'] = i

            tc['steps'] = steps

        return test_cases

    def _remove_duplicate_tests(self, test_cases: List[Dict], story_id: str) -> List[Dict]:
        """Remove test cases whose objectives overlap heavily with an earlier test.

        Uses word-overlap on the objective field. AC1 and accessibility tests are
        always kept. When a duplicate is detected, the earlier (lower-index) test
        wins and the later one is dropped.
        """
        if len(test_cases) <= 1:
            return test_cases

        def _objective_words(tc: Dict) -> set:
            obj = tc.get('objective', tc.get('title', '')).lower()
            # Strip common filler words for better comparison
            stop = {'a', 'an', 'the', 'is', 'are', 'of', 'to', 'and', 'or', 'in',
                    'on', 'that', 'for', 'by', 'it', 'its', 'with', 'can', 'be', 'not'}
            return set(obj.split()) - stop

        keep: list[Dict] = []
        removed = 0
        for tc in test_cases:
            tc_id = tc.get('id', '')
            # Always keep AC1 and accessibility tests
            if tc_id.endswith('-AC1') or 'accessibility' in tc.get('title', '').lower():
                keep.append(tc)
                continue

            tc_words = _objective_words(tc)
            is_dup = False
            for existing in keep:
                existing_words = _objective_words(existing)
                if not tc_words or not existing_words:
                    continue
                overlap = len(tc_words & existing_words) / len(tc_words | existing_words)
                if overlap > 0.75:
                    is_dup = True
                    break
            if is_dup:
                removed += 1
            else:
                keep.append(tc)

        if removed:
            print(f"  Removed {removed} duplicate test(s)")
            # Renumber IDs after removal
            keep = self._renumber_test_ids(keep, story_id)
        return keep

    def _get_story_platforms(self, acceptance_criteria: List[str]) -> List[str]:
        """Filter global platforms to only those relevant to this story's ACs.

        Primary platform (first in config) is always included.
        Additional platforms only included if explicitly mentioned in AC text.
        """
        all_platforms = getattr(self._project_config.application, 'supported_platforms', [])
        if not all_platforms or len(all_platforms) <= 1:
            return all_platforms

        primary = all_platforms[0]
        ac_text = ' '.join(acceptance_criteria).lower()

        filtered = [primary]
        for platform in all_platforms[1:]:
            if platform.lower() in ac_text:
                filtered.append(platform)

        return filtered

    def _ensure_accessibility_tests(
        self,
        test_cases: List[Dict],
        story_id: str,
        feature_name: str
    ) -> List[Dict]:
        """
        Ensure all required platform accessibility tests are present.
        If missing, add them programmatically.

        Only generates tests for platforms relevant to this story's ACs
        (primary platform always included, others only if mentioned in ACs).
        """
        if not self._project_config:
            return test_cases

        # Get story-scoped platforms (filtered by AC mentions)
        ac_list = getattr(self, '_current_acceptance_criteria', [])
        platforms = self._get_story_platforms(ac_list) if ac_list else \
            getattr(self._project_config.application, 'supported_platforms', [])
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

        print(f"  Warning: Missing accessibility tests for: {', '.join(missing_platforms)}")
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

    # =========================================================================
    # AC COVERAGE VALIDATION — detect uncovered ACs and generate gap-filling tests
    # =========================================================================

    def _extract_ac_keywords(self, ac_text: str) -> set:
        """Extract meaningful keywords from an AC bullet for coverage matching."""
        import re as _re
        # Lowercase and remove punctuation (keep alphanumeric and spaces)
        text = _re.sub(r'[^a-z0-9\s]', ' ', ac_text.lower())
        words = text.split()
        # Filter: remove stop words and short words
        return {w for w in words if w not in AC_STOP_WORDS and len(w) >= 3}

    def _is_meta_ac(self, ac_text: str) -> bool:
        """Check if an AC is a vague meta/catch-all statement (not testable)."""
        import re as _re
        ac_lower = ac_text.lower()
        return any(_re.search(p, ac_lower) for p in META_AC_PATTERNS)

    def _map_acs_to_tests(
        self,
        test_cases: List[Dict],
        acceptance_criteria: List[str]
    ) -> Dict[int, List[str]]:
        """
        Map each in-scope AC to test case IDs that cover it.
        Returns {ac_index (1-based): [test_ids]}. Empty list = uncovered.
        """
        import re as _re

        try:
            from .prompt_builder import clean_acceptance_criteria, split_scope
            cleaned = clean_acceptance_criteria(acceptance_criteria)
            in_scope, _ = split_scope(cleaned)
        except ImportError:
            in_scope = acceptance_criteria

        # Pre-build searchable text blob for each test case (once, reused per AC)
        tc_blobs = []
        for tc in test_cases:
            title = tc.get('title', '').lower()
            objective = tc.get('objective', '').lower()
            step_actions = ' '.join(
                s.get('action', '').lower() for s in tc.get('steps', [])
            )
            step_expected = ' '.join(
                s.get('expected', '').lower() for s in tc.get('steps', [])
            )
            tc_blobs.append(f"{title} {objective} {step_actions} {step_expected}")

        coverage_map = {}

        for ac_idx, ac in enumerate(in_scope, 1):
            keywords = self._extract_ac_keywords(ac)
            if not keywords:
                # Can't extract meaningful keywords — treat as covered
                coverage_map[ac_idx] = ['(no keywords)']
                continue

            matching_tests = []
            min_hits = max(2, int(len(keywords) * 0.4))

            for tc_i, blob in enumerate(tc_blobs):
                hits = sum(
                    1 for kw in keywords
                    if _re.search(rf'\b{_re.escape(kw)}\b', blob)
                )
                if hits >= min_hits:
                    matching_tests.append(test_cases[tc_i].get('id', f'TC-{tc_i}'))

            coverage_map[ac_idx] = matching_tests

        return coverage_map

    def _get_max_test_num(self, test_cases: List[Dict]) -> int:
        """Get the highest numeric test ID from existing test cases."""
        max_id = 0
        for tc in test_cases:
            tc_id = tc.get('id', '')
            if '-' in tc_id:
                try:
                    num_part = tc_id.split('-')[-1]
                    if num_part.isdigit():
                        max_id = max(max_id, int(num_part))
                except (ValueError, IndexError):
                    pass
        return max_id

    def _apply_structural_fixes(self, tc: Dict):
        """Apply structural fixes to a single test case (PRE-REQ, launch, close, cleanup)."""
        if 'title' in tc:
            tc['title'] = self._title_case_scenario(tc['title'])

        steps = tc.get('steps', [])

        # Ensure first step is PRE-REQ
        if steps and 'pre-req' not in steps[0].get('action', '').lower():
            steps.insert(0, {'step': 1, 'action': self._prereq, 'expected': ''})
        elif steps:
            steps[0]['action'] = self._prereq
            steps[0]['expected'] = ''

        # Ensure launch expected
        if len(steps) >= 2:
            action_lower = steps[1].get('action', '').lower()
            if ('launch' in action_lower or 'navigate' in action_lower) and self._launch_expected:
                steps[1]['expected'] = self._launch_expected

        # Ensure last step is close
        if steps:
            last = steps[-1]
            if 'close' not in last.get('action', '').lower() and 'exit' not in last.get('action', '').lower():
                steps.append({'step': len(steps) + 1, 'action': self._close, 'expected': ''})
            else:
                last['action'] = self._close
                last['expected'] = ''

        # Clean forbidden language + renumber steps
        for step in steps:
            step['action'] = self._clean_forbidden_language(step.get('action', ''))
            step['expected'] = self._clean_forbidden_language(step.get('expected', ''))
        for i, step in enumerate(steps, 1):
            step['step'] = i

        tc['steps'] = steps

    def _generate_missing_ac_tests(
        self,
        story_id: str,
        feature_name: str,
        uncovered_acs: List[tuple],
        max_existing_id: int,
        story_description: str = ""
    ) -> List[Dict]:
        """Generate test cases for uncovered ACs via a targeted LLM call."""
        # Get increment from config
        increment = 5
        if self._project_config:
            increment = getattr(self._project_config.rules, 'test_id_increment', 5)

        # Build the uncovered AC list for the prompt
        ac_list_text = ""
        for ac_idx, ac_text in uncovered_acs:
            ac_list_text += f"  AC {ac_idx}: {ac_text}\n"

        # Calculate starting ID
        next_id = max_existing_id + increment

        system_prompt = f"""You are a senior QA test engineer writing test cases for {self._app_name}.
Return ONLY a JSON object: {{"test_cases": [...]}}

Each test case must have:
- "id": "{story_id}-XXX" (3-digit number)
- "title": "{story_id}-XXX: {feature_name} / <Area> / <Scenario In Title Case>"
- "objective": "Verify that <specific behavior>"
- "steps": [{{"step": 1, "action": "...", "expected": "..."}}]

Step structure:
- Step 1: "{self._prereq}" (empty expected)
- Step 2: Launch/Navigate step
- Middle steps: Feature-specific actions with deterministic expected results
- Last step: "{self._close}" (empty expected)

Rules:
- NO forbidden language: "or", "if available", "if supported", "if applicable"
- ONE action per step
- Expected results must be specific and deterministic
- Title format: EXACTLY 3 segments after ID (Feature / Area / Scenario)

CRITICAL GROUNDING RULE:
- ONLY use UI elements, controls, menus, and mechanisms that are EXPLICITLY described in the story description below.
- Do NOT invent, assume, or hallucinate UI elements that are not mentioned in the story.
- If the story says a feature is accessed via a specific menu, use THAT menu — do not create buttons or panels that don't exist."""

        # Build story context for grounding
        story_context = ""
        if story_description:
            # Truncate very long descriptions to avoid token waste
            desc_truncated = story_description[:2000]
            story_context = f"""
## STORY DESCRIPTION (use ONLY UI elements mentioned here):
{desc_truncated}
"""

        user_prompt = f"""The following Acceptance Criteria have ZERO test coverage.
Generate 1-2 focused test cases for EACH uncovered AC.

Story: {story_id} - {feature_name}
{story_context}
## UNCOVERED ACCEPTANCE CRITERIA:
{ac_list_text}
## ID SEQUENCE:
Start test IDs from {story_id}-{next_id:03d}, incrementing by {increment}.

## REQUIREMENTS:
- Generate 1-2 test cases per uncovered AC
- Each test must directly exercise the behavior described in its AC
- ONLY reference UI elements (menus, panels, buttons, tools) that appear in the story description above
- Total new tests: {len(uncovered_acs)} to {len(uncovered_acs) * 2}

Return JSON: {{"test_cases": [...]}}"""

        try:
            result = self._call_llm(system_prompt, user_prompt)
            new_tests = result.get("test_cases", [])

            # Renumber to avoid ID collisions
            current_num = next_id
            for tc in new_tests:
                tc_id = f"{story_id}-{current_num:03d}"
                tc['id'] = tc_id
                # Fix title prefix
                old_title = tc.get('title', '')
                if ':' in old_title:
                    parts = old_title.split(':', 1)
                    tc['title'] = f"{tc_id}:{parts[1]}"
                else:
                    tc['title'] = f"{tc_id}: {feature_name} / General / {old_title}"
                current_num += increment

            return new_tests

        except Exception as e:
            print(f"  → AC gap-fill LLM call failed: {e}")
            return []

    def _ensure_ac_coverage(
        self,
        test_cases: List[Dict],
        story_id: str,
        feature_name: str,
        acceptance_criteria: List[str],
        story_description: str = ""
    ) -> List[Dict]:
        """
        Ensure every in-scope AC has at least one test case covering it.
        If uncovered ACs are found, make a targeted LLM call to generate
        gap-filling tests.
        """
        try:
            from .prompt_builder import clean_acceptance_criteria, split_scope
            cleaned = clean_acceptance_criteria(acceptance_criteria)
            in_scope, _ = split_scope(cleaned)
        except ImportError:
            in_scope = acceptance_criteria

        if not in_scope:
            return test_cases

        # Map ACs to existing tests
        coverage_map = self._map_acs_to_tests(test_cases, acceptance_criteria)

        # Identify uncovered ACs (skip meta-ACs that are vague catch-all statements)
        uncovered = []
        skipped_meta = []
        for ac_idx, test_ids in coverage_map.items():
            if not test_ids:
                ac_text = in_scope[ac_idx - 1]
                if self._is_meta_ac(ac_text):
                    skipped_meta.append((ac_idx, ac_text))
                else:
                    uncovered.append((ac_idx, ac_text))

        if skipped_meta:
            print(f"  Skipped {len(skipped_meta)} meta-AC(s) (not testable):")
            for ac_idx, ac_text in skipped_meta:
                print(f"    AC {ac_idx}: {ac_text[:80]}...")

        if not uncovered:
            print(f"  AC coverage: All {len(in_scope)} ACs covered by existing tests")
            return test_cases

        # Print warnings
        print(f"  Warning: {len(uncovered)} AC(s) have no test coverage:")
        for ac_idx, ac_text in uncovered:
            print(f"    AC {ac_idx}: {ac_text[:80]}...")

        # If no LLM provider, skip remediation
        if not self.provider:
            print(f"  → Cannot generate gap-filling tests (no LLM provider)")
            return test_cases

        # Get highest test ID for numbering
        max_id = self._get_max_test_num(test_cases)

        # Generate tests for missing ACs
        print(f"  → Generating tests for {len(uncovered)} uncovered AC(s)...")
        new_tests = self._generate_missing_ac_tests(
            story_id, feature_name, uncovered, max_id, story_description
        )

        if new_tests:
            # Apply structural fixes to each new test
            for tc in new_tests:
                self._apply_structural_fixes(tc)

            test_cases.extend(new_tests)
            print(f"  → Added {len(new_tests)} gap-filling test(s)")
            for tc in new_tests:
                print(f"    + {tc.get('title', '')[:70]}...")
        else:
            print(f"  → LLM gap-fill returned no tests, skipping")

        return test_cases

    def _resolve_entry_point(self, feature_name: str) -> str:
        """Resolve the entry point menu for a feature using project config mappings.

        Uses prefix-stem matching (leading \\b only) so that stems like
        'dimension' also match 'dimensions', 'propert' matches 'properties', etc.
        Keywords are tried longest-first to prefer specific matches over short ones.
        """
        if not self._project_config:
            return "the application menu"

        import re
        entry_points = getattr(self._project_config.application, 'entry_point_mappings', {})
        feature_lower = feature_name.lower()

        # Sort by keyword length descending — longer (more specific) keywords first
        for keyword, menu in sorted(entry_points.items(), key=lambda kv: len(kv[0]), reverse=True):
            # Leading \b prevents substring false positives (e.g. 'cut' in 'executed')
            # No trailing \b so stems match plurals ('dimension' → 'dimensions')
            if re.search(rf'\b{re.escape(keyword)}', feature_lower):
                return menu

        return "the application menu"

    def _generate_accessibility_test(
        self,
        story_id: str,
        feature_name: str,
        platform: str,
        test_num: int
    ) -> Dict:
        """Generate an accessibility test for a specific platform."""
        platform_lower = platform.lower()
        entry_menu = self._resolve_entry_point(feature_name)

        # Determine test specifics based on platform
        if 'windows' in platform_lower:
            prereq_tool = "Pre-req: Accessibility Insights for Windows is installed"
            nav_action = f"Navigate to {entry_menu} using keyboard."
            verify_action = f"Verify the {feature_name} controls are keyboard accessible."
            verify_expected = f"Keyboard focus moves to {feature_name} controls with visible focus indicator."
            tool_action = f"Verify {feature_name} controls expose meaningful labels in Accessibility Insights."
            tool_expected = "Controls expose correct accessible name and role."
            test_type = "Keyboard navigation and labels"
        elif 'ipad' in platform_lower or 'ios' in platform_lower:
            prereq_tool = "Pre-req: VoiceOver is enabled"
            nav_action = f"Navigate to {entry_menu} using VoiceOver swipe gestures."
            verify_action = f"Verify the {feature_name} controls are announced with meaningful labels."
            verify_expected = f"VoiceOver announces {feature_name} controls with meaningful labels and roles."
            tool_action = "Verify reading order is logical."
            tool_expected = "VoiceOver announces controls in logical order."
            test_type = "VoiceOver navigation"
        elif 'android' in platform_lower:
            prereq_tool = "Pre-req: Accessibility Scanner for Android is installed"
            nav_action = f"Navigate to {entry_menu} using touch gestures."
            verify_action = f"Verify the {feature_name} controls are accessible via touch."
            verify_expected = f"{feature_name} controls respond correctly to touch gestures."
            tool_action = f"Run Accessibility Scanner on the {feature_name} screen."
            tool_expected = "No critical accessibility issues are reported by Accessibility Scanner."
            test_type = "TalkBack and Accessibility Scanner"
        else:
            prereq_tool = f"Pre-req: Accessibility tools for {platform} are available"
            nav_action = f"Navigate to {entry_menu}."
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


def ensure_credentials(config) -> None:
    """Ensure all platform credentials are loaded from environment."""
    # ADO credentials (for source or target)
    if config.source_platform == 'ado' or config.target_platform == 'ado':
        if not config.ado.pat:
            config.ado.pat = os.getenv('ADO_PAT')

    # Jira credentials (for source)
    if config.source_platform == 'jira' and config.jira:
        if not config.jira.api_token:
            config.jira.api_token = os.getenv('JIRA_API_TOKEN')
        if not config.jira.base_url:
            config.jira.base_url = os.getenv('JIRA_BASE_URL', '')
        if not config.jira.email:
            config.jira.email = os.getenv('JIRA_EMAIL', '')

    # TestRail credentials (for target)
    if config.target_platform == 'testrail' and config.testrail:
        if not config.testrail.api_key:
            config.testrail.api_key = os.getenv('TESTRAIL_API_KEY')


def generate_and_correct(
    story_id: int,
    output_dir: str = "output",
    skip_correction: bool = False
) -> bool:
    """
    Generate test cases using non-LLM generator, then correct with LLM.

    Args:
        story_id: Story ID from source platform
        output_dir: Output directory
        skip_correction: If True, skip LLM correction step

    Returns:
        True if successful
    """
    # Get project configuration
    project_manager = get_project_manager()
    project_manager.load_from_directory()
    project_config = project_manager.get_or_create_default()

    source_platform = project_config.source_platform.upper()

    print(f"\nHybrid Test Generation for Story {story_id}")
    print(f"Source Platform: {source_platform}")
    print(f"Mode: {'Non-LLM Only' if skip_correction else 'Non-LLM + LLM Correction'}\n")

    # Step 1: Fetch story data from source platform
    print(f"Step 1: Fetching story data from {source_platform}...")
    try:
        # Ensure credentials are loaded
        ensure_credentials(project_config)

        # Use repository factory for platform-agnostic story fetching
        story_repo = get_story_repository(project_config)
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
        provider_type = getattr(project_config, 'llm_provider', None) or config.LLM_PROVIDER
        api_key = config.EnvironmentConfig.get_llm_api_key() if hasattr(config, 'EnvironmentConfig') else os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "your-api-key-here":
            print(f"\n  Warning: API key for {provider_type} not configured, skipping LLM correction")
        else:
            print(f"\nStep 3: Correcting test cases with LLM ({provider_type})...")
            corrector = LLMCorrector(
                api_key=api_key,
                model=config.LLM_MODEL,
                project_config=project_config,
                provider_type=provider_type
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

    print(f"\nGeneration complete")
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
