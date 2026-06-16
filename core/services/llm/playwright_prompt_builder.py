"""
Playwright Script Prompt Builder

Builds system + user prompts for LLM-based conversion of test cases
to Playwright TypeScript test scripts.
"""
import json
from typing import List, Dict, Optional


class PlaywrightPromptBuilder:
    """Builds system + user prompts for Playwright script generation."""

    def __init__(self, app_name: str, app_type: str, story_id: str, feature_name: str,
                 element_inventory=None):
        self.app_name = app_name
        self.app_type = app_type
        self.story_id = story_id
        self.feature_name = feature_name
        # Optional ElementInventory (core.domain.ui_element) of REAL observed
        # selectors. When present, the LLM is grounded to these instead of guessing.
        self.element_inventory = element_inventory

    @classmethod
    def from_project_config(cls, config, story_id: str, feature_name: str,
                            element_inventory=None) -> 'PlaywrightPromptBuilder':
        return cls(
            app_name=config.application.name,
            app_type=config.application.app_type,
            story_id=story_id,
            feature_name=feature_name,
            element_inventory=element_inventory,
        )

    def build_system_prompt(self) -> str:
        """System prompt with Playwright best practices."""
        grounded = self.element_inventory is not None and bool(getattr(self.element_inventory, "elements", None))

        if grounded:
            selector_strategy = """## SELECTOR STRATEGY (GROUNDED)
A list of the application's REAL, observed UI elements and their exact Playwright
locators is provided in the user message under "## AVAILABLE UI ELEMENTS".
- Use ONLY selectors from that list. Copy the locator string verbatim.
- Choose the element whose role + accessible name best matches the test step.
- If NO listed element fits a step, do NOT invent a selector. Emit a comment
  `// UNGROUNDED: <what was needed>` and skip the action (do not guess a locator).
- Never emit `// TODO: Update selector` — selectors are known and grounded."""
        else:
            selector_strategy = """## SELECTOR STRATEGY (Priority Order)
1. `getByRole('button', { name: '...' })` for buttons
2. `getByRole('menuitem', { name: '...' })` for menu items
3. `getByRole('checkbox', { name: '...' })` for toggles/checkboxes
4. `getByLabel('...')` for form inputs
5. `getByText('...')` for text elements
6. `getByPlaceholder('...')` for placeholder-based inputs
7. `page.locator('[data-testid="..."]')` as last resort
- Add `// TODO: Update selector` comment where the exact selector is uncertain"""

        return """You are an expert test automation engineer who converts manual QA test cases into Playwright TypeScript test scripts.

## OUTPUT FORMAT
Return ONLY valid TypeScript code for a Playwright .spec.ts file. No markdown fences. No commentary outside code comments.

## PLAYWRIGHT BEST PRACTICES
1. Use `import { test, expect } from '@playwright/test';`
2. Use `test.describe()` to group related tests
3. Each test case becomes one `test()` block
4. Use `page` fixture (not `browser.newPage()`)
5. Use `await` for all Playwright actions
6. Use meaningful selectors: prefer `getByRole()`, `getByText()`, `getByLabel()` over CSS
7. Use `expect()` assertions for expected results
8. Add `test.beforeEach()` for common setup (prereq + launch steps)
9. Add `test.afterEach()` for common teardown (close steps)
10. Each test function name must include the test case ID for traceability

## ASSERTION PATTERNS
- Visibility: `await expect(page.getByText('...')).toBeVisible()`
- Text content: `await expect(page.locator('...')).toHaveText('...')`
- Enabled state: `await expect(page.getByRole('button', { name: '...' })).toBeEnabled()`
- Count: `await expect(page.locator('...')).toHaveCount(N)`
- Not visible: `await expect(page.getByText('...')).not.toBeVisible()`

## STEP CONVERSION RULES
- "Pre-req" steps -> skip (handled in beforeEach)
- "Launch" steps -> skip (handled in beforeEach)
- "Close" steps -> skip (handled in afterEach)
- "Navigate to X Menu" -> `await page.getByRole('menuitem', { name: 'X' }).click()`
- "Click button Y" -> `await page.getByRole('button', { name: 'Y' }).click()`
- "Verify X is visible" -> `await expect(page.getByText('X')).toBeVisible()`
- "Enter value Z" -> `await page.getByLabel('...').fill('Z')`
- Steps with empty expected -> action-only, no assertion

""" + selector_strategy + """

## IMPORTANT
- Generate COMPILABLE TypeScript. Every `await` must be inside an `async` function.
- Include `// Story: {story_id}` comment at the top for traceability.
- Do NOT invent page URLs. Use placeholder `const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';`
"""

    def build_user_prompt(self, test_cases: List[Dict]) -> str:
        """User prompt with test cases to convert."""
        tc_json = json.dumps(test_cases, indent=2)

        grounded = self.element_inventory is not None and bool(getattr(self.element_inventory, "elements", None))
        inventory_block = ""
        selector_requirement = "6. Add `// TODO: Update selector` comments where the exact selector is uncertain"
        if grounded:
            block = self.element_inventory.to_prompt_block()
            if block:
                inventory_block = "\n" + block + "\n"
                selector_requirement = (
                    "6. Use ONLY selectors from the AVAILABLE UI ELEMENTS list above. "
                    "If no listed element fits a step, emit `// UNGROUNDED: <need>` instead of guessing"
                )

        return f"""Convert these test cases into a Playwright TypeScript .spec.ts file.

## CONTEXT
- Application: {self.app_name} ({self.app_type})
- Story: {self.story_id} - {self.feature_name}
- Test cases to convert: {len(test_cases)}
{inventory_block}
## TEST CASES
{tc_json}

## REQUIREMENTS
1. Group all tests under `test.describe('{self.story_id}: {self.feature_name}', ...)`
2. Extract common PRE-REQ and CLOSE steps into `beforeEach` / `afterEach`
3. Each test() must include the test case ID: `test('{self.story_id}-XXX: scenario', ...)`
4. Convert every action step to a Playwright command
5. Convert every non-empty expected result to an `expect()` assertion
{selector_requirement}
7. Skip accessibility test cases (those with "Accessibility" in the title)

Return ONLY the TypeScript code."""
