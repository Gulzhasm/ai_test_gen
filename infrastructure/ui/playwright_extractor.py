"""
PlaywrightExtractor: capture a running app's UI element inventory via a live crawl.

For each PageState it mocks the backend at the network layer (so data-driven DOM
renders deterministically without the real backend), navigates by scripted role
clicks, waits for readiness, then walks the DOM to build a structured
ElementInventory. The inventory is later fed to the Playwright script generator
to ground selectors in real, observed elements.

Requires the `playwright` package (`pip install playwright && playwright install chromium`).
"""
import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Optional

from core.domain.ui_element import (
    UIElement,
    ElementInventory,
    BoundingBox,
    STABILITY_HIGH,
    STABILITY_MEDIUM,
    STABILITY_LOW,
)
from core.interfaces.element_extractor import (
    IElementExtractor,
    PageState,
    NavStep,
    ApiMock,
)


# Roles worth capturing for selector grounding (interactive + landmarks + headers).
GROUNDABLE_ROLES = {
    "button", "link", "tab", "menuitem", "checkbox", "radio", "switch",
    "textbox", "combobox", "searchbox", "spinbutton", "slider",
    "heading", "columnheader", "tabpanel", "banner", "navigation",
    "main", "region", "dialog", "alert",
}

# JS walked in the page to extract a pragmatic role + accessible name + features
# for every candidate element. Role/name computation is an approximation of the
# ARIA algorithm sufficient for apps that name elements by text (no aria-label).
_EXTRACT_JS = r"""
() => {
  const CANDIDATE = 'button,a[href],[role],input,select,textarea,h1,h2,h3,h4,h5,h6,th,nav,main';

  function inferRole(el) {
    const explicit = el.getAttribute('role');
    if (explicit) return explicit.trim().toLowerCase();
    const tag = el.tagName.toLowerCase();
    if (tag === 'button') return 'button';
    if (tag === 'a' && el.hasAttribute('href')) return 'link';
    if (tag === 'nav') return 'navigation';
    if (tag === 'main') return 'main';
    if (tag === 'th') return 'columnheader';
    if (/^h[1-6]$/.test(tag)) return 'heading';
    if (tag === 'select') return 'combobox';
    if (tag === 'textarea') return 'textbox';
    if (tag === 'input') {
      const t = (el.getAttribute('type') || 'text').toLowerCase();
      if (t === 'checkbox') return 'checkbox';
      if (t === 'radio') return 'radio';
      if (t === 'search') return 'searchbox';
      if (t === 'number') return 'spinbutton';
      if (t === 'range') return 'slider';
      if (['button', 'submit', 'reset'].includes(t)) return 'button';
      return 'textbox';
    }
    return '';
  }

  function accName(el, role) {
    const al = el.getAttribute('aria-label');
    if (al && al.trim()) return al.trim();
    const lb = el.getAttribute('aria-labelledby');
    if (lb) {
      const ref = document.getElementById(lb);
      if (ref && ref.textContent.trim()) return ref.textContent.trim();
    }
    if (role === 'textbox' || role === 'searchbox' || role === 'combobox' || role === 'spinbutton') {
      const ph = el.getAttribute('placeholder');
      if (ph && ph.trim()) return ph.trim();
    }
    const txt = (el.textContent || '').replace(/\s+/g, ' ').trim();
    if (txt) return txt;
    const ph = el.getAttribute('placeholder');
    if (ph && ph.trim()) return ph.trim();
    const alt = el.getAttribute('alt');
    if (alt && alt.trim()) return alt.trim();
    return '';
  }

  function roleChain(el) {
    const chain = [];
    let p = el.parentElement;
    while (p && p !== document.body) {
      const r = inferRole(p);
      if (r) chain.unshift(r);
      p = p.parentElement;
    }
    return chain.slice(-4); // nearest 4 landmark/role ancestors
  }

  function cssPath(el) {
    const parts = [];
    let node = el;
    let depth = 0;
    while (node && node.nodeType === 1 && depth < 5) {
      let part = node.tagName.toLowerCase();
      if (node.id) { part += '#' + node.id; parts.unshift(part); break; }
      parts.unshift(part);
      node = node.parentElement;
      depth++;
    }
    return parts.join(' > ');
  }

  const out = [];
  const els = Array.from(document.querySelectorAll(CANDIDATE));
  for (const el of els) {
    const role = inferRole(el);
    if (!role) continue;
    const rect = el.getBoundingClientRect();
    // skip elements with no rendered box (display:none etc.)
    if (rect.width === 0 && rect.height === 0) continue;
    const name = accName(el, role);
    const tag = el.tagName.toLowerCase();
    const attrs = {};
    for (const a of ['id', 'class', 'data-testid', 'placeholder', 'type', 'name', 'aria-label']) {
      const v = el.getAttribute(a);
      if (v) attrs[a] = v;
    }
    const editable = tag === 'input' || tag === 'textarea' || tag === 'select' || el.isContentEditable;
    out.push({
      role, name, tag, attrs,
      text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 120),
      disabled: !!(el.disabled || el.getAttribute('aria-disabled') === 'true'),
      editable,
      focusable: el.tabIndex >= 0 || ['a', 'button', 'input', 'select', 'textarea'].includes(tag),
      value: editable && 'value' in el ? (el.value || '') : null,
      role_chain: roleChain(el),
      structural_path: cssPath(el),
      bbox: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
    });
  }
  return { elements: out, viewport: { width: window.innerWidth, height: window.innerHeight } };
}
"""


def _esc(s: str) -> str:
    """Escape single quotes for embedding in a Playwright JS selector string."""
    return s.replace("\\", "\\\\").replace("'", "\\'")


def _build_selector(role: str, name: str, attrs: Dict[str, str], exact: bool = False) -> (str, List[str]):
    """Return (recommended_selector, fallback_selectors) for an element.

    `exact=True` emits `{ name: '...', exact: true }` so the selector is not
    ambiguous under Playwright's default substring name matching (e.g. so that
    name 'Scan' does not also match the 'Scanner' tab button).
    """
    fallbacks: List[str] = []

    testid = attrs.get("data-testid")
    if testid:
        fallbacks.append(f"page.getByTestId('{_esc(testid)}')")

    placeholder = attrs.get("placeholder")
    name_opt = f"name: '{_esc(name)}'" + (", exact: true" if exact else "")

    if name:
        if role in ("textbox", "searchbox", "combobox", "spinbutton") and placeholder:
            recommended = f"page.getByPlaceholder('{_esc(placeholder)}')"
            fallbacks.append(f"page.getByRole('{role}', {{ {name_opt} }})")
        else:
            recommended = f"page.getByRole('{role}', {{ {name_opt} }})"
            fallbacks.append(f"page.getByText('{_esc(name)}', {{ exact: true }})")
    elif placeholder:
        recommended = f"page.getByPlaceholder('{_esc(placeholder)}')"
    elif testid:
        recommended = fallbacks.pop(0)
    else:
        recommended = ""

    return recommended, fallbacks


class PlaywrightExtractor(IElementExtractor):
    """Live-DOM element extractor backed by Playwright (sync API)."""

    def __init__(self, headless: bool = True, viewport_width: int = 1280, viewport_height: int = 900):
        self._headless = headless
        self._viewport = {"width": viewport_width, "height": viewport_height}

    def extract(
        self,
        base_url: str,
        page_states: List[PageState],
        api_mocks: Optional[List[ApiMock]] = None,
    ) -> ElementInventory:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError(
                "playwright is not installed. Run: pip install playwright && playwright install chromium"
            ) from e

        api_mocks = api_mocks or []
        # Pre-load mock bodies so the route handler is cheap and self-contained.
        mock_bodies = []
        for m in api_mocks:
            with open(m.body_file, "r", encoding="utf-8") as f:
                mock_bodies.append((m.url_glob, f.read(), m.status))

        inventory = ElementInventory(
            app_name="",
            base_url=base_url,
            captured_at=datetime.now(timezone.utc).isoformat(),
        )

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self._headless)
            context = browser.new_context(viewport=self._viewport)
            page = context.new_page()

            # Register API mocks once — they persist across navigations.
            # NOTE: Playwright calls the handler as handler(route, request); keep the
            # captured body/status keyword-only so the positional request can't clobber them.
            for url_glob, body, status in mock_bodies:
                def _handler(route, request=None, *, _body=body, _status=status):
                    route.fulfill(status=_status, content_type="application/json", body=_body)
                page.route(url_glob, _handler)

            all_elements: List[UIElement] = []
            for state in page_states:
                print(f"  Crawling page state: {state.name}")
                self._navigate(page, base_url, state)
                raw = page.evaluate(_EXTRACT_JS)
                all_elements.extend(
                    self._build_elements(raw, page_context=state.name)
                )

            browser.close()

        inventory.elements = self._dedupe(all_elements)
        return inventory

    def _navigate(self, page, base_url: str, state: PageState) -> None:
        for step in state.steps:
            if step.kind == "goto":
                url = step.target if step.target.startswith("http") else base_url.rstrip("/") + "/" + step.target.lstrip("/")
                if step.target in ("", "/"):
                    url = base_url
                page.goto(url, wait_until="domcontentloaded")
            elif step.kind == "click_role":
                page.get_by_role(step.role, name=step.name).first.click()
            else:
                raise ValueError(f"Unknown nav step kind: {step.kind}")
        if state.ready_selector:
            try:
                page.wait_for_selector(state.ready_selector, timeout=8000)
            except Exception:
                print(f"    Warning: ready_selector '{state.ready_selector}' not found for '{state.name}'")
        # settle async renders
        page.wait_for_timeout(400)

    def _build_elements(self, raw: Dict, page_context: str) -> List[UIElement]:
        viewport = raw.get("viewport")
        raw_els = raw.get("elements", [])

        # Count (role, name) occurrences to determine uniqueness on this page state.
        counts: Dict[tuple, int] = {}
        names_by_role: Dict[str, set] = {}
        for r in raw_els:
            key = (r["role"], r["name"])
            counts[key] = counts.get(key, 0) + 1
            names_by_role.setdefault(r["role"], set()).add(r["name"])

        seen_index: Dict[tuple, int] = {}
        built: List[UIElement] = []
        for r in raw_els:
            role = r["role"]
            if role not in GROUNDABLE_ROLES:
                continue
            name = r["name"]
            key = (role, name)
            occ = seen_index.get(key, 0)
            seen_index[key] = occ + 1
            is_unique = counts.get(key, 1) == 1

            # Playwright matches `name` as a substring by default. If this name is a
            # substring of another same-role element's name, the selector is ambiguous,
            # so emit exact matching (e.g. 'Scan' vs the 'Scanner' tab button).
            exact = bool(name) and any(
                other != name and name in other for other in names_by_role.get(role, ())
            )
            recommended, fallbacks = _build_selector(role, name, r["attrs"], exact=exact)
            if not recommended:
                continue

            stability = self._stability(role, name, is_unique, r["attrs"])

            bbox = r.get("bbox") or {}
            built.append(UIElement(
                role=role,
                accessible_name=name,
                page_context=page_context,
                text=r.get("text", ""),
                tag=r.get("tag", ""),
                attributes=r.get("attrs", {}),
                role_chain=r.get("role_chain", []),
                structural_path=r.get("structural_path", ""),
                bounding_box=BoundingBox(
                    x=bbox.get("x", 0.0), y=bbox.get("y", 0.0),
                    width=bbox.get("width", 0.0), height=bbox.get("height", 0.0),
                ),
                viewport=viewport,
                disabled=r.get("disabled", False),
                editable=r.get("editable", False),
                focusable=r.get("focusable", False),
                value=r.get("value"),
                is_unique=is_unique,
                occurrence_index=occ,
                recommended_selector=recommended,
                fallback_selectors=fallbacks,
                stability_tier=stability,
            ))
        return built

    @staticmethod
    def _stability(role: str, name: str, is_unique: bool, attrs: Dict[str, str]) -> str:
        if attrs.get("data-testid"):
            return STABILITY_HIGH
        if not is_unique:
            return STABILITY_LOW
        if name and role in ("button", "link", "tab", "menuitem", "checkbox",
                             "radio", "switch", "heading", "columnheader"):
            return STABILITY_HIGH
        if name or attrs.get("placeholder"):
            return STABILITY_MEDIUM
        return STABILITY_LOW

    @staticmethod
    def _dedupe(elements: List[UIElement]) -> List[UIElement]:
        """Drop exact duplicate elements (same id) captured across page states."""
        seen = set()
        out: List[UIElement] = []
        for e in elements:
            if e.element_id in seen:
                continue
            seen.add(e.element_id)
            out.append(e)
        return out
