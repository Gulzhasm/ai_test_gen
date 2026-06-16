"""
Build the LLM prompt for POM specs and validate the result.

The prompt exposes the generated page-object API surface (classes -> methods +
locator properties) and forbids raw selectors, so the LLM can only orchestrate
real, grounded page-object members. analyze_method_grounding() then verifies the
generated spec only references members that actually exist and contains no raw
selectors.
"""
import json
import re
from typing import List, Dict

from infrastructure.export.pom.page_object_generator import PageObjectAPI

# Raw-selector calls that must NEVER appear in a POM spec (the LLM bypassed the API).
_RAW_SELECTOR_RE = re.compile(r"\b(?:getByRole|getByText|getByLabel|getByPlaceholder|getByTestId)\s*\(|\.locator\s*\(")
# Member access on a fixture identifier: `scanner.clickScan(` or `scanner.tickerColumn`
_MEMBER_CALL_RE = re.compile(r"\b([a-z]\w*)\.([a-z]\w*)\b")


def _method_name(sig: str) -> str:
    return sig.split("(", 1)[0].strip()


def _api_block(apis: List[PageObjectAPI]) -> str:
    lines = []
    for a in apis:
        lines.append(f"### {a.class_name}  (fixture: `{a.fixture_name}`)")
        if a.actions:
            lines.append("  actions:")
            lines += [f"    - {a.fixture_name}.{sig}" for sig in a.actions]
        if a.assertions:
            lines.append("  assertions:")
            lines += [f"    - {a.fixture_name}.{sig}" for sig in a.assertions]
        if a.locators:
            lines.append("  locators (use inside expect(...)):")
            lines += [f"    - {a.fixture_name}.{loc}: Locator" for loc in a.locators]
        lines.append("")
    return "\n".join(lines)


class PomSpecPromptBuilder:
    def __init__(self, app_name: str, story_id: str, feature_name: str, apis: List[PageObjectAPI]):
        self.app_name = app_name
        self.story_id = story_id
        self.feature_name = feature_name
        self.apis = apis

    def build_system_prompt(self) -> str:
        fixtures = ", ".join(a.fixture_name for a in self.apis) + ", page"
        return f"""You are an expert test automation engineer writing Playwright tests in a Page Object Model project.

## OUTPUT FORMAT
Return ONLY valid TypeScript for a Playwright .spec.ts file. No markdown fences. No prose outside code comments.

## HOW THIS PROJECT WORKS
- Import the test runner: `import {{ test, expect }} from '../fixtures/test-fixtures';`
- Page objects are injected as fixtures: `async ({{ {fixtures} }}) => {{ ... }}`
- Call ONLY the page-object methods listed under "AVAILABLE PAGE OBJECTS".
- You MAY assert on exposed locator properties: `await expect(scanner.tickerColumn).toBeVisible();`
- You MUST NOT write raw selectors (`page.getByRole`, `page.locator`, `getByText`, etc.). The page
  objects own all selectors. If no method/locator fits a step, emit `// UNGROUNDED: <what was needed>`
  and skip that step — never invent a selector.

## STRUCTURE
1. `test.describe('{self.story_id}: {self.feature_name}', () => {{ ... }})`
2. `test.beforeEach(async ({{ dashboard }}) => {{ await dashboard.goto(); await dashboard.expectLoaded(); }})`
3. One `test('{self.story_id}-XXX: scenario', async ({{ ... }}) => {{ ... }})` per test case.
4. Skip accessibility test cases (those with "Accessibility" in the title).
5. Convert each non-empty expected result into an `expect(...)` assertion via a page-object assertion
   method or locator property.
"""

    def build_user_prompt(self, test_cases: List[Dict]) -> str:
        tc_json = json.dumps(test_cases, indent=2)
        return f"""Write a Playwright POM spec for the following test cases.

## CONTEXT
- Application: {self.app_name}
- Story: {self.story_id} - {self.feature_name}
- Test cases: {len(test_cases)}

## AVAILABLE PAGE OBJECTS
{_api_block(self.apis)}
## TEST CASES
{tc_json}

## REQUIREMENTS
1. Import from '../fixtures/test-fixtures'.
2. Group under `test.describe('{self.story_id}: {self.feature_name}', ...)`.
3. `beforeEach`: `await dashboard.goto(); await dashboard.expectLoaded();`
4. Each test() name includes the test case ID.
5. Use ONLY the page-object methods/locators above. No raw selectors. Use `// UNGROUNDED:` when nothing fits.

Return ONLY the TypeScript code."""


def build_known_members(apis: List[PageObjectAPI]) -> Dict[str, set]:
    """Map fixture name -> set of valid member names (methods + locator properties)."""
    known: Dict[str, set] = {}
    for a in apis:
        members = set(a.locators)
        members |= {_method_name(s) for s in a.actions}
        members |= {_method_name(s) for s in a.assertions}
        known[a.fixture_name] = members
    return known


def analyze_method_grounding(spec: str, apis: List[PageObjectAPI]) -> Dict:
    """
    Validate a POM spec references only real page-object members and no raw selectors.

    Returns {total, grounded, coverage, ungrounded[], raw_selectors:int}.
    raw_selectors > 0 is a hard failure (the LLM bypassed the page-object API).
    """
    known = build_known_members(apis)
    fixtures = set(known)

    raw_selectors = len(_RAW_SELECTOR_RE.findall(spec))

    total = 0
    grounded = 0
    ungrounded: List[str] = []
    for fixture, member in _MEMBER_CALL_RE.findall(spec):
        if fixture not in fixtures:
            continue  # not a page-object reference (e.g. page.goto, expect.soft)
        total += 1
        if member in known[fixture]:
            grounded += 1
        else:
            ungrounded.append(f"{fixture}.{member}")

    coverage = (grounded / total) if total else 1.0
    return {
        "total": total,
        "grounded": grounded,
        "coverage": coverage,
        "ungrounded": ungrounded,
        "raw_selectors": raw_selectors,
    }
