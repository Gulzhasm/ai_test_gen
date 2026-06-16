"""
UIElement and ElementInventory: structured representation of a web app's UI.

An ElementInventory is captured by crawling a running application (see
infrastructure/ui/playwright_extractor.py) and is consumed by the Playwright
script generator to GROUND selectors in real, observed elements instead of
guessing them.

The schema deliberately captures multi-modal features (textual / structural /
attribute / layout) described in the dissertation's self-healing locator design
(§3.3.1). Embeddings are NOT computed here — they are deferred to the later
self-healing increment, which consumes this same inventory as its baseline store.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
import hashlib
import json


# Stability tiers for a recommended selector (used for ranking + later ML labels).
STABILITY_HIGH = "high"      # role + accessible name, unique on page
STABILITY_MEDIUM = "medium"  # text / label based, unique
STABILITY_LOW = "low"        # nth-match / structural only, ambiguous


@dataclass
class BoundingBox:
    """Layout feature: element geometry in CSS pixels (from locator.bounding_box())."""
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0


@dataclass
class UIElement:
    """
    A single selectable UI element observed in the running application.

    Identity is captured by `element_id`, a stable hash over the element's role,
    accessible name, ARIA ancestor chain, and page context — stable enough to
    address the element across crawls (unlike a raw DOM index path).
    """
    # --- Identity ---
    role: str                                  # ARIA role, e.g. "button", "heading", "columnheader"
    accessible_name: str = ""                  # computed accessible name, e.g. "Scan"
    page_context: str = ""                     # logical page/tab, e.g. "Scanner"

    # --- Textual features ---
    text: str = ""                             # visible text content
    tag: str = ""                              # DOM tag, e.g. "button", "h1", "th"

    # --- Attribute features ---
    attributes: Dict[str, str] = field(default_factory=dict)  # id / class / data-testid / placeholder

    # --- Structural features ---
    role_chain: List[str] = field(default_factory=list)  # ARIA ancestor roles, outermost first
    structural_path: str = ""                  # CSS-ish path, best-effort

    # --- Layout features ---
    bounding_box: Optional[BoundingBox] = None
    viewport: Optional[Dict[str, int]] = None  # {"width": ..., "height": ...}

    # --- Interaction state ---
    disabled: bool = False
    editable: bool = False
    focusable: bool = False
    value: Optional[str] = None

    # --- Usability / disambiguation ---
    is_unique: bool = True                     # does recommended_selector resolve to exactly one node?
    occurrence_index: int = 0                  # index among same-(role, name) elements

    # --- Selectors ---
    recommended_selector: str = ""             # Playwright locator string, e.g. getByRole('button', { name: 'Scan' })
    fallback_selectors: List[str] = field(default_factory=list)
    stability_tier: str = STABILITY_MEDIUM

    # --- Provenance ---
    element_id: str = ""                       # stable hash; auto-filled if empty

    def __post_init__(self):
        if not self.element_id:
            self.element_id = self.compute_id()

    def compute_id(self) -> str:
        """Stable identity hash — addresses this element across crawls."""
        key = "|".join([
            self.role,
            self.accessible_name,
            ">".join(self.role_chain),
            self.page_context,
            str(self.occurrence_index),
        ])
        return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "UIElement":
        bbox = data.get("bounding_box")
        kwargs = {k: v for k, v in data.items() if k != "bounding_box"}
        elem = cls(**kwargs)
        if bbox:
            elem.bounding_box = BoundingBox(**bbox)
        return elem


@dataclass
class ElementInventory:
    """A captured snapshot of an application's selectable UI elements."""
    app_name: str
    base_url: str
    captured_at: str = ""                      # ISO timestamp, stamped by the extractor
    elements: List[UIElement] = field(default_factory=list)

    # --- Serialization ---
    def to_dict(self) -> Dict:
        return {
            "app_name": self.app_name,
            "base_url": self.base_url,
            "captured_at": self.captured_at,
            "elements": [e.to_dict() for e in self.elements],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict) -> "ElementInventory":
        return cls(
            app_name=data.get("app_name", ""),
            base_url=data.get("base_url", ""),
            captured_at=data.get("captured_at", ""),
            elements=[UIElement.from_dict(e) for e in data.get("elements", [])],
        )

    @classmethod
    def from_json(cls, text: str) -> "ElementInventory":
        return cls.from_dict(json.loads(text))

    @classmethod
    def load(cls, path: str) -> "ElementInventory":
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_json(f.read())

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    # --- Prompt rendering ---
    def to_prompt_block(self, page_context: Optional[str] = None, max_elements: int = 60) -> str:
        """
        Render a compact, token-bounded list of REAL selectors for the LLM prompt.

        Filtered to the elements worth grounding against: interactive controls,
        landmarks/headings, and column headers. Repeated table cells are NOT listed
        (they collapse into their column headers). Optionally scoped to one page/tab.
        """
        GROUNDABLE_ROLES = {
            "button", "link", "tab", "menuitem", "checkbox", "radio", "switch",
            "textbox", "combobox", "searchbox", "spinbutton", "slider",
            "heading", "columnheader", "tabpanel", "banner", "navigation",
            "main", "region", "dialog", "alert",
        }

        # Filter
        picked: List[UIElement] = []
        for e in self.elements:
            if page_context and e.page_context and e.page_context != page_context:
                continue
            if e.role not in GROUNDABLE_ROLES:
                continue
            if not e.recommended_selector:
                continue
            picked.append(e)

        # De-duplicate by recommended selector, keep most stable first
        order = {STABILITY_HIGH: 0, STABILITY_MEDIUM: 1, STABILITY_LOW: 2}
        picked.sort(key=lambda e: (order.get(e.stability_tier, 3), e.role, e.accessible_name))
        seen = set()
        unique: List[UIElement] = []
        for e in picked:
            if e.recommended_selector in seen:
                continue
            seen.add(e.recommended_selector)
            unique.append(e)

        if not unique:
            return ""

        lines: List[str] = []
        truncated = unique[:max_elements]
        for e in truncated:
            name = e.accessible_name or e.text or ""
            ctx = f" [{e.page_context}]" if e.page_context else ""
            flags = []
            if e.disabled:
                flags.append("disabled")
            if not e.is_unique:
                flags.append("non-unique")
            flag_str = f" ({', '.join(flags)})" if flags else ""
            label = f' "{name}"' if name else ""
            lines.append(f"- {e.role}{label}{ctx} -> {e.recommended_selector}{flag_str}")

        header = "## AVAILABLE UI ELEMENTS (use ONLY these real selectors)"
        footer = ""
        if len(unique) > max_elements:
            footer = f"\n- ... ({len(unique) - max_elements} more elements omitted)"
        return header + "\n" + "\n".join(lines) + footer

    def selector_set(self) -> set:
        """Set of all known recommended + fallback selectors (for grounding checks)."""
        s = set()
        for e in self.elements:
            if e.recommended_selector:
                s.add(e.recommended_selector)
            for f in e.fallback_selectors:
                s.add(f)
        return s

    def name_role_pairs(self) -> set:
        """Set of (role, normalized accessible_name) tuples for fuzzy grounding checks."""
        return {
            (e.role.lower(), (e.accessible_name or "").strip().lower())
            for e in self.elements
            if e.accessible_name
        }

    def accessible_names(self) -> set:
        """Set of normalized accessible names + visible text (for text/label grounding)."""
        names = set()
        for e in self.elements:
            if e.accessible_name:
                names.add(e.accessible_name.strip().lower())
            if e.text:
                names.add(e.text.strip().lower())
        return names
