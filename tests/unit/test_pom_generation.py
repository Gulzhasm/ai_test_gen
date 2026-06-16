"""
Unit tests for POM (Page Object Model) generation.

Covers the deterministic logic: element bucketing, page-object code generation
(critical: `page.`->`this.page.` rewrite + exact:true preservation), and the
spec method-grounding validator.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.domain.ui_element import UIElement, ElementInventory
from infrastructure.export.pom.element_bucketer import bucket_elements, DASHBOARD
from infrastructure.export.pom.page_object_generator import generate_all, generate_page_object
from infrastructure.export.pom.pom_spec_prompt_builder import analyze_method_grounding


def _el(role, name, ctx, selector):
    e = UIElement(role=role, accessible_name=name, page_context=ctx)
    e.recommended_selector = selector
    return e


def _inventory():
    # App title + tab buttons appear in every context (shared chrome);
    # 'Ticker' columnheader appears in BOTH Scanner and Journal (must NOT be hoisted).
    inv = ElementInventory(app_name="Gap Forecaster", base_url="http://localhost:3000")
    els = []
    for ctx in ("Scanner", "Journal", "Stats"):
        els.append(_el("heading", "Gap Forecaster", ctx, "page.getByRole('heading', { name: 'Gap Forecaster' })"))
        els.append(_el("button", "Scanner", ctx, "page.getByRole('button', { name: 'Scanner' })"))
        els.append(_el("button", "Journal", ctx, "page.getByRole('button', { name: 'Journal' })"))
        els.append(_el("button", "Stats", ctx, "page.getByRole('button', { name: 'Stats' })"))
    els.append(_el("button", "Scan", "Scanner", "page.getByRole('button', { name: 'Scan', exact: true })"))
    els.append(_el("columnheader", "Ticker", "Scanner", "page.getByRole('columnheader', { name: 'Ticker' })"))
    els.append(_el("columnheader", "Ticker", "Journal", "page.getByRole('columnheader', { name: 'Ticker' })"))
    els.append(_el("columnheader", "Date", "Journal", "page.getByRole('columnheader', { name: 'Date' })"))
    inv.elements = els
    return inv


class TestBucketing:
    def test_shared_chrome_goes_to_dashboard(self):
        buckets = bucket_elements(_inventory(), tab_names=["Scanner", "Journal", "Stats"], app_name="Gap Forecaster")
        names = [b.name for b in buckets]
        assert names[0] == DASHBOARD
        dash = buckets[0]
        dash_names = {(e.role, e.accessible_name) for e in dash.elements}
        assert ("heading", "Gap Forecaster") in dash_names
        assert ("button", "Scanner") in dash_names
        assert dash.nav_targets == ["Scanner", "Journal", "Stats"]

    def test_colliding_columnheader_not_hoisted(self):
        buckets = bucket_elements(_inventory(), tab_names=["Scanner", "Journal", "Stats"])
        by_name = {b.name: b for b in buckets}
        # Ticker must stay in BOTH Scanner and Journal, not be promoted to Dashboard
        assert ("columnheader", "Ticker") not in {(e.role, e.accessible_name) for e in by_name[DASHBOARD].elements}
        assert any(e.accessible_name == "Ticker" for e in by_name["Scanner"].elements)
        assert any(e.accessible_name == "Ticker" for e in by_name["Journal"].elements)

    def test_scan_button_stays_in_scanner(self):
        buckets = bucket_elements(_inventory(), tab_names=["Scanner", "Journal", "Stats"])
        scanner = next(b for b in buckets if b.name == "Scanner")
        assert any(e.accessible_name == "Scan" for e in scanner.elements)


class TestPageObjectCode:
    def test_page_prefix_rewritten_to_this_page(self):
        buckets = bucket_elements(_inventory(), tab_names=["Scanner", "Journal", "Stats"])
        scanner = generate_page_object(next(b for b in buckets if b.name == "Scanner"))
        assert "this.page.getByRole(" in scanner.code
        assert "= page.getByRole(" not in scanner.code  # bare page. must be rewritten

    def test_exact_true_preserved(self):
        buckets = bucket_elements(_inventory(), tab_names=["Scanner", "Journal", "Stats"])
        scanner = generate_page_object(next(b for b in buckets if b.name == "Scanner"))
        assert "{ name: 'Scan', exact: true }" in scanner.code

    def test_generated_banner_and_class_name(self):
        buckets = bucket_elements(_inventory(), tab_names=["Scanner", "Journal", "Stats"])
        dash = generate_page_object(buckets[0])
        assert dash.code.startswith("// @generated")
        assert "export class DashboardPage extends BasePage" in dash.code
        assert "async openScanner(): Promise<void>" in dash.code
        assert "async expectLoaded(): Promise<void>" in dash.code

    def test_clickscan_action_generated(self):
        buckets = bucket_elements(_inventory(), tab_names=["Scanner", "Journal", "Stats"])
        scanner = generate_page_object(next(b for b in buckets if b.name == "Scanner"))
        assert "async clickScan(): Promise<void>" in scanner.code

    def test_no_landmark_locators(self):
        # navigation/main landmarks must not become page-object members
        buckets = bucket_elements(_inventory(), tab_names=["Scanner", "Journal", "Stats"])
        for g in generate_all(buckets):
            assert "Nav: Locator" not in g.code


class TestMethodGrounding:
    def test_valid_spec_is_fully_grounded(self):
        buckets = bucket_elements(_inventory(), tab_names=["Scanner", "Journal", "Stats"])
        apis = [g.api for g in generate_all(buckets)]
        spec = """
        import { test, expect } from '../fixtures/test-fixtures';
        test('AC1', async ({ dashboard, scanner }) => {
          await dashboard.goto();
          await scanner.clickScan();
          await expect(scanner.tickerColumn).toBeVisible();
        });
        """
        res = analyze_method_grounding(spec, apis)
        assert res["raw_selectors"] == 0
        assert res["total"] >= 3
        assert res["grounded"] == res["total"]
        assert res["ungrounded"] == []

    def test_raw_selector_is_flagged(self):
        buckets = bucket_elements(_inventory(), tab_names=["Scanner", "Journal", "Stats"])
        apis = [g.api for g in generate_all(buckets)]
        spec = "await page.getByRole('button', { name: 'Scan' }).click();"
        assert analyze_method_grounding(spec, apis)["raw_selectors"] == 1

    def test_unknown_method_is_ungrounded(self):
        buckets = bucket_elements(_inventory(), tab_names=["Scanner", "Journal", "Stats"])
        apis = [g.api for g in generate_all(buckets)]
        spec = "await scanner.clickNonexistentThing();"
        res = analyze_method_grounding(spec, apis)
        assert "scanner.clickNonexistentThing" in res["ungrounded"]
