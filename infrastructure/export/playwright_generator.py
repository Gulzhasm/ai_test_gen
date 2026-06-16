"""
Playwright Script Generator

Generates Playwright TypeScript test scripts from test cases using LLM.
Follows the same export pattern as CSVGenerator and ObjectiveGenerator.
"""
import os
import re
from typing import Dict, List, Optional


class PlaywrightGenerator:
    """
    Generates Playwright .spec.ts files from test case dicts.

    Uses LLM to convert Action/Expected steps into Playwright commands.
    Falls back to deterministic template if LLM is unavailable or fails.

    When an element inventory (captured by scripts/extract_ui_inventory.py) is
    available, selectors are GROUNDED in real observed UI elements and a
    grounding-coverage metric is reported. Without an inventory, behavior is
    unchanged (the LLM guesses selectors).
    """

    def __init__(
        self,
        app_name: str = "Application",
        app_type: str = "desktop",
        provider_type: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        inventory_path: Optional[str] = None,
    ):
        self._app_name = app_name
        self._app_type = app_type
        self._provider_type = provider_type
        self._model = model
        self._api_key = api_key
        self._inventory_path = inventory_path
        self._inventory = None
        self._inventory_loaded = False
        self._provider = None

    @property
    def inventory(self):
        """Lazy-load the element inventory from disk (None if unavailable)."""
        if not self._inventory_loaded:
            self._inventory_loaded = True
            if self._inventory_path and os.path.exists(self._inventory_path):
                try:
                    from core.domain.ui_element import ElementInventory
                    self._inventory = ElementInventory.load(self._inventory_path)
                    print(f"  Grounding Playwright selectors in {len(self._inventory.elements)} "
                          f"UI elements from {self._inventory_path}")
                except Exception as e:
                    print(f"  Warning: could not load UI inventory ({e}); generating ungrounded")
            elif self._inventory_path:
                print(f"  Note: UI inventory not found at {self._inventory_path}; generating ungrounded. "
                      f"Run scripts/extract_ui_inventory.py to create it.")
        return self._inventory

    @property
    def provider(self):
        """Lazy initialization of LLM provider via factory."""
        if self._provider is None and self._provider_type:
            try:
                from core.services.llm.factory import create_llm_provider
                self._provider = create_llm_provider(
                    provider_type=self._provider_type,
                    model=self._model or "gpt-4o-mini",
                    timeout=120,
                    max_retries=2,
                    api_key=self._api_key
                )
            except Exception as e:
                print(f"  Warning: Could not create LLM provider for Playwright: {e}")
        return self._provider

    def generate_script(
        self,
        test_cases: List[Dict],
        story_id: str,
        feature_name: str,
        output_file: str
    ) -> str:
        """Generate Playwright script and save to file. Returns script content."""
        content = self.generate_script_string(test_cases, story_id, feature_name)
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        return content

    def generate_script_string(
        self,
        test_cases: List[Dict],
        story_id: str,
        feature_name: str
    ) -> str:
        """Generate Playwright script as string. LLM first, fallback if it fails."""
        # Filter out accessibility tests (need separate Axe tooling)
        functional_tests = [
            tc for tc in test_cases
            if 'accessibility' not in tc.get('title', '').lower()
        ]

        if not functional_tests:
            return self._generate_deterministic([], story_id, feature_name)

        if self.provider:
            script = self._generate_with_llm(functional_tests, story_id, feature_name)
            if script and self._validate_script(script):
                self._report_grounding(script)
                return script
            print("  Warning: LLM Playwright output invalid, using deterministic fallback")

        return self._generate_deterministic(functional_tests, story_id, feature_name)

    def _generate_with_llm(self, test_cases: List[Dict], story_id: str, feature_name: str) -> Optional[str]:
        """Generate script using LLM."""
        from core.services.llm.playwright_prompt_builder import PlaywrightPromptBuilder

        builder = PlaywrightPromptBuilder(
            app_name=self._app_name,
            app_type=self._app_type,
            story_id=story_id,
            feature_name=feature_name,
            element_inventory=self.inventory,
        )
        system_prompt = builder.build_system_prompt()
        user_prompt = builder.build_user_prompt(test_cases)

        try:
            result = self.provider.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.2,
                max_tokens=16000
            )
            if result is None:
                return None

            # Handle both Dict (Gemini) and LLMResponse (OpenAI) return types
            if isinstance(result, dict):
                content = result.get("content", "")
            else:
                content = getattr(result, "content", "")

            if not content:
                return None

            # Strip markdown fences if LLM wrapped the code
            content = content.strip()
            for prefix in ('```typescript', '```ts', '```'):
                if content.startswith(prefix):
                    content = content[len(prefix):].strip()
                    break
            if content.endswith('```'):
                content = content[:-3].strip()

            return content

        except Exception as e:
            print(f"  Playwright LLM generation failed: {e}")
            return None

    def _validate_script(self, script: str) -> bool:
        """Basic structural validation of generated TypeScript."""
        if not script or len(script) < 50:
            return False
        has_import = "import" in script and "playwright" in script.lower()
        has_test = "test(" in script or "test.describe(" in script
        balanced = script.count('{') == script.count('}')
        return has_import and has_test and balanced

    def _report_grounding(self, script: str) -> None:
        """Non-fatal grounding check: how many generated selectors map to real elements?"""
        if not self.inventory:
            return
        result = analyze_grounding(script, self.inventory)
        total = result["total"]
        if total == 0:
            return
        pct = result["coverage"] * 100
        print(f"  Selector grounding: {result['grounded']}/{total} ({pct:.0f}%) "
              f"resolve to real elements")
        if result["ungrounded"]:
            for sel in result["ungrounded"][:10]:
                print(f"    ungrounded: {sel}")
        n_todo = len(re.findall(r"//\s*TODO:\s*Update selector", script))
        if n_todo:
            print(f"  Warning: {n_todo} '// TODO: Update selector' comment(s) — expected 0 when grounded")
        n_ungrounded_comments = len(re.findall(r"//\s*UNGROUNDED:", script))
        if n_ungrounded_comments:
            print(f"  Note: {n_ungrounded_comments} step(s) marked // UNGROUNDED (no matching element)")

    def _generate_deterministic(self, test_cases: List[Dict], story_id: str, feature_name: str) -> str:
        """Deterministic fallback: generate skeleton .spec.ts from test cases."""
        lines = [
            f"// Story: {story_id} - {feature_name}",
            f"// Auto-generated Playwright test skeleton",
            f"// TODO: Update selectors for actual application UI",
            "",
            "import { test, expect } from '@playwright/test';",
            "",
            "const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';",
            "",
            f"test.describe('{story_id}: {feature_name}', () => {{",
            "  test.beforeEach(async ({ page }) => {",
            "    await page.goto(BASE_URL);",
            "    // TODO: Add application launch / prerequisite steps",
            "  });",
            "",
            "  test.afterEach(async ({ page }) => {",
            "    // TODO: Add close / cleanup steps",
            "  });",
            "",
        ]

        for tc in test_cases:
            tc_id = tc.get('id', 'unknown')
            title = tc.get('title', '')
            scenario = title.split('/')[-1].strip() if '/' in title else title
            steps = tc.get('steps', [])

            lines.append(f"  test('{tc_id}: {scenario}', async ({{ page }}) => {{")

            for step in steps:
                action = step.get('action', '')
                expected = step.get('expected', '')

                # Skip prereq/close steps (handled in hooks)
                action_lower = action.lower()
                if 'pre-req' in action_lower or 'close the' in action_lower:
                    continue
                if 'launch the' in action_lower:
                    continue

                lines.append(f"    // Action: {action}")
                if expected:
                    lines.append(f"    // Expected: {expected}")
                lines.append("    // TODO: Implement step")
                lines.append("")

            lines.append("  });")
            lines.append("")

        lines.append("});")
        return '\n'.join(lines)


# --- Grounding analysis --------------------------------------------------------

# Selector call shapes our system prompt constrains the LLM to. Regex (not a TS
# AST) is sufficient and pragmatic — no Node tooling in the repo. Chained/templated
# selectors are accepted as known false-negative noise in the coverage metric.
_RE_GET_BY_ROLE_NAMED = re.compile(r"getByRole\(\s*['\"](\w+)['\"]\s*,\s*\{\s*name:\s*['\"]([^'\"]+)['\"]")
_RE_GET_BY_ROLE_BARE = re.compile(r"getByRole\(\s*['\"](\w+)['\"]\s*\)")
_RE_GET_BY_TEXT = re.compile(r"getBy(?:Text|Label)\(\s*['\"]([^'\"]+)['\"]")
_RE_GET_BY_PLACEHOLDER = re.compile(r"getByPlaceholder\(\s*['\"]([^'\"]+)['\"]")
_RE_GET_BY_TESTID = re.compile(r"getByTestId\(\s*['\"]([^'\"]+)['\"]")


def analyze_grounding(script: str, inventory) -> Dict:
    """
    Parse selectors out of generated TypeScript and check them against the
    inventory of real elements.

    Returns {total, grounded, coverage, ungrounded[]}.
    """
    role_pairs = inventory.name_role_pairs()       # {(role, name_lower)}
    names = inventory.accessible_names()           # {name_lower / text_lower}
    known_roles = {r for r, _ in role_pairs}

    total = 0
    grounded = 0
    ungrounded: List[str] = []

    def mark(ok: bool, label: str):
        nonlocal total, grounded
        total += 1
        if ok:
            grounded += 1
        else:
            ungrounded.append(label)

    for role, name in _RE_GET_BY_ROLE_NAMED.findall(script):
        ok = (role.lower(), name.strip().lower()) in role_pairs
        mark(ok, f"getByRole('{role}', {{ name: '{name}' }})")

    for role in _RE_GET_BY_ROLE_BARE.findall(script):
        # bare role (no name) — count as grounded if that role exists at all
        mark(role.lower() in known_roles, f"getByRole('{role}')")

    for text in _RE_GET_BY_TEXT.findall(script):
        mark(text.strip().lower() in names, f"getByText/Label('{text}')")

    for ph in _RE_GET_BY_PLACEHOLDER.findall(script):
        mark(ph.strip().lower() in names, f"getByPlaceholder('{ph}')")

    for tid in _RE_GET_BY_TESTID.findall(script):
        testids = {e.attributes.get("data-testid", "").lower() for e in inventory.elements}
        mark(tid.strip().lower() in testids, f"getByTestId('{tid}')")

    coverage = (grounded / total) if total else 0.0
    return {"total": total, "grounded": grounded, "coverage": coverage, "ungrounded": ungrounded}
