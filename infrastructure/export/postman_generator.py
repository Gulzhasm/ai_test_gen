"""
Postman Collection Generator

Generates Postman Collection v2.1 JSON from story descriptions using LLM.
Follows the same export pattern as CSVGenerator and ObjectiveGenerator.
"""
import json
import os
from typing import Dict, List, Optional


class PostmanGenerator:
    """
    Generates Postman Collection v2.1 JSON from story context.

    Uses LLM to identify API endpoints from story description and ACs.
    Falls back to empty collection skeleton if LLM unavailable or fails.
    """

    def __init__(
        self,
        app_name: str = "Application",
        provider_type: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        self._app_name = app_name
        self._provider_type = provider_type
        self._model = model
        self._api_key = api_key
        self._provider = None

    @property
    def provider(self):
        """Lazy initialization of LLM provider via factory."""
        if self._provider is None and self._provider_type:
            try:
                from core.services.llm.factory import create_llm_provider
                self._provider = create_llm_provider(
                    provider_type=self._provider_type,
                    model=self._model or "gpt-4o-mini",
                    timeout=90,
                    max_retries=2,
                    api_key=self._api_key
                )
            except Exception as e:
                print(f"  Warning: Could not create LLM provider for Postman: {e}")
        return self._provider

    def generate_collection(
        self,
        story_id: str,
        feature_name: str,
        description: str,
        acceptance_criteria: List[str],
        output_file: str
    ) -> Dict:
        """Generate Postman collection and save to file. Returns collection dict."""
        collection = self.generate_collection_dict(
            story_id, feature_name, description, acceptance_criteria
        )
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(collection, f, indent=2)
        return collection

    def generate_collection_dict(
        self,
        story_id: str,
        feature_name: str,
        description: str,
        acceptance_criteria: List[str]
    ) -> Dict:
        """Generate Postman collection as dict. LLM first, fallback if it fails."""
        if self.provider:
            collection = self._generate_with_llm(
                story_id, feature_name, description, acceptance_criteria
            )
            if collection and self._validate_collection(collection):
                return collection
            print("  Warning: LLM Postman output invalid, using skeleton fallback")

        return self._generate_skeleton(story_id, feature_name)

    def _generate_with_llm(
        self,
        story_id: str,
        feature_name: str,
        description: str,
        acceptance_criteria: List[str]
    ) -> Optional[Dict]:
        """Generate collection using LLM."""
        from core.services.llm.postman_prompt_builder import PostmanPromptBuilder

        builder = PostmanPromptBuilder(
            app_name=self._app_name,
            story_id=story_id,
            feature_name=feature_name
        )
        system_prompt = builder.build_system_prompt()
        user_prompt = builder.build_user_prompt(description, acceptance_criteria)

        try:
            # Try generate_json first (structured JSON output)
            if hasattr(self.provider, 'generate_json'):
                result = self.provider.generate_json(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=0.2,
                    max_tokens=8000
                )
                if isinstance(result, dict):
                    return result

            # Fallback: use generate() and parse JSON from text
            result = self.provider.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.2,
                max_tokens=8000
            )
            if result is None:
                return None

            content = result.get("content", "") if isinstance(result, dict) else getattr(result, "content", "")
            if not content:
                return None

            # Strip markdown fences
            content = content.strip()
            for prefix in ('```json', '```'):
                if content.startswith(prefix):
                    content = content[len(prefix):].strip()
                    break
            if content.endswith('```'):
                content = content[:-3].strip()

            return json.loads(content)

        except (json.JSONDecodeError, Exception) as e:
            print(f"  Postman LLM generation failed: {e}")
            return None

    def _validate_collection(self, collection: Dict) -> bool:
        """Validate Postman collection has required structure."""
        return (
            isinstance(collection, dict)
            and 'info' in collection
            and 'item' in collection
        )

    def _generate_skeleton(self, story_id: str, feature_name: str) -> Dict:
        """Deterministic fallback: empty collection structure."""
        return {
            "info": {
                "name": f"{story_id}: {feature_name}",
                "description": f"API tests for story {story_id} - {feature_name}",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "item": [
                {
                    "name": "TODO: Add API requests",
                    "description": f"Extract API endpoints from story {story_id} and add requests here.",
                    "item": []
                }
            ],
            "variable": [
                {"key": "base_url", "value": "http://localhost:3000/api"}
            ]
        }
