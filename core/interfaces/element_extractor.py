"""
IElementExtractor: contract for capturing a running app's UI element inventory.

Implementations crawl a live application and return an ElementInventory of
selectable elements, used to ground Playwright selector generation in real UI.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from core.domain.ui_element import ElementInventory


@dataclass
class NavStep:
    """A single navigation step within a PageState.

    kind:
      - "goto": navigate to `target` (a URL or path appended to base_url)
      - "click_role": click the element with ARIA `role` and accessible `name`
    """
    kind: str
    target: str = ""        # for goto
    role: str = ""          # for click_role
    name: str = ""          # for click_role


@dataclass
class PageState:
    """A reachable UI state to snapshot.

    Tabs in single-page apps are client-side state (not routes), so a state is
    reached by a scripted sequence of nav steps rather than a URL alone.
    """
    name: str                                          # logical name, e.g. "Scanner"
    steps: List[NavStep] = field(default_factory=list)
    ready_selector: Optional[str] = None               # wait for this before snapshotting


@dataclass
class ApiMock:
    """A backend response to fulfill at the network layer during the crawl.

    `url_glob` is matched against outgoing requests (e.g. "**/api/scan").
    `body_file` is a path to a JSON fixture used as the response body.
    """
    url_glob: str
    body_file: str
    status: int = 200


class IElementExtractor(ABC):
    """Captures an ElementInventory from a running application."""

    @abstractmethod
    def extract(
        self,
        base_url: str,
        page_states: List[PageState],
        api_mocks: Optional[List[ApiMock]] = None,
    ) -> ElementInventory:
        """Crawl the app across the given page states and return its inventory."""
        raise NotImplementedError
