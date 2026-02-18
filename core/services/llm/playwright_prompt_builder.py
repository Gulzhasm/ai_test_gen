"""
Playwright Script Prompt Builder

Builds system + user prompts for LLM-based conversion of test cases
to Playwright TypeScript test scripts.
"""
import json
from typing import List, Dict


class PlaywrightPromptBuilder:
    """Builds system + user prompts for Playwright script generation."""

    def __init__(self, app_name: str, app_type: str, story_id: str, feature_name: str):
        self.app_name = app_name
        self.app_type = app_type
        self.story_id = story_id
        self.feature_name = feature_name

    @classmethod
    def from_project_config(cls, config, story_id: str, feature_name: str) -> 'PlaywrightPromptBuilder':
        return cls(
            app_name=config.application.name,
            app_type=config.application.app_type,
            story_id=story_id,
            feature_name=feature_name
        )

    def build_system_prompt(self) -> str:
        """System prompt with Playwright best practices."""
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

## SELECTOR STRATEGY (Priority Order)
1. `getByRole('button', { name: '...' })` for buttons
2. `getByRole('menuitem', { name: '...' })` for menu items
3. `getByRole('checkbox', { name: '...' })` for toggles/checkboxes
4. `getByLabel('...')` for form inputs
5. `getByText('...')` for text elements
6. `getByPlaceholder('...')` for placeholder-based inputs
7. `page.locator('[data-testid="..."]')` as last resort
- Add `// TODO: Update selector` comment where the exact selector is uncertain

## IMPORTANT
- Generate COMPILABLE TypeScript. Every `await` must be inside an `async` function.
- Include `// Story: {story_id}` comment at the top for traceability.
- Do NOT invent page URLs. Use placeholder `const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';`
"""

    def build_user_prompt(self, test_cases: List[Dict]) -> str:
        """User prompt with test cases to convert."""
        tc_json = json.dumps(test_cases, indent=2)
        return f"""Convert these test cases into a Playwright TypeScript .spec.ts file.

## CONTEXT
- Application: {self.app_name} ({self.app_type})
- Story: {self.story_id} - {self.feature_name}
- Test cases to convert: {len(test_cases)}

## TEST CASES
{tc_json}

## REQUIREMENTS
1. Group all tests under `test.describe('{self.story_id}: {self.feature_name}', ...)`
2. Extract common PRE-REQ and CLOSE steps into `beforeEach` / `afterEach`
3. Each test() must include the test case ID: `test('{self.story_id}-XXX: scenario', ...)`
4. Convert every action step to a Playwright command
5. Convert every non-empty expected result to an `expect()` assertion
6. Add `// TODO: Update selector` comments where the exact selector is uncertain
7. Skip accessibility test cases (those with "Accessibility" in the title)

Return ONLY the TypeScript code."""
