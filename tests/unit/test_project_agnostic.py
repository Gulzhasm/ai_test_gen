"""
test_project_agnostic.py — the highest-value test in this repository.

WHY THIS EXISTS
---------------
The framework's entire premise is that it is project-agnostic: one engine, many
projects, each described by a YAML config. That premise is easy to break and the
breakage is silent.

The failure mode: someone hardcodes the *current* project's specifics into the
LLM prompt or the structural validator — an app name, a prereq string, a list of
UI surfaces, an object-setup step. Everything keeps working. Tests keep passing.
Then a second project is onboarded, generation "succeeds", and the output quietly
instructs the tester to launch an application that team has never heard of.

Nobody notices until the test cases are already in the tracker.

This test catches that. Add it to CI. It is cheap and it protects the thing the
framework is actually for.

USAGE
-----
1. Drop this in tests/unit/.
2. Fill in FIXTURES below — one entry per onboarded project.
3. Run it. If it fails, the framework is leaking; fix the call site to read from
   ProjectConfig rather than hardcoding.

    pytest tests/unit/test_project_agnostic.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from projects.project_config import ProjectConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIGS = REPO_ROOT / "projects" / "configs"

FIXTURE_STORY_IDS = ("999001", "999002")


@pytest.fixture(autouse=True)
def _clean_fixture_steps_from_chroma():
    """Generation embeds steps into the per-project ChromaDB collections.

    Fixture stories must not persist there — they would be retrieved as
    reference wording for real generations. Delete them after each test.
    """
    yield
    try:
        from infrastructure.vector_db.chroma_repository import ChromaRepository
        for name in ("test_steps_env-quickdraw", "test_steps_env-ims", "test_steps"):
            repo = ChromaRepository(name)
            all_ids = repo.collection.get()["ids"]
            polluted = [i for i in all_ids
                        if any(sid in i for sid in FIXTURE_STORY_IDS)]
            if polluted:
                repo.collection.delete(ids=polluted)
    except Exception:
        pass  # cleanup is best-effort; never fail the test run itself


# -----------------------------------------------------------------------------
# FIXTURES — one entry per project you've onboarded.
#
#   config:   the YAML
#   story:    a minimal representative story for that project
#   forbidden: vocabulary that belongs to OTHER projects and must never appear
#              in this project's output. Include app names, signature UI surfaces,
#              domain verbs, assignee emails.
# -----------------------------------------------------------------------------
FIXTURES = [
    pytest.param(
        {
            "config": "env-quickdraw.yaml",
            "story": {
                "id": "999001",
                "title": "Add Show Grid toggle to the View Menu",
                "acceptance_criteria": [
                    "User can toggle grid visibility from the View Menu.",
                    "The menu label reflects the current state.",
                ],
            },
            "forbidden": [
                "establishment", "inspection", "violation", "log in to ims",
                "claim", "policy",
            ],
        },
        id="env-quickdraw",
    ),
    pytest.param(
        {
            "config": "env-ims.yaml",
            "story": {
                "id": "999002",
                "title": "Rebuild the Establishment Search Page with legacy parity",
                "acceptance_criteria": [
                    "User can search establishments by name starting with a value.",
                    "Deleted establishments are excluded from default results.",
                ],
            },
            "forbidden": [
                "quickdraw", "canvas", "draw a shape", "dimensions panel",
                "is installed",          # IMS is a web app — nothing is installed
                "dimensions menu",
            ],
        },
        id="env-ims",
    ),
]


def _generate_cases(config_name: str, story: dict) -> list:
    """Generate test cases for one story using the real generator API."""
    cfg_path = CONFIGS / config_name
    if not cfg_path.is_file():
        pytest.skip(f"config not present: {cfg_path}")

    config = ProjectConfig.load_from_yaml(str(cfg_path))

    # Import here so a missing/renamed generator skips rather than errors at
    # collection time.
    from core.services.test_generator import GenericTestGenerator  # type: ignore

    generator = GenericTestGenerator(config, enable_quality_enhancement=False)
    story_data = {
        "story_id": story["id"],
        "title": story["title"],
        "description": story.get("description", ""),
    }
    return generator.generate_test_cases(story_data, story["acceptance_criteria"])


def _generate(config_name: str, story: dict) -> str:
    """Generate for one story and return the whole output as a lowercase blob.

    Deliberately blunt: we don't care WHERE the leak appears — title, step,
    expected result, objective. Any occurrence anywhere is a bug.
    """
    return json.dumps(_generate_cases(config_name, story), default=str).lower()


@pytest.mark.parametrize("fixture", FIXTURES)
def test_no_cross_project_vocabulary(fixture: dict) -> None:
    """A config for project A must never produce vocabulary from project B."""
    blob = _generate(fixture["config"], fixture["story"])

    leaks = [term for term in fixture["forbidden"] if term.lower() in blob]

    assert not leaks, (
        f"{fixture['config']} leaked another project's vocabulary: {leaks}\n\n"
        f"This means something is hardcoded in the prompt or the validator "
        f"instead of being read from ProjectConfig. Find the call site and "
        f"source it from config — the fields already exist "
        f"(prereq_template, launch_step, close_step, main_ui_surfaces, "
        f"supported_platforms)."
    )


@pytest.mark.parametrize("fixture", FIXTURES)
def test_prereq_matches_app_type(fixture: dict) -> None:
    """Web apps are logged into. Desktop apps are installed. Never the reverse.

    This is the specific leak that survives a careless find-and-replace: someone
    swaps the app NAME but leaves "is installed" in place, and every web project
    opens its tests with a desktop prerequisite.
    """
    cfg_path = CONFIGS / fixture["config"]
    if not cfg_path.is_file():
        pytest.skip(f"config not present: {cfg_path}")

    config = ProjectConfig.load_from_yaml(str(cfg_path))
    app_type = config.application.app_type
    blob = _generate(fixture["config"], fixture["story"])

    if app_type == "web":
        assert "is installed" not in blob, (
            f"{fixture['config']} is a WEB app but its generated tests say "
            f"'is installed'. The prereq is not being read from config."
        )
    elif app_type == "desktop":
        assert "log in to" not in blob or "install" in blob, (
            f"{fixture['config']} is a DESKTOP app but its tests only mention "
            f"logging in. Check prereq_template is being applied."
        )


@pytest.mark.parametrize("fixture", FIXTURES)
def test_areas_come_from_config(fixture: dict) -> None:
    """Every Area in a generated title must exist in that project's allowed_areas.

    An Area from outside the list means the generator got it from somewhere other
    than config — i.e. it's hardcoded.
    """
    cfg_path = CONFIGS / fixture["config"]
    if not cfg_path.is_file():
        pytest.skip(f"config not present: {cfg_path}")

    config = ProjectConfig.load_from_yaml(str(cfg_path))
    allowed = {a.lower() for a in config.rules.allowed_areas}
    if not allowed:
        pytest.skip("config declares no allowed_areas")

    test_cases = _generate_cases(fixture["config"], fixture["story"])

    offenders: list[str] = []
    for tc in test_cases:
        title = tc.get("title", "")
        # Title format: <StoryID>-XXX: <Feature> / <Area> / <Scenario>
        parts = [p.strip() for p in title.split("/")]
        if len(parts) < 3:
            continue
        area = parts[1].lower()
        # Accessibility titles carry a device suffix: "Canvas (iPad)"
        area = area.split("(")[0].strip()
        # Accessibility-class tests use "Accessibility" as their Area by
        # long-standing suite convention (device suffix in the scenario);
        # they are exempt from the allowed_areas check.
        if area == "accessibility":
            continue
        if area and area not in allowed:
            offenders.append(f"{area!r} in {title!r}")

    assert not offenders, (
        f"{fixture['config']} produced Areas not in allowed_areas:\n  "
        + "\n  ".join(offenders)
        + "\n\nThe Area list is hardcoded somewhere instead of read from "
          "config.rules.allowed_areas."
    )
