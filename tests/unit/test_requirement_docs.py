"""Tests for the requirement documents loader (local source)."""
from infrastructure.docs.requirement_docs import RequirementDocsLoader


def _write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_loads_story_result_links_and_named_docs(tmp_path):
    _write(tmp_path, "story-results/123.md", "See [spec](../tracker/123.md#ac), [legacy](../legacy-ui/users.md) and [web](https://x.y/z.md).")
    _write(tmp_path, "tracker/123.md", "Tracker spec text")
    _write(tmp_path, "legacy-ui/users.md", "Old system screen")
    _write(tmp_path, "handoffs/story-123-review.md", "Handoff text")
    _write(tmp_path, "story-results/999.md", "Other story")
    loader = RequirementDocsLoader({"enabled": True, "source": "local", "local_root": str(tmp_path),
                                    "exclude": ["legacy-ui/"]})
    docs = loader.load(123)
    assert docs.paths() == ["story-results/123.md", "tracker/123.md", "handoffs/story-123-review.md"]
    assert [d.role for d in docs.docs] == ["story_result", "linked", "named"]
    assert "Old system" not in docs.grounding_text()


def test_prompt_block_respects_budget_and_order(tmp_path):
    _write(tmp_path, "story-results/5.md", "A" * 50 + " [t](../tracker/5.md)")
    _write(tmp_path, "tracker/5.md", "B" * 5000)
    docs = RequirementDocsLoader({"enabled": True, "source": "local", "local_root": str(tmp_path)}).load(5)
    block = docs.prompt_block(max_chars=1000)
    assert block.startswith("<requirement_documents>")
    assert block.index("story-results/5.md") < block.index("tracker/5.md")
    assert "truncated" in block


def test_disabled_or_missing_returns_empty(tmp_path):
    assert not RequirementDocsLoader({"enabled": False}).load(1).found
    assert not RequirementDocsLoader({"enabled": True, "source": "local", "local_root": str(tmp_path)}).load(1).found
