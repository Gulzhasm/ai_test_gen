"""
Bucket inventory elements into logical pages for the Page Object Model.

Cross-cutting elements (those observed in 2+ page states — e.g. the app title and
the tab-navigation buttons) are hoisted into a shared "Dashboard" page. Everything
else stays in its own page-state bucket (Scanner / Journal / Stats).

This is the riskiest mapping in POM generation, so it is isolated here and unit-tested.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from core.domain.ui_element import UIElement, ElementInventory

DASHBOARD = "Dashboard"

# Only these roles are hoisted to the shared Dashboard page when they appear in
# multiple page contexts. Table cells/columnheaders are intentionally excluded:
# a "Ticker" column existing in both the Scanner and Journal tables is a genuine
# per-tab element, not shared chrome, and must stay in each tab's page object.
HOISTABLE_ROLES = {"button", "link", "tab", "menuitem", "heading", "navigation", "banner"}


def _norm(s: str) -> str:
    return (s or "").strip().lower()


@dataclass
class PageBucket:
    """Elements that belong to one page object."""
    name: str                                      # e.g. "Dashboard", "Scanner"
    elements: List[UIElement] = field(default_factory=list)
    nav_targets: List[str] = field(default_factory=list)  # accessible names of tab buttons (Dashboard only)


def bucket_elements(
    inventory: ElementInventory,
    tab_names: Optional[List[str]] = None,
    app_name: str = "",
) -> List[PageBucket]:
    """
    Group inventory elements into ordered page buckets (Dashboard first, then tabs).

    Args:
        inventory: the captured element inventory.
        tab_names: page-state names in display order (e.g. ["Scanner","Journal","Stats"]).
        app_name: application name (used only as a safety-net hint).

    Returns:
        Ordered list of PageBucket. Dashboard holds cross-cutting elements; each tab
        bucket holds elements unique to that page_context.
    """
    tab_names = tab_names or []

    # Map (role, normalized name) -> set of contexts it appears in, plus a representative element.
    contexts_by_key: Dict[tuple, set] = {}
    rep_by_key: Dict[tuple, UIElement] = {}
    for e in inventory.elements:
        key = (e.role, _norm(e.accessible_name))
        contexts_by_key.setdefault(key, set()).add(e.page_context or "")
        rep_by_key.setdefault(key, e)  # first occurrence is the representative

    # Shared keys appear in 2+ page contexts AND are "chrome" roles → Dashboard.
    shared_keys = {
        k for k, ctxs in contexts_by_key.items()
        if len(ctxs) >= 2 and rep_by_key[k].role in HOISTABLE_ROLES
    }

    # Dashboard bucket: one representative per shared key.
    dashboard = PageBucket(name=DASHBOARD)
    tab_name_set = {_norm(t) for t in tab_names}
    for key in shared_keys:
        rep = rep_by_key[key]
        dashboard.elements.append(rep)
        # Tab-nav buttons: shared buttons whose name matches a configured page-state name.
        if rep.role == "button" and _norm(rep.accessible_name) in tab_name_set:
            dashboard.nav_targets.append(rep.accessible_name)

    # Stable order for Dashboard: nav buttons first (in tab order), then others.
    nav_order = {_norm(t): i for i, t in enumerate(tab_names)}
    dashboard.elements.sort(key=lambda e: (
        0 if (e.role == "button" and _norm(e.accessible_name) in tab_name_set) else 1,
        nav_order.get(_norm(e.accessible_name), 99),
        e.role,
        _norm(e.accessible_name),
    ))
    dashboard.nav_targets.sort(key=lambda n: nav_order.get(_norm(n), 99))

    # Per-tab buckets: elements unique to that context (not promoted to Dashboard).
    # Order tabs as configured; fall back to first-seen order for any extras.
    seen_order: List[str] = []
    for e in inventory.elements:
        ctx = e.page_context or ""
        if ctx and ctx not in seen_order:
            seen_order.append(ctx)
    ordered_tabs = [t for t in tab_names if t in seen_order] + [t for t in seen_order if t not in tab_names]

    buckets: List[PageBucket] = [dashboard]
    for tab in ordered_tabs:
        b = PageBucket(name=tab)
        for e in inventory.elements:
            if (e.page_context or "") != tab:
                continue
            if (e.role, _norm(e.accessible_name)) in shared_keys:
                continue
            b.elements.append(e)
        if b.elements:
            buckets.append(b)

    return buckets
