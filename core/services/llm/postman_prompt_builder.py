"""
Postman Collection Prompt Builder

Builds system + user prompts for LLM-based generation of Postman Collections
from user story descriptions and acceptance criteria.
"""
import json
from typing import List


class PostmanPromptBuilder:
    """Builds system + user prompts for Postman collection generation."""

    def __init__(self, app_name: str, story_id: str, feature_name: str):
        self.app_name = app_name
        self.story_id = story_id
        self.feature_name = feature_name

    @classmethod
    def from_project_config(cls, config, story_id: str, feature_name: str) -> 'PostmanPromptBuilder':
        return cls(
            app_name=config.application.name,
            story_id=story_id,
            feature_name=feature_name
        )

    def build_system_prompt(self) -> str:
        """System prompt with Postman Collection v2.1 best practices."""
        return """You are an API test engineer who generates Postman Collection v2.1 JSON from user story descriptions.

## OUTPUT FORMAT
Return ONLY valid JSON matching Postman Collection v2.1 schema. No markdown fences. No commentary.

## COLLECTION STRUCTURE
{
  "info": {
    "name": "Story ID: Feature Name",
    "description": "API tests for story ...",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Folder name",
      "item": [
        {
          "name": "Request name (Story-ID)",
          "request": {
            "method": "GET|POST|PUT|DELETE|PATCH",
            "header": [
              { "key": "Content-Type", "value": "application/json" }
            ],
            "url": {
              "raw": "{{base_url}}/endpoint",
              "host": ["{{base_url}}"],
              "path": ["endpoint"]
            },
            "body": {
              "mode": "raw",
              "raw": "{ }",
              "options": { "raw": { "language": "json" } }
            }
          },
          "response": [],
          "event": [
            {
              "listen": "test",
              "script": {
                "exec": [
                  "pm.test('Status code is 200', function() {",
                  "  pm.response.to.have.status(200);",
                  "});"
                ]
              }
            }
          ]
        }
      ]
    }
  ],
  "variable": [
    { "key": "base_url", "value": "http://localhost:3000/api" }
  ]
}

## RULES
1. Use {{base_url}} variable for all URLs
2. Include test scripts for EVERY request (status code checks at minimum)
3. Group related requests into folders (e.g., "Setup", "Core Actions", "Verification")
4. Use meaningful request names that include the story ID
5. Include request body examples for POST/PUT/PATCH
6. Add Content-Type: application/json header where applicable
7. Use {{variables}} for dynamic values (tokens, IDs)
8. Extract API endpoints from the story description and acceptance criteria
9. If no clear API endpoints exist, infer RESTful endpoints from the feature
"""

    def build_user_prompt(self, description: str, acceptance_criteria: List[str]) -> str:
        """User prompt with story context for API extraction."""
        ac_text = '\n'.join(f"- {ac}" for ac in acceptance_criteria)
        return f"""Generate a Postman Collection v2.1 JSON for this user story.

## CONTEXT
- Application: {self.app_name}
- Story: {self.story_id} - {self.feature_name}

## STORY DESCRIPTION
{description}

## ACCEPTANCE CRITERIA
{ac_text}

## REQUIREMENTS
1. Identify all API endpoints implied by the story
2. Create requests for each endpoint (CRUD operations as applicable)
3. Include test scripts that validate response status and key fields
4. Group requests into logical folders
5. Include pre-request scripts for auth tokens if needed
6. Add description to each request linking back to story {self.story_id}

Return ONLY the Postman Collection JSON."""
