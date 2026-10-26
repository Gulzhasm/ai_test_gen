"""
Requirement documents loader.

Some teams keep the refined requirements of a story next to the code rather than
in the work item, for example ``documentation/story-results/<story id>.md`` per story
in the application's git repo, linking to tracker specs, verification records, QA
runbooks, UI state/schema docs and answered customer questions. Test cases generated
from the work item alone had to guess these details, which is where many
hallucinations came from.

This loader collects, for one story:
  1. the story-results file (``<story_results_dir>/<id>.md``),
  2. every repository document it links to (one hop, relative markdown links),
  3. any other document whose path contains the story id,
skipping excluded paths (for example legacy-system descriptions, which must not
set expectations for a rewrite). Documents are cached on disk.

Configuration (project YAML)::

    requirement_docs:
      enabled: true
      source: ado_git            # or "local"
      ado_repo: My App           # ado_git: repository name in the ADO project
      branch: main               # ado_git: optional
      local_root: ""             # local: path to the documentation folder
      root: /documentation       # folder inside the repo
      story_results_dir: story-results
      follow_links: true
      exclude: [project-planning/legacy-ui/]
      max_chars: 120000          # prompt budget for all documents together

The returned text is reference DATA. Prompts must present it as such.
"""
from __future__ import annotations

import base64
import json
import os
import posixpath
import re
from dataclasses import dataclass, field
from pathlib import Path

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

_LINK = re.compile(r"\]\(((?!https?:|mailto:|#)[^)\s#]+\.md)(?:#[^)]*)?\)")


@dataclass
class RequirementDoc:
    path: str          # path relative to the documentation root
    text: str
    role: str          # "story_result" | "linked" | "named"


@dataclass
class RequirementDocs:
    story_id: int
    docs: list[RequirementDoc] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return bool(self.docs)

    def grounding_text(self) -> str:
        """All document text, for deterministic grounding checks (no budget)."""
        return "\n".join(d.text for d in self.docs)

    def prompt_block(self, max_chars: int = 120_000) -> str:
        """Fenced reference block for an LLM prompt, story-results first, within budget."""
        if not self.docs:
            return ""
        parts, used = [], 0
        order = {"story_result": 0, "named": 1, "linked": 2}
        for d in sorted(self.docs, key=lambda d: order.get(d.role, 3)):
            remaining = max_chars - used
            if remaining <= 500:
                parts.append(f'<document path="{d.path}" omitted="budget"/>')
                continue
            body = d.text if len(d.text) <= remaining else d.text[:remaining] + "\n[... truncated ...]"
            parts.append(f'<document path="{d.path}" role="{d.role}">\n{body}\n</document>')
            used += len(body)
        return "<requirement_documents>\n" + "\n".join(parts) + "\n</requirement_documents>"

    def story_result_text(self) -> str:
        """Text of the story's own story-results file (the most specific document)."""
        return "\n".join(d.text for d in self.docs if d.role == "story_result")

    def paths(self) -> list[str]:
        return [d.path for d in self.docs]


class RequirementDocsLoader:
    """Loads requirement documents for a story from a local folder or an ADO git repo."""

    def __init__(self, settings: dict, organization: str = "", project: str = "",
                 cache_dir: str | Path = "output/.cache/requirement_docs", pat: str | None = None):
        self.s = settings or {}
        self.enabled = bool(self.s.get("enabled"))
        self.source = self.s.get("source", "local")
        self.root = "/" + str(self.s.get("root", "/documentation")).strip("/")
        self.results_dir = str(self.s.get("story_results_dir", "story-results")).strip("/")
        self.exclude = [e.strip("/") for e in self.s.get("exclude", [])]
        self.follow_links = self.s.get("follow_links", True)
        self.org, self.project = organization, project
        self.repo = self.s.get("ado_repo", "")
        self.branch = self.s.get("branch")
        self.local_root = Path(self.s["local_root"]).expanduser() if self.s.get("local_root") else None
        self.cache = Path(cache_dir) / re.sub(r"[^\w.-]+", "_", f"{self.org}_{self.project}_{self.repo or 'local'}")
        self._pat = pat or os.getenv("ADO_PAT", "")
        self._tree: list[str] | None = None

    # -- public ---------------------------------------------------------------

    def load(self, story_id: int) -> RequirementDocs:
        result = RequirementDocs(story_id)
        if not self.enabled:
            return result
        seen: set[str] = set()
        main = f"{self.results_dir}/{story_id}.md"
        text = self._read(main)
        if text is not None:
            result.docs.append(RequirementDoc(main, text, "story_result"))
            seen.add(main)
            if self.follow_links:
                for rel in self._links(main, text):
                    if rel in seen or self._excluded(rel):
                        continue
                    linked = self._read(rel)
                    if linked is not None:
                        result.docs.append(RequirementDoc(rel, linked, "linked"))
                        seen.add(rel)
        for rel in self._named_paths(story_id):
            if rel in seen or self._excluded(rel):
                continue
            named = self._read(rel)
            if named is not None:
                result.docs.append(RequirementDoc(rel, named, "named"))
                seen.add(rel)
        return result

    # -- helpers --------------------------------------------------------------

    def _excluded(self, rel: str) -> bool:
        return any(rel.startswith(e) or f"/{e}" in f"/{rel}" for e in self.exclude)

    @staticmethod
    def _links(base_rel: str, text: str) -> list[str]:
        base_dir = posixpath.dirname(base_rel)
        out = []
        for m in _LINK.finditer(text):
            rel = posixpath.normpath(posixpath.join(base_dir, m.group(1)))
            if not rel.startswith(".."):
                out.append(rel)
        return list(dict.fromkeys(out))

    def _named_paths(self, story_id: int) -> list[str]:
        sid = str(story_id)
        return [p for p in self._list_tree() if sid in posixpath.basename(p) and p.endswith(".md")]

    def _list_tree(self) -> list[str]:
        if self._tree is not None:
            return self._tree
        tree: list[str] = []
        if self.source == "local" and self.local_root and self.local_root.exists():
            tree = [str(p.relative_to(self.local_root)).replace(os.sep, "/") for p in self.local_root.rglob("*.md")]
        elif self.source == "ado_git":
            cached = self.cache / "_tree.json"
            if cached.exists():
                tree = json.loads(cached.read_text())
            else:
                data = self._ado_get("items", {"scopePath": self.root, "recursionLevel": "Full"}, as_json=True)
                if data:
                    prefix = self.root.rstrip("/") + "/"
                    tree = [i["path"][len(prefix):] for i in data.get("value", [])
                            if i.get("gitObjectType") == "blob" and i["path"].startswith(prefix)]
                    cached.parent.mkdir(parents=True, exist_ok=True)
                    cached.write_text(json.dumps(tree))
        self._tree = tree
        return tree

    def _read(self, rel: str) -> str | None:
        if self.source == "local":
            if not self.local_root:
                return None
            p = self.local_root / rel
            return p.read_text(errors="replace") if p.is_file() else None
        cached = self.cache / rel
        if cached.is_file():
            return cached.read_text(errors="replace")
        text = self._ado_get("items", {"path": f"{self.root}/{rel}"}, as_json=False)
        if text is None:
            return None
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(text)
        return text

    def _ado_get(self, endpoint: str, params: dict, as_json: bool):
        if requests is None or not (self.org and self.project and self.repo and self._pat):
            return None
        url = (f"https://dev.azure.com/{self.org}/{self.project}/_apis/git/repositories/"
               f"{requests.utils.quote(self.repo)}/{endpoint}")
        q = dict(params, **{"api-version": "7.1"})
        if self.branch:
            q.update({"versionDescriptor.version": self.branch, "versionDescriptor.versionType": "branch"})
        token = base64.b64encode(f":{self._pat}".encode()).decode()
        headers = {"Authorization": f"Basic {token}", "Accept": "application/json" if as_json else "text/plain"}
        try:
            r = requests.get(url, params=q, headers=headers, timeout=30)
        except requests.RequestException:
            return None
        if r.status_code != 200:
            return None
        return r.json() if as_json else r.text


def load_for_story(project_config, story_id: int) -> RequirementDocs:
    """Convenience: build a loader from a project config object/dict and load one story."""
    settings = _get(project_config, "requirement_docs") or {}
    ado = _get(project_config, "ado") or {}
    loader = RequirementDocsLoader(settings, _get(ado, "organization") or "", _get(ado, "project") or "")
    return loader.load(story_id)


def _get(obj, key):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)
