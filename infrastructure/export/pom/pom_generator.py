"""
Orchestrate generation of a standalone POM Playwright project.

ensure_project() (idempotent, once per run): inventory -> buckets -> deterministic
page objects -> scaffold + fixtures. generate_spec() (per story): LLM writes a spec
against the page-object API, validated for method grounding (no raw selectors).
"""
import os
from typing import List, Dict, Optional

from core.domain.ui_element import ElementInventory
from infrastructure.export.pom.element_bucketer import bucket_elements
from infrastructure.export.pom.page_object_generator import generate_all, PageObjectAPI
from infrastructure.export.pom.project_scaffolder import ProjectScaffolder
from infrastructure.export.pom.pom_spec_prompt_builder import (
    PomSpecPromptBuilder, analyze_method_grounding,
)


def _safe_title(title: str, maxlen: int = 50) -> str:
    keep = "".join(c if c.isalnum() or c in " -_" else " " for c in title)
    return "_".join(keep.split())[:maxlen] or "spec"


class PomGenerator:
    def __init__(
        self,
        project_path: str,
        app_name: str,
        inventory_path: str,
        tab_names: Optional[List[str]] = None,
        api_mocks: Optional[List[Dict[str, str]]] = None,
        provider_type: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.project_path = project_path
        self.app_name = app_name
        self.inventory_path = inventory_path
        self.tab_names = tab_names or []
        self.api_mocks = api_mocks or []
        self._provider_type = provider_type
        self._model = model
        self._api_key = api_key

        self.scaffolder = ProjectScaffolder(project_path, app_name)
        self._apis: Optional[List[PageObjectAPI]] = None
        self._provider = None
        self._ready = False

    @property
    def apis(self) -> List[PageObjectAPI]:
        return self._apis or []

    @property
    def provider(self):
        if self._provider is None and self._provider_type:
            try:
                from core.services.llm.factory import create_llm_provider
                self._provider = create_llm_provider(
                    provider_type=self._provider_type,
                    model=self._model or "gpt-4o-mini",
                    timeout=120, max_retries=2, api_key=self._api_key,
                )
            except Exception as e:
                print(f"  Warning: could not create LLM provider for POM specs: {e}")
        return self._provider

    def ensure_project(self) -> List[PageObjectAPI]:
        """Scaffold (once) + regenerate page objects & fixtures from the inventory."""
        if self._ready:
            return self._apis

        inventory = ElementInventory.load(self.inventory_path)
        buckets = bucket_elements(inventory, tab_names=self.tab_names, app_name=self.app_name)
        generated = generate_all(buckets, captured_at=inventory.captured_at)
        self._apis = [g.api for g in generated]

        mock_files = [m["body_file"] for m in self.api_mocks]
        self.scaffolder.ensure_scaffold(mock_body_files=mock_files)
        self.scaffolder.write_page_objects(generated)
        self.scaffolder.write_fixtures(self._apis, self.api_mocks)

        self._ready = True
        print(f"  POM project ready at {self.project_path} "
              f"({len(generated)} page objects: {', '.join(g.class_name for g in generated)})")
        return self._apis

    def generate_spec(self, test_cases: List[Dict], story_id: str, feature_name: str) -> Optional[str]:
        """Generate one POM spec for a story; write into tests/. Returns spec content."""
        self.ensure_project()
        # Drop accessibility cases (handled by separate Axe tooling)
        functional = [tc for tc in test_cases if "accessibility" not in tc.get("title", "").lower()]
        if not functional:
            return None
        if not self.provider:
            print("  Warning: no LLM provider; cannot generate POM spec (page objects still written).")
            return None

        builder = PomSpecPromptBuilder(self.app_name, str(story_id), feature_name, self.apis)
        spec = self._invoke_llm(builder, functional)
        if not spec:
            return None

        result = analyze_method_grounding(spec, self.apis)
        if result["raw_selectors"] > 0 or result["ungrounded"]:
            print(f"  POM spec validation failed (raw_selectors={result['raw_selectors']}, "
                  f"ungrounded={result['ungrounded'][:5]}); regenerating once...")
            spec = self._invoke_llm(builder, functional)
            result = analyze_method_grounding(spec, self.apis) if spec else result

        if spec:
            cov = result["coverage"] * 100
            print(f"  POM spec method-grounding: {result['grounded']}/{result['total']} "
                  f"({cov:.0f}%), raw selectors: {result['raw_selectors']}")
            file_name = f"{story_id}_{_safe_title(feature_name)}.spec.ts"
            path = self.scaffolder.write_spec(file_name, spec)
            print(f"  POM spec: {path}")
        return spec

    def _invoke_llm(self, builder: PomSpecPromptBuilder, test_cases: List[Dict]) -> Optional[str]:
        try:
            result = self.provider.generate(
                prompt=builder.build_user_prompt(test_cases),
                system_prompt=builder.build_system_prompt(),
                temperature=0.2, max_tokens=16000,
            )
            if result is None:
                return None
            content = result.get("content", "") if isinstance(result, dict) else getattr(result, "content", "")
            if not content:
                return None
            content = content.strip()
            for prefix in ("```typescript", "```ts", "```"):
                if content.startswith(prefix):
                    content = content[len(prefix):].strip()
                    break
            if content.endswith("```"):
                content = content[:-3].strip()
            return content
        except Exception as e:
            print(f"  POM spec LLM generation failed: {e}")
            return None
