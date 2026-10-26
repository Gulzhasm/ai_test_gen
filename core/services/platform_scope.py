"""
Story-scoped platform selection, shared by every generation layer.

A project lists the platforms it supports (``application.platforms``); a story
needs tests only for the platforms its acceptance criteria talk about. Criteria
rarely use the config's exact names -- they say "iOS", "Apple App Store",
"Google Play", "Microsoft Store" or "each applicable package" -- so matching on
the literal platform name silently dropped whole platforms (story 294626 lost
iPad and Android because its ACs said "Apple/iOS" and "Google Play/Android").

The rule-based generator, prompt builder, LLM corrector, suite creator and the
output quality gate all select platforms through this module, so every layer
agrees on the same set.

Two kinds of alias exist:
- specific ones ("ios", "google play") identify exactly one kind of platform;
- generic form-factor words ("tablet", "mobile") only widen story scope. They
  are ignored when deciding which platform a single test exercises, otherwise
  a test titled "(Android Tablet)" would also count as covering iPad.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence

# Specific aliases keyed by a token of the configured platform name. A platform
# collects every group whose token appears in its lower-cased name, so
# "Chrome (Windows 11)" gets chrome + windows. Project configs can add more via
# ``application.platform_aliases``.
_SPECIFIC_ALIASES: dict[str, tuple[str, ...]] = {
    "windows": ("windows", "microsoft store", "ms store", "msix", "pc"),
    "mac": ("macos", "mac os", "mac app store"),
    "ipad": ("ipad", "ipados", "ios", "apple", "app store", "testflight"),
    "iphone": ("iphone", "ios", "apple", "app store", "testflight"),
    "ios": ("ios", "apple", "app store", "testflight"),
    "android": ("android", "google play", "play store", "apk"),
    "chrome": ("chrome", "chromium"),
    # bare "edge" would match "edge case"
    "edge": ("microsoft edge", "edge browser"),
    "firefox": ("firefox",),
    "safari": ("safari",),
}

# Generic form-factor words and the platform-name tokens that imply them.
_GENERIC_ALIASES: dict[str, tuple[str, ...]] = {
    "tablet": ("tablet", "tablets"),
    "phone": ("phone", "phones", "mobile"),
}
_FORM_FACTOR_TOKENS: dict[str, tuple[str, ...]] = {
    "tablet": ("tablet", "ipad"),
    "phone": ("phone", "iphone"),
}

_ALL_PLATFORMS_RE = re.compile(
    # up to two qualifiers: "all applicable SiteDraft installation packages"
    r"\b(?:all|every|each)\s+(?:of\s+the\s+)?(?:[\w-]+\s+){0,2}"
    r"(?:platforms?|devices?|operating\s+systems?|installation\s+packages?|packages?"
    r"|app(?:lication)?\s+stores?|stores?)\b"
    r"|\bcross[- ]platform\b",
    re.IGNORECASE,
)

_BROWSER_TOKENS = ("chrome", "chromium", "firefox", "safari", "edge", "browser")


def platform_aliases(
    platform: str,
    custom: Mapping[str, Sequence[str]] | None = None,
    include_generic: bool = True,
) -> list[str]:
    """All phrases that refer to ``platform``, longest first."""
    name = platform.lower()
    aliases = {name}
    # "Chrome (Windows 11)" also matches on "chrome" and "windows 11"
    aliases.update(part.strip() for part in re.split(r"[()]", name) if part.strip())
    for token, group in _SPECIFIC_ALIASES.items():
        if token in name:
            aliases.update(group)
    if include_generic:
        for form_factor, tokens in _FORM_FACTOR_TOKENS.items():
            if any(token in name for token in tokens):
                aliases.update(_GENERIC_ALIASES[form_factor])
    else:
        # the platform's own name may contain a generic word ("Android Tablet")
        aliases -= {a for group in _GENERIC_ALIASES.values() for a in group}
    if custom and platform in custom:
        aliases.update(alias.lower() for alias in custom[platform])
    return sorted(aliases, key=len, reverse=True)


def _contains(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text) is not None


def platforms_mentioned(
    text: str,
    platforms: Sequence[str],
    custom: Mapping[str, Sequence[str]] | None = None,
    include_generic: bool = True,
) -> list[str]:
    """Configured platforms that ``text`` refers to, in config order.

    Pass ``include_generic=False`` to ask which platform a single test
    exercises; generic words like "tablet" then match nothing on their own.
    """
    lowered = (text or "").lower()
    return [
        p for p in platforms
        if any(_contains(lowered, alias)
               for alias in platform_aliases(p, custom, include_generic))
    ]


def mentions_all_platforms(text: str) -> bool:
    """True when the text scopes the story to every platform ("each applicable package")."""
    return bool(_ALL_PLATFORMS_RE.search(text or ""))


def select_story_platforms(
    platforms: Sequence[str],
    texts: Iterable[str],
    custom: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    """Platforms a story needs tests for.

    The primary platform (first in config) is always included. Others are
    included when the texts refer to them by name or alias, or when the texts
    scope the story to all platforms.
    """
    platforms = list(platforms or [])
    if len(platforms) <= 1:
        return platforms
    text = " ".join(t for t in texts if t)
    if mentions_all_platforms(text):
        return platforms
    mentioned = set(platforms_mentioned(text, platforms, custom))
    return [p for i, p in enumerate(platforms) if i == 0 or p in mentioned]


def is_browser_platform(platform: str) -> bool:
    name = platform.lower()
    return any(token in name for token in _BROWSER_TOKENS)


def accessibility_profile(
    platform: str,
    app_type: str = "desktop",
    overrides: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Accessibility tool, test label and input mode for one platform.

    Web apps are checked in the browser regardless of the host OS, so
    "Chrome (Windows 11)" gets web tooling, not a Windows desktop scanner.
    """
    name = platform.lower()
    if overrides and platform in overrides:
        return {"tool": overrides[platform], "test_type": "Accessibility Check",
                "input": "keyboard"}
    if app_type == "web" or is_browser_platform(platform):
        return {"tool": "Accessibility Insights for Web",
                "test_type": "Keyboard And Screen Reader", "input": "keyboard"}
    if any(t in name for t in ("ipad", "iphone", "ios")):
        return {"tool": "VoiceOver", "test_type": "VoiceOver Navigation", "input": "touch"}
    if "android" in name:
        return {"tool": "TalkBack and Accessibility Scanner",
                "test_type": "TalkBack And Accessibility Scanner", "input": "touch"}
    if "mac" in name:
        return {"tool": "VoiceOver for macOS", "test_type": "VoiceOver Navigation",
                "input": "keyboard"}
    if "windows" in name:
        return {"tool": "Accessibility Insights for Windows",
                "test_type": "Keyboard Navigation", "input": "keyboard"}
    return {"tool": f"the screen reader for {platform}", "test_type": "Accessibility Check",
            "input": "keyboard"}
