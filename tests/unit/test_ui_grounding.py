"""
Unit tests for UI element inventory + Playwright selector grounding.

Covers the pure logic of the grounded-generation increment (no live browser):
- UIElement / ElementInventory model + JSON round-trip + stable IDs
- ElementInventory.to_prompt_block filtering and scoping
- analyze_grounding selector coverage
- PlaywrightPromptBuilder grounded vs ungrounded prompt branching
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.domain.ui_element import UIElement, ElementInventory, STABILITY_HIGH
from core.services.llm.playwright_prompt_builder import PlaywrightPromptBuilder
from infrastructure.export.playwright_generator import analyze_grounding


def _el(role, name, ctx="Scanner", recommended=None):
    e = UIElement(role=role, accessible_name=name, page_context=ctx, stability_tier=STABILITY_HIGH)
    e.recommended_selector = recommended or f"page.getByRole('{role}', {{ name: '{name}' }})"
    return e


def _inventory():
    inv = ElementInventory(app_name="Gap Forecaster", base_url="http://localhost:3000")
    inv.elements = [
        _el("button", "Scan"),
        _el("button", "Scanner"),
        _el("button", "Journal", ctx="Journal"),
        _el("heading", "Gap Forecaster"),
        _el("columnheader", "Ticker"),
    ]
    return inv


class TestUIElementModel:
    def test_stable_id_is_deterministic(self):
        a = _el("button", "Scan")
        b = _el("button", "Scan")
        assert a.element_id == b.element_id
        assert len(a.element_id) == 16

    def test_id_differs_by_role_name_context(self):
        assert _el("button", "Scan").element_id != _el("button", "Scanner").element_id
        assert _el("button", "Scan", ctx="Scanner").element_id != _el("button", "Scan", ctx="Journal").element_id

    def test_json_round_trip_preserves_elements(self):
        inv = _inventory()
        restored = ElementInventory.from_json(inv.to_json())
        assert restored.app_name == inv.app_name
        assert len(restored.elements) == len(inv.elements)
        assert restored.elements[0].element_id == inv.elements[0].element_id


class TestPromptBlock:
    def test_lists_real_selectors(self):
        block = _inventory().to_prompt_block()
        assert "AVAILABLE UI ELEMENTS" in block
        assert "page.getByRole('button', { name: 'Scan' })" in block

    def test_skips_elements_without_recommended_selector(self):
        inv = ElementInventory(app_name="X", base_url="")
        inv.elements = [UIElement(role="button", accessible_name="Nameless")]  # no recommended_selector
        assert inv.to_prompt_block() == ""

    def test_scopes_by_page_context(self):
        block = _inventory().to_prompt_block(page_context="Journal")
        assert "Journal" in block
        assert "Scan" not in block.replace("Scanner", "")  # 'Scan' button excluded


class TestGroundingAnalysis:
    def test_counts_grounded_and_ungrounded(self):
        inv = _inventory()
        script = """
        await page.getByRole('button', { name: 'Scan' }).click();
        await expect(page.getByRole('heading', { name: 'Gap Forecaster' })).toBeVisible();
        await page.getByRole('button', { name: 'DoesNotExist' }).click();
        await expect(page.getByText('Ticker')).toBeVisible();
        """
        res = analyze_grounding(script, inv)
        assert res["total"] == 4
        assert res["grounded"] == 3
        assert abs(res["coverage"] - 0.75) < 1e-6
        assert any("DoesNotExist" in u for u in res["ungrounded"])

    def test_empty_script_has_zero_total(self):
        assert analyze_grounding("// nothing here", _inventory())["total"] == 0


class TestPromptBuilderBranching:
    def test_grounded_prompt_forbids_todo_guessing(self):
        b = PlaywrightPromptBuilder("Gap Forecaster", "web", "123", "Scan", element_inventory=_inventory())
        sp = b.build_system_prompt()
        assert "SELECTOR STRATEGY (GROUNDED)" in sp
        assert "UNGROUNDED" in sp
        up = b.build_user_prompt([{"id": "AC1", "title": "t", "steps": []}])
        assert "AVAILABLE UI ELEMENTS" in up
        assert "Use ONLY selectors" in up

    def test_ungrounded_prompt_keeps_priority_order(self):
        b = PlaywrightPromptBuilder("X", "web", "1", "f")  # no inventory
        assert "Priority Order" in b.build_system_prompt()
