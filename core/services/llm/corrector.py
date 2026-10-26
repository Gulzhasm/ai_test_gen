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
import glob
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# The script entry points below (upload_tests_to_platform, generate_and_correct,
# main) import the generator, repositories and exporters locally: importing them
# here made LLMCorrector depend on the order core.services loads its submodules
# (a circular import as soon as the package imports were re-sorted).

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

from ..platform_scope import (
    accessibility_profile,
    mentions_all_platforms,
    platforms_mentioned,
    select_story_platforms,
)

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

# Words that appear in nearly every test's template steps, so they are no
# evidence that a test covers a particular AC.
_COVERAGE_NOISE = {'application', 'app', 'successfully', 'verify', 'test', 'step'}

# Filler ignored when comparing a step with a configured template step
_TEMPLATE_STOP_WORDS = {'the', 'a', 'an', 'to', 'of', 'and', 'in', 'on', 'with', 'for'}

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


def find_existing_test_files(story_id: int, output_dir: str = "output") -> dict[str, str]:
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


def load_existing_test_cases(json_file: str) -> list[dict] | None:
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
    test_cases: list[dict],
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
    from infrastructure.repository_factory import get_story_repository, get_test_repositories

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
            print("  Warning: Test suite not found. Please create a test suite manually.")
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
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        app_config=None,
        project_config=None,  # Full project config for dynamic prompts
        provider_type: str | None = None  # Override provider type
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
        self._qa_rules = getattr(project_config, 'qa_rules', None) if project_config else None
        self._prompt_builder = None
        self._current_requirement_docs = ""
        # Open questions the generator reported (strict grounding); read by the workflow
        self.last_open_questions: list[str] = []

        # Default step templates (can be overridden by app_config or project_config)
        self._app_name = "Application"
        self._prereq = "Pre-req: The application is installed"
        self._launch_step = "Launch the application."
        self._launch_expected = ""
        self._create_file_step = "Create a new file/document."
        self._create_file_expected = "A new blank file is created."
        self._close = "Close the application"

        # Use project_config if available, otherwise fall back to app_config
        if project_config:
            self._app_config = project_config.application
            app_config = project_config.application

        if app_config:
            self._app_name = getattr(app_config, 'name', self._app_name)
            if hasattr(app_config, 'get_prereq_step'):
                self._prereq = app_config.get_prereq_step()
            if hasattr(app_config, 'get_launch_step'):
                self._launch_step = app_config.get_launch_step()
            if hasattr(app_config, 'launch_expected'):
                self._launch_expected = app_config.launch_expected or ""
            if hasattr(app_config, 'get_create_file_step'):
                self._create_file_step = app_config.get_create_file_step()
            if hasattr(app_config, 'create_file_expected'):
                self._create_file_expected = getattr(app_config, 'create_file_expected', '') or ""
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
        test_cases: list[dict],
        story_id: str,
        feature_name: str,
        acceptance_criteria: list[str],
        qa_prep: str,
        reference_steps: list[dict] | None = None,
        story_description: str = "",
        requirement_docs: str = ""
    ) -> list[dict]:
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
        self._current_story_description = story_description
        self._current_requirement_docs = requirement_docs or ""
        self.last_open_questions = []

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
                qa_prep=qa_prep,
                story_description=story_description,
                requirement_docs=requirement_docs
            )
            self._prompt_builder = builder
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

            corrected = result.get("test_cases") if isinstance(result, dict) else None
            corrected = [tc for tc in corrected or [] if isinstance(tc, dict) and tc.get("steps")]
            if isinstance(result, dict):
                self.last_open_questions = [str(q) for q in result.get("open_questions") or [] if str(q).strip()]
            if not corrected:
                raise ValueError("LLM returned no usable test cases")
            if len(corrected) < len(test_cases) // 2:
                print(f"  Warning: LLM returned only {len(corrected)} of {len(test_cases)} "
                      "seed tests; the AC coverage check will backfill gaps")

            # Post-process to ensure correct structure
            corrected = self._post_process_corrections(corrected, story_id)

            # Ensure all required accessibility tests are present
            corrected = self._ensure_accessibility_tests(corrected, story_id, feature_name)

            # Remove duplicate/overlapping test cases
            corrected = self._remove_duplicate_tests(corrected, story_id)

            # Ensure every AC, and every platform an AC names, has a covering test
            corrected = self._ensure_ac_coverage(
                corrected, story_id, feature_name, acceptance_criteria, story_description
            )

            # Second dedup pass — gap-filling and retry may introduce duplicates
            corrected = self._remove_duplicate_tests(corrected, story_id)

            # Enforce minimum test count — retry if under minimum
            min_tests = self._get_minimum_test_count(acceptance_criteria)
            # A computed minimum pushes the model to pad with invented tests; strict
            # projects can turn it off (qa_rules.enforce_min_test_count).
            if len(corrected) < min_tests and self._rule_flag('enforce_min_test_count', True):
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
                test_cases, story_id, feature_name, acceptance_criteria, story_description
            )
            print(f"  Applied post-processing to {len(test_cases)} uncorrected test cases")
            return test_cases

    def _call_llm(self, system_prompt: str, user_prompt: str) -> dict:
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

    def _get_minimum_test_count(self, acceptance_criteria: list[str]) -> int:
        """Calculate the minimum required test count based on story complexity."""
        try:
            from .prompt_builder import (
                calculate_test_requirements,
                clean_acceptance_criteria,
                detect_feature_types,
                detect_format_variations,
                extract_boundary_entities,
                extract_comprehensive_workflows,
                split_scope,
            )

            # Clean ACs first
            cleaned_acs = clean_acceptance_criteria(acceptance_criteria)
            in_scope, _ = split_scope(cleaned_acs)

            # Same story-scoped platform set as the prompt builder
            platform_count = len(self._get_story_platforms(in_scope)) or 1

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
            # Use 1 platform (primary only) as safe fallback to avoid inflated minimums
            return ac_count + 1

    def _retry_for_minimum_count(
        self,
        current_tests: list[dict],
        story_id: str,
        feature_name: str,
        acceptance_criteria: list[str],
        qa_prep: str,
        min_tests: int
    ) -> list[dict]:
        """Retry LLM call with stronger emphasis on meeting minimum count."""
        if not self.provider:
            return current_tests

        shortage = min_tests - len(current_tests)

        retry_prompt = f'''The previous response returned only {len(current_tests)} test cases.
The MINIMUM required is {min_tests} tests. You need {shortage} more.

Current test cases (DO NOT reduce these):
{json.dumps({"test_cases": current_tests}, indent=2)}

## ADDITIONS NEEDED ({shortage} more tests):
Review the acceptance criteria below. For each AC, check whether the existing
tests already cover it with concrete steps. If an AC is NOT yet covered, add a
focused test case for it.

STRICT RULES for new tests:
- Every new test MUST map to a specific AC number. If you cannot cite which AC
  it validates, do NOT add it.
- Do NOT add tests for features, UI elements, or behaviors not explicitly
  mentioned in the ACs.
- Do NOT add stress tests, rapid-action tests, or performance tests unless an
  AC specifically requires them.
- Do NOT add tests for input methods (keyboard shortcuts, mouse clicks) unless
  an AC specifically mentions them.
- Do NOT duplicate coverage already provided by existing tests.
- Accessibility tests (keyboard navigation, color contrast) should ONLY be
  added if the project requires them and they are not already present.

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
                print("  → Retry returned fewer tests, keeping original")
                return current_tests

        except Exception as e:
            print(f"  → Retry failed: {e}")
            return current_tests

    def _build_fallback_prompts(
        self,
        story_id: str,
        feature_name: str,
        acceptance_criteria: list[str],
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
2. ADD edge case tests ONLY when the AC explicitly describes the behavior being tested (e.g., error handling, validation, min/max limits)
3. ADD negative tests ONLY for operations the AC explicitly mentions can fail or have invalid states
4. ADD boundary value tests ONLY at limits explicitly defined in the ACs — do NOT invent limits
5. WRITE tests as if a human expert QA engineer wrote them

## ANTI-HALLUCINATION RULES
- Do NOT add tests for interactions the feature doesn't support (e.g., "invalid dimensions" for mouse-drag operations)
- Do NOT invent UI elements, options, or menu items not described in the story/ACs
- Do NOT add keyboard shortcut tests unless the AC explicitly mentions keyboard shortcuts
- Every test must map to a specific AC. If you cannot cite which AC it validates, do NOT add it.

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
2. ADD edge case tests ONLY if AC explicitly describes testable edge conditions
3. ADD negative tests ONLY for operations the AC says can fail or have invalid states
4. ADD boundary value tests ONLY at AC-defined limits (do NOT invent limits)
5. ADD accessibility tests for supported platforms
6. Do NOT add tests for features, interactions, or UI elements not mentioned in the ACs

## OUTPUT
Return enhanced JSON: {{"test_cases": [...]}}'''

        return system_prompt, user_prompt

    def _renumber_test_ids(self, test_cases: list[dict], story_id: str) -> list[dict]:
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
            elif old_title and ':' not in old_title:
                # The model dropped the ID prefix entirely
                tc['title'] = f"{new_id}: {old_title.strip()}"
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

    def _post_process_corrections(self, test_cases: list[dict], story_id: str) -> list[dict]:
        """Post-process LLM corrections to ensure structure compliance."""
        # First, renumber test IDs to ensure proper sequence (AC1, 005, 010, 015, ...)
        test_cases = self._renumber_test_ids(test_cases, story_id)
        for tc in test_cases:
            self._normalize_structure(tc)
        return test_cases

    # =========================================================================
    # STEP STRUCTURE — recognised by the project's own templates, not keywords
    # =========================================================================

    @staticmethod
    def _step_words(text: str) -> set:
        return set(re.findall(r'[a-z0-9]+', (text or '').lower())) - _TEMPLATE_STOP_WORDS

    def _matches_template(self, action: str, template: str) -> bool:
        """True when ``action`` is (a shortened form of) the configured ``template`` step."""
        action_words, template_words = self._step_words(action), self._step_words(template)
        if not action_words or not template_words:
            return False
        overlap = len(action_words & template_words)
        return overlap / min(len(action_words), len(template_words)) >= 0.8

    def _is_launch_step(self, action: str) -> bool:
        if self._matches_template(action, self._launch_step):
            return True
        app = re.escape(self._app_name.lower())
        return bool(re.match(
            rf'^\s*(?:launch\b|(?:start|open|run)\s+(?:the\s+)?(?:{app}|app|application)\b)',
            (action or '').lower()))

    def _is_close_step(self, action: str) -> bool:
        """True for the app-level close / sign-out step — not "Close the About dialog"."""
        if self._matches_template(action, self._close):
            return True
        text = (action or '').strip().lower()
        if re.match(r'^(?:sign|log)\s*(?:out|off)\W*$', text):
            return True
        app = re.escape(self._app_name.lower())
        return bool(re.match(
            rf'^(?:close|exit|quit|sign\s*out|log\s*(?:out|off))\b(?:\s+(?:of|from))?'
            rf'\s+(?:the\s+)?(?:{app}|app|application)\b', text))

    def _normalize_structure(self, tc: dict) -> None:
        """Enforce Pre-req → Launch → … → Close using the configured templates.

        Steps are recognised by similarity to the project's own templates, not by
        keywords. A web app's launch step itself starts with "Navigate to …" and
        its close step is "Sign out of …"; keyword matching inserted a second
        launch step and appended a second sign-out. A feature step such as
        "Close the About dialog" keeps its expected result.
        """
        if 'title' in tc:
            tc['title'] = self._title_case_scenario(tc['title'])
        steps = [s for s in tc.get('steps', []) if isinstance(s, dict)]
        if not steps:
            tc['steps'] = steps
            return

        if self._strict():
            self._normalize_structure_strict(tc, steps)
            return

        # The template pre-req comes first; test-specific pre-reqs stay after it
        if self._matches_template(steps[0].get('action', ''), self._prereq):
            steps[0]['action'] = self._prereq
        else:
            steps.insert(0, {'action': self._prereq, 'expected': ''})

        # Launch right after the leading pre-req steps
        idx = 0
        while idx < len(steps) and steps[idx].get('action', '').lower().startswith('pre-req'):
            idx += 1
        if idx < len(steps) and self._is_launch_step(steps[idx].get('action', '')):
            steps[idx]['action'] = self._launch_step
            if self._launch_expected:
                steps[idx]['expected'] = self._launch_expected
        elif self._launch_step and not any(self._is_launch_step(s.get('action', '')) for s in steps):
            steps.insert(idx, {'action': self._launch_step, 'expected': self._launch_expected})

        # App close / sign-out last, with an empty expected result
        if self._is_close_step(steps[-1].get('action', '')):
            steps[-1]['action'] = self._close
        elif self._close:
            steps.append({'action': self._close, 'expected': ''})
        steps[-1]['expected'] = ''

        for step in steps:
            if step.get('action', '').lower().startswith('pre-req'):
                step['expected'] = ''
            step['action'] = self._clean_forbidden_language(step.get('action', ''))
            step['expected'] = self._clean_forbidden_language(step.get('expected', ''))
        for i, step in enumerate(steps, 1):
            step['step'] = i
        tc['steps'] = steps

    def _normalize_structure_strict(self, tc: dict, steps: list[dict]) -> None:
        """Strict grounding: templates are patterns the model fills per test (roles in the
        Pre-req, the named role in the sign-in step), so they are never pasted back literally.

        - One Pre-req first: keep the model's own Pre-req, merge further "Pre-req:" steps and
          role-definition lines ("Name: definition.") with no expected result into it, and drop
          unfilled template text containing "<...>".
        - Steps still holding a template placeholder are removed.
        - The closing sign-out step is last with an empty expected result.
        """
        placeholder = re.compile(r"<[^>]+>")
        base_prereq = placeholder.split(self._prereq)[0].strip() or "Pre-req:"
        prereq_parts: list[str] = []
        body: list[dict] = []
        for st in steps:
            action = (st.get('action') or '').strip()
            expected = (st.get('expected') or '').strip()
            if action.lower().startswith('pre-req'):
                text = placeholder.sub('', action.split(':', 1)[-1]).strip(' .')
                if text:
                    prereq_parts.append(text)
                continue
            if not expected and not body and re.match(r"^[A-Z][\w' /-]{2,60}: \S", action):
                prereq_parts.append(action.rstrip('.'))     # role definition spilled into its own step
                continue
            if placeholder.search(action):
                continue                                    # unfilled template step
            body.append({'action': action, 'expected': expected})

        merged: list[str] = []
        for part in prereq_parts:
            for sentence in re.split(r"(?<=\.)\s+", part):
                sentence = sentence.strip(' .:')
                if not re.search(r"[A-Za-z]", sentence):
                    continue                                # leftover of a removed placeholder
                if sentence.lower() not in {m.lower() for m in merged}:
                    merged.append(sentence)
        prereq = "Pre-req: " + ". ".join(merged) + "." if merged else base_prereq
        steps = [{'action': prereq, 'expected': ''}] + body

        if len(steps) > 1 and self._is_close_step(steps[-1].get('action', '')):
            steps[-1]['action'] = self._close
        elif self._close:
            steps.append({'action': self._close, 'expected': ''})
        steps[-1]['expected'] = ''
        for step in steps:
            step['action'] = self._clean_forbidden_language(step.get('action', ''))
            step['expected'] = self._clean_forbidden_language(step.get('expected', ''))
        for i, step in enumerate(steps, 1):
            step['step'] = i
        tc['steps'] = steps

    def _setup_policy(self) -> str:
        """Context setup policy from config: always | when_needed | never."""
        if not self._create_file_step:
            return 'never'
        app = self._app_config
        return (getattr(app, 'setup_step_policy', 'always') or 'always').lower() if app else 'always'

    def _setup_step_line(self) -> str:
        """Prompt line describing the context setup step, per the project's policy."""
        policy = self._setup_policy()
        if policy == 'never':
            return ''
        qualifier = ' (ONLY when the feature needs this context)' if policy == 'when_needed' else ''
        return (f'- Step 3{qualifier}: "{self._create_file_step}" '
                f'(expected: "{self._create_file_expected}")\n')

    def _remove_duplicate_tests(self, test_cases: list[dict], story_id: str) -> list[dict]:
        """Drop a test only when an earlier test has the same goal AND the same steps.

        Objective wording alone is not enough: platform variants and tests with
        different oracles share most of their words ("… on Windows 11" vs
        "… on iPad"). Tests that target different platforms are never
        duplicates. AC1 and accessibility tests are always kept; the earlier
        test wins.
        """
        if len(test_cases) <= 1:
            return test_cases

        app = self._app_config
        platforms = getattr(app, 'supported_platforms', []) if app else []
        aliases = getattr(app, 'platform_aliases', None) if app else None
        stop = {'a', 'an', 'the', 'is', 'are', 'of', 'to', 'and', 'or', 'in',
                'on', 'that', 'for', 'by', 'it', 'its', 'with', 'can', 'be', 'not',
                'verify', 'b'}

        def _words(text: str) -> set:
            return set(re.findall(r'[a-z0-9]+', re.sub(r'<[^>]+>', ' ', text or '').lower())) - stop

        def _jaccard(a: set, b: set) -> float:
            return len(a & b) / len(a | b) if a and b else 0.0

        def _profile(tc: dict) -> tuple:
            objective = _words(tc.get('objective') or tc.get('title', ''))
            steps = _words(' '.join(
                f"{s.get('action', '')} {s.get('expected', '')}" for s in tc.get('steps', [])))
            tags = frozenset(platforms_mentioned(
                f"{tc.get('title', '')} {tc.get('objective', '')}", platforms, aliases,
                include_generic=False))
            return objective, steps, tags

        keep: list[dict] = []
        profiles: list[tuple] = []
        removed = []
        for tc in test_cases:
            tc_id = tc.get('id', '')
            profile = _profile(tc)
            if tc_id.endswith('-AC1') or 'accessibility' in tc.get('title', '').lower():
                keep.append(tc)
                profiles.append(profile)
                continue

            duplicate_of = next(
                (existing.get('id', '') for existing, other in zip(keep, profiles)
                 if other[2] == profile[2]
                 and _jaccard(profile[0], other[0]) > 0.75
                 and _jaccard(profile[1], other[1]) > 0.8),
                None,
            )
            if duplicate_of:
                removed.append(f"{tc_id} (same as {duplicate_of})")
            else:
                keep.append(tc)
                profiles.append(profile)

        if removed:
            print(f"  Removed {len(removed)} duplicate test(s): {', '.join(removed)}")
            # Renumber IDs after removal
            keep = self._renumber_test_ids(keep, story_id)
        return keep

    def _get_story_platforms(self, acceptance_criteria: list[str]) -> list[str]:
        """Platforms this story needs tests for (see core.services.platform_scope).

        Primary platform (first in config) is always included; others when the
        ACs or the feature name refer to them by name or alias.
        """
        app = self._project_config.application if self._project_config else self._app_config
        all_platforms = list(getattr(app, 'supported_platforms', []) or []) if app else []
        texts = list(acceptance_criteria) + [getattr(self, '_current_feature_name', '')]
        return select_story_platforms(all_platforms, texts, getattr(app, 'platform_aliases', None))

    def _rule_flag(self, name: str, default: bool) -> bool:
        return bool(getattr(self._qa_rules, name, default)) if self._qa_rules is not None else default

    def _strict(self) -> bool:
        return self._rule_flag('strict_grounding', False)

    def _grounding_rules_text(self) -> str:
        """The strict source rules, also for a corrector that never ran the main pass."""
        if self._prompt_builder is None and PROMPT_BUILDER_AVAILABLE and self._project_config:
            self._prompt_builder = PromptBuilder.from_project_config(
                config=self._project_config, story_id="", feature_name="",
                acceptance_criteria=[], requirement_docs=self._current_requirement_docs)
        return self._prompt_builder._strict_grounding_rules() if self._prompt_builder else ""

    def _ensure_accessibility_tests(
        self,
        test_cases: list[dict],
        story_id: str,
        feature_name: str
    ) -> list[dict]:
        """
        Ensure all required platform accessibility tests are present.
        If missing, add them programmatically.

        Only generates tests for platforms relevant to this story's ACs
        (primary platform always included, others only if mentioned in ACs).
        """
        # Projects can require an AC or requirement document to ask for accessibility
        # before any test is added (qa_rules.auto_accessibility_tests: false).
        if not self._rule_flag('auto_accessibility_tests', True):
            return test_cases
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
        test_cases: list[dict],
        acceptance_criteria: list[str]
    ) -> dict[int, list[str]]:
        """
        Map each in-scope AC to test case IDs that cover it.
        Returns {ac_index (1-based): [test_ids]}. Empty list = uncovered.

        Evidence comes from the objective and the feature steps only. Template
        steps (pre-req, launch, setup, close) repeat the app name and words
        like "application" and "successfully" in every test, which used to make
        unrelated ACs look covered. A declared ``ac_refs`` entry counts when at
        least one AC keyword also appears in the test.
        """
        in_scope = self._in_scope_acs(acceptance_criteria)
        noise = self._step_words(self._app_name) | _COVERAGE_NOISE

        # Pre-build searchable text blob for each test case (once, reused per AC)
        tc_blobs = []
        for tc in test_cases:
            feature_steps = ' '.join(
                f"{s.get('action', '')} {s.get('expected', '')}"
                for s in tc.get('steps', [])
                if not self._is_boilerplate_step(s.get('action', ''))
            )
            tc_blobs.append(f"{tc.get('objective', '')} {feature_steps}".lower())

        coverage_map = {}
        for ac_idx, ac in enumerate(in_scope, 1):
            keywords = self._extract_ac_keywords(ac) - noise
            if not keywords:
                # Can't extract meaningful keywords — treat as covered
                coverage_map[ac_idx] = ['(no keywords)']
                continue

            min_hits = min(len(keywords), max(2, int(len(keywords) * 0.4)))
            matching_tests = []
            for tc_i, blob in enumerate(tc_blobs):
                hits = sum(1 for kw in keywords if re.search(rf'\b{re.escape(kw)}\b', blob))
                declared = ac_idx in (test_cases[tc_i].get('ac_refs') or [])
                if hits >= min_hits or (declared and hits >= 1):
                    matching_tests.append(test_cases[tc_i].get('id', f'TC-{tc_i}'))
            coverage_map[ac_idx] = matching_tests

        return coverage_map

    @staticmethod
    def _in_scope_acs(acceptance_criteria: list[str]) -> list[str]:
        """Cleaned, in-scope ACs — the numbering prompts and ``ac_refs`` use."""
        try:
            from .prompt_builder import clean_acceptance_criteria, split_scope
        except ImportError:
            return list(acceptance_criteria)
        in_scope, _ = split_scope(clean_acceptance_criteria(acceptance_criteria))
        return in_scope

    def _is_boilerplate_step(self, action: str) -> bool:
        """Template steps (pre-req, launch, context setup, close) say nothing about any AC."""
        action = action or ''
        return (action.lower().startswith('pre-req')
                or self._is_launch_step(action)
                or self._is_close_step(action)
                or self._matches_template(action, self._create_file_step))

    def _missing_platform_variants(
        self,
        test_cases: list[dict],
        in_scope: list[str],
        coverage_map: dict[int, list[str]],
    ) -> list[tuple]:
        """(ac_index, text) for each platform an AC names that none of its tests exercise.

        "Verified on Windows, iOS and Android" is three obligations; one covering
        test on Windows used to satisfy the whole AC.
        """
        app = self._app_config
        aliases = getattr(app, 'platform_aliases', None) if app else None
        story_platforms = self._get_story_platforms(in_scope)
        if len(story_platforms) <= 1:
            return []

        by_id = {tc.get('id'): tc for tc in test_cases}
        gaps = []
        for ac_idx, ac in enumerate(in_scope, 1):
            named = (story_platforms if mentions_all_platforms(ac)
                     else platforms_mentioned(ac, story_platforms, aliases))
            covering = [by_id[i] for i in coverage_map.get(ac_idx, []) if i in by_id]
            if len(named) < 2 or not covering:
                continue
            exercised = set()
            for tc in covering:
                if 'accessibility' in tc.get('title', '').lower():
                    continue
                text = tc.get('title', '') + ' ' + ' '.join(
                    f"{s.get('action', '')} {s.get('expected', '')}" for s in tc.get('steps', []))
                exercised.update(platforms_mentioned(text, named, aliases, include_generic=False))
            gaps.extend(
                (ac_idx, f"{ac} [variant not yet covered: {p}]")
                for p in named if p not in exercised
            )
        return gaps

    def _get_max_test_num(self, test_cases: list[dict]) -> int:
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

    def _apply_structural_fixes(self, tc: dict):
        """Apply structural fixes to a single test case (PRE-REQ, launch, close, cleanup)."""
        self._normalize_structure(tc)

    def _generate_missing_ac_tests(
        self,
        story_id: str,
        feature_name: str,
        uncovered_acs: list[tuple],
        max_existing_id: int,
        story_description: str = "",
        existing_tests: list[dict] = None
    ) -> list[dict]:
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
- "ac_refs": [<number of the uncovered AC this test verifies>]
- "steps": [{{"step": 1, "action": "...", "expected": "..."}}]

MANDATORY step structure (follow this EXACT pattern):
- Step 1: "{self._prereq}" (empty expected)
- Step 2: "{self._launch_step}" (expected: "{self._launch_expected}")
{self._setup_step_line()}- Then: Navigate to the feature using the exact menu path ("Select 'MenuName' > 'CommandName'.")
- Middle steps: Feature-specific actions — ONE action per step, deterministic expected results
- Last step: "{self._close}" (empty expected)

IMPORTANT: Do NOT combine launch + navigation into a single step. Each action must be a separate step.

Rules:
- NO forbidden language: "or", "if available", "if supported", "if applicable"
- ONE action per step — never combine two actions
- Expected results must be specific and deterministic (never empty for middle steps)
- Title format: EXACTLY 3 segments after ID (Feature / Area / Scenario)
- When an uncovered item ends with "[variant not yet covered: X]", write the test for platform X and end the scenario with "(X)".
- Expected results state ONE concrete, observable outcome, using the story's own values (versions, labels, messages) when it gives them. Never "works correctly", "as expected" or "displays correctly", and never invent a value.
- When an AC is a release or process step that happens OUTSIDE the application (store submission, approvals, work-item states), test it where it happens — the store's developer console, the work-item tracker — named in a Pre-req. Never look for it in the application's menus.
- Steps and expected results must not contradict the DOMAIN NOTES below.

CRITICAL GROUNDING RULE:
- ONLY use UI elements, controls, menus, and mechanisms that are EXPLICITLY described in the story description or acceptance criteria below.
- Do NOT invent, assume, or hallucinate UI elements, options, or behaviors that are not mentioned in the story.
- If the story says a feature is accessed via a specific mechanism (e.g., mouse drag on Canvas), use THAT mechanism — do not create buttons, panels, or menu options that don't exist.
- Do NOT add edge cases, invalid input tests, or negative scenarios UNLESS the AC explicitly describes that behavior (e.g., error handling, validation rules, min/max limits).
- Do NOT add keyboard shortcut or accessibility tests — those are handled separately."""

        # Build story context for grounding — include FULL description, not truncated
        story_context = ""
        if story_description:
            story_context = f"""
## STORY DESCRIPTION (use ONLY UI elements and mechanisms mentioned here):
{story_description}
"""

        # Add app config constraints for grounding
        app_constraints = ""
        if self._project_config:
            app_cfg = self._project_config.application
            ui_surfaces = getattr(app_cfg, 'main_ui_surfaces', [])
            forbidden_ui = getattr(app_cfg, 'forbidden_ui_terms', [])
            unavailable = getattr(app_cfg, 'unavailable_features', [])
            if ui_surfaces:
                app_constraints += f"\n## VALID UI SURFACES (only reference these):\n{', '.join(ui_surfaces)}\n"
            if forbidden_ui:
                app_constraints += f"\n## FORBIDDEN UI TERMS (do NOT use these — they don't exist):\n{', '.join(forbidden_ui)}\n"
            if unavailable:
                app_constraints += f"\n## UNAVAILABLE FEATURES (do NOT reference these):\n{', '.join(unavailable)}\n"
            notes = getattr(app_cfg, 'feature_notes', {}) or {}
            if notes:
                app_constraints += "\n## DOMAIN NOTES (do NOT contradict these):\n" + "".join(
                    f"- {topic}: {note}\n" for topic, note in notes.items())

        # Extract example steps from existing tests to enforce consistent wording
        example_section = ""
        if existing_tests:
            # Take first test that has 5+ steps as the wording reference
            reference = next((tc for tc in existing_tests if len(tc.get('steps', [])) >= 5), None)
            if reference:
                ref_steps = reference.get('steps', [])
                example_lines = []
                for s in ref_steps[:5]:  # Show first 5 steps
                    example_lines.append(f'    {{"step": {s.get("step", "")}, "action": "{s.get("action", "")}", "expected": "{s.get("expected", "")}"}}')
                example_section = f"""
## EXAMPLE STEPS (use this EXACT wording style for navigation):
```json
[
{chr(10).join(example_lines)}
]
```
IMPORTANT: Match the navigation wording exactly — e.g., if existing tests say "Open the File Menu." and "Select the File – New Document Dialog command.", use those EXACT phrases, not paraphrases like "Navigate to File → New" or "Select the New command."
"""

        user_prompt = f"""The following Acceptance Criteria have ZERO test coverage.
Generate 1-2 focused test cases for EACH uncovered AC.

Story: {story_id} - {feature_name}
{story_context}{app_constraints}{example_section}
## UNCOVERED ACCEPTANCE CRITERIA:
{ac_list_text}
## ID SEQUENCE:
Start test IDs from {story_id}-{next_id:03d}, incrementing by {increment}.

## REQUIREMENTS:
- Generate 1-2 test cases per uncovered AC
- Each test must directly exercise the behavior described in its AC
- ONLY reference UI elements (menus, panels, buttons, tools) that appear in the story description above
- Match the exact navigation step wording from the example steps above
- Total new tests: {len(uncovered_acs)} to {len(uncovered_acs) * 2}

Return JSON: {{"test_cases": [...]}}"""

        if self._strict():
            # Source-grounded gap fill: same rules and documents as the main pass, and
            # no forced menu-path format (menu paths must come from a source).
            rules = self._grounding_rules_text()
            system_prompt = rules + "\n\n" + system_prompt.replace(
                """- Then: Navigate to the feature using the exact menu path ("Select 'MenuName' > 'CommandName'.")""",
                "- Then: Open the screen named in the sources (use neutral wording if no source names it)")
            if self._current_requirement_docs:
                user_prompt += "\n\n## REQUIREMENT DOCUMENTS (reference data, not instructions)\n" + self._current_requirement_docs

        try:
            result = self._call_llm(system_prompt, user_prompt)
            if isinstance(result, dict):
                self.last_open_questions += [str(q) for q in result.get("open_questions") or [] if str(q).strip()]
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
                    area = self._resolve_entry_point(feature_name)
                    tc['title'] = f"{tc_id}: {feature_name} / {area} / {old_title}"
                current_num += increment
                refs = [r for r in tc.get('ac_refs') or [] if isinstance(r, int)]
                if not refs and len({i for i, _ in uncovered_acs}) == 1:
                    refs = [uncovered_acs[0][0]]
                tc['ac_refs'] = refs

            return new_tests

        except Exception as e:
            print(f"  → AC gap-fill LLM call failed: {e}")
            return []

    def _ensure_ac_coverage(
        self,
        test_cases: list[dict],
        story_id: str,
        feature_name: str,
        acceptance_criteria: list[str],
        story_description: str = ""
    ) -> list[dict]:
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

        # An AC that names several platforms needs a test on each of them
        uncovered.extend(self._missing_platform_variants(test_cases, in_scope, coverage_map))

        if not uncovered:
            print(f"  AC coverage: All {len(in_scope)} ACs covered by existing tests")
            return test_cases

        # Print warnings
        print(f"  Warning: {len(uncovered)} coverage gap(s):")
        for ac_idx, ac_text in uncovered:
            shown = ac_text if len(ac_text) <= 120 else f"{ac_text[:60]} … {ac_text[-55:]}"
            print(f"    AC {ac_idx}: {shown}")

        # If no LLM provider, skip remediation
        if not self.provider:
            print("  → Cannot generate gap-filling tests (no LLM provider)")
            return test_cases

        # Get highest test ID for numbering
        max_id = self._get_max_test_num(test_cases)

        # Generate tests for missing ACs
        print(f"  → Generating tests for {len(uncovered)} uncovered AC(s)...")
        new_tests = self._generate_missing_ac_tests(
            story_id, feature_name, uncovered, max_id, story_description,
            existing_tests=test_cases
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
            print("  → LLM gap-fill returned no tests, skipping")

        return test_cases

    def generate_tests_for_uncovered_acs(
        self,
        uncovered: list[tuple],
        existing_tests: list[dict],
        story_id: str,
        feature_name: str,
        story_description: str = "",
    ) -> list[dict]:
        """Gap-fill hook for the judge: tests for the (ac_number, ac_text) pairs it reports."""
        if not self.provider:
            return []
        new_tests = self._generate_missing_ac_tests(
            story_id, feature_name, uncovered, self._get_max_test_num(existing_tests),
            story_description, existing_tests=existing_tests,
        )
        for tc in new_tests:
            self._normalize_structure(tc)
        return new_tests

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
    ) -> dict:
        """Generate an accessibility test for one platform from the project's own steps.

        Tool and input mode come from platform_scope.accessibility_profile, so a
        web app on "Chrome (Windows 11)" is checked with web tooling. Launch and
        setup steps come from config (never a hardcoded "Launch the app").
        """
        app = self._app_config
        profile = accessibility_profile(
            platform, getattr(app, 'app_type', 'desktop') if app else 'desktop',
            getattr(app, 'accessibility_tools', None) if app else None)
        tool = profile['tool']
        entry = self._resolve_entry_point(feature_name)

        steps = [
            {'action': self._prereq, 'expected': ''},
            {'action': f"Pre-req: {tool} is available on {platform}", 'expected': ''},
            {'action': self._launch_step, 'expected': self._launch_expected},
        ]
        policy = self._setup_policy()
        needs_setup = policy == 'always' or (
            policy == 'when_needed' and app is not None
            and hasattr(app, 'requires_object_interaction')
            and app.requires_object_interaction(feature_name))
        if needs_setup:
            steps.append({'action': self._create_file_step, 'expected': self._create_file_expected})
        if profile['input'] == 'touch':
            steps.append({
                'action': f"With {tool} on, swipe through {entry} and the {feature_name} controls.",
                'expected': f"{tool} announces every {feature_name} control with a meaningful "
                            "name and role, in a logical order.",
            })
        else:
            steps.append({
                'action': f"Using only the keyboard (Tab, Shift+Tab, Enter, arrow keys), open "
                          f"{entry} and move through the {feature_name} controls.",
                'expected': "Every control receives focus in a logical order, shows a visible "
                            "focus indicator and can be operated from the keyboard.",
            })
        steps.append({
            'action': f"Run {tool} on the {feature_name} screen.",
            'expected': "No critical accessibility issues are reported; text contrast is at "
                        "least 4.5:1 (WCAG 2.1 AA).",
        })
        steps.append({'action': self._close, 'expected': ''})
        for i, step in enumerate(steps, 1):
            step['step'] = i

        test_id = f"{story_id}-{test_num:03d}"
        return {
            'id': test_id,
            'title': f"{test_id}: {feature_name} / Accessibility / {profile['test_type']} ({platform})",
            'objective': f"Verify that <b>{feature_name}</b> controls meet <b>WCAG 2.1 AA</b> "
                         f"standards on <b>{platform}</b>",
            'ac_refs': [],
            'steps': steps,
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
    from core.config import environment as config
    from core.services import GenericTestGenerator
    from infrastructure.export import CSVGenerator, ObjectiveGenerator
    from infrastructure.repository_factory import get_story_repository
    from projects import get_project_manager

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
        api_key = config.EnvironmentConfig.get_llm_api_key(provider_type) if hasattr(config, 'EnvironmentConfig') else os.getenv("OPENAI_API_KEY")
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

    print("\nGeneration complete")
    print(f"  Story: {story_id} - {title}")
    print(f"  Test cases generated: {len(test_cases)}")
    print(f"  Output directory: {output_dir}")
    print("\nFiles created:")
    print(f"  - {csv_filename}")
    print(f"  - {obj_filename}")
    print(f"  - {json_filename}")

    return True


def main():
    from projects import get_project_manager

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
