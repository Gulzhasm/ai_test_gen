"""
Jira repository implementations.

Implements repository interfaces for Jira data access.
"""
from typing import Optional, List, Dict, Any
import re
from bs4 import BeautifulSoup

from core.domain.story import UserStory
from core.interfaces.repository import IStoryRepository
from .http_client import JiraHttpClient


class JiraHtmlParser:
    """Utility class for parsing HTML/ADF content from Jira."""

    @staticmethod
    def normalize_to_text(content: Any) -> str:
        """Convert Jira content to plain text.

        Handles both HTML (Jira Server) and ADF (Atlassian Document Format, Jira Cloud).

        Args:
            content: HTML string or ADF dictionary

        Returns:
            Plain text with preserved structure
        """
        if not content:
            return ""

        # Check if it's ADF (Atlassian Document Format - used in Jira Cloud)
        if isinstance(content, dict):
            return JiraHtmlParser._parse_adf(content)

        # Otherwise treat as HTML (Jira Server or rendered content)
        return JiraHtmlParser._parse_html(content)

    @staticmethod
    def _parse_adf(adf: Dict) -> str:
        """Parse Atlassian Document Format to plain text."""
        if not isinstance(adf, dict):
            return str(adf) if adf else ""

        content_type = adf.get('type', '')
        content = adf.get('content', [])
        text_parts = []

        # Handle different ADF node types
        if content_type == 'text':
            return adf.get('text', '')

        if content_type == 'paragraph':
            para_text = ''.join(JiraHtmlParser._parse_adf(child) for child in content)
            return para_text + '\n' if para_text else ''

        if content_type == 'bulletList':
            for item in content:
                item_text = JiraHtmlParser._parse_adf(item).strip()
                if item_text:
                    text_parts.append(f'• {item_text}')
            return '\n'.join(text_parts)

        if content_type == 'orderedList':
            for idx, item in enumerate(content, 1):
                item_text = JiraHtmlParser._parse_adf(item).strip()
                if item_text:
                    text_parts.append(f'{idx}. {item_text}')
            return '\n'.join(text_parts)

        if content_type == 'listItem':
            return ''.join(JiraHtmlParser._parse_adf(child) for child in content)

        if content_type == 'heading':
            heading_text = ''.join(JiraHtmlParser._parse_adf(child) for child in content)
            return f'\n{heading_text}\n' if heading_text else ''

        if content_type == 'hardBreak':
            return '\n'

        if content_type == 'doc':
            return ''.join(JiraHtmlParser._parse_adf(child) for child in content)

        # For any other type, recursively process children
        if content:
            return ''.join(JiraHtmlParser._parse_adf(child) for child in content)

        return ''

    @staticmethod
    def _parse_html(html_content: str) -> str:
        """Parse HTML content to plain text."""
        if not html_content or not isinstance(html_content, str):
            return ""

        soup = BeautifulSoup(html_content, 'html.parser')

        # Process lists
        for ul in soup.find_all(['ul', 'ol']):
            list_lines = []
            is_ordered = ul.name == 'ol'

            for idx, li in enumerate(ul.find_all('li', recursive=False), start=1):
                text = li.get_text(separator=' ').strip()
                text = ' '.join(text.split())

                if text:
                    if is_ordered:
                        list_lines.append(f'{idx}. {text}')
                    else:
                        list_lines.append(f'• {text}')

            if list_lines:
                new_text = soup.new_string('\n'.join(list_lines))
                ul.replace_with(new_text)

        text = soup.get_text(separator='\n')

        # Clean up
        lines = []
        for line in text.split('\n'):
            stripped = line.strip()
            if stripped:
                lines.append(stripped)

        return '\n'.join(lines)

    @staticmethod
    def parse_acceptance_criteria(ac_text: str) -> List[str]:
        """Parse acceptance criteria text into list of AC bullets.

        Args:
            ac_text: Raw acceptance criteria text

        Returns:
            List of complete AC bullet strings
        """
        if not ac_text:
            return []

        bullets = []
        lines = ac_text.strip().split('\n')
        current_ac = []

        def is_bullet_start(line: str) -> bool:
            """Check if line starts a new AC bullet."""
            stripped = line.strip()
            return (
                stripped.startswith('•') or
                stripped.startswith('- ') or
                re.match(r'^\d+\.(\s|$)', stripped) or
                re.match(r'^AC\s*\d+[:\.]', stripped, re.IGNORECASE) or
                re.match(r'^\[\s*[xX]?\s*\]', stripped) or
                re.match(r'^\*\s', stripped) or
                # Gherkin-style
                re.match(r'^(Given|When|Then|And)\s', stripped, re.IGNORECASE)
            )

        def clean_bullet_prefix(line: str) -> str:
            """Remove bullet prefix from line."""
            line = line.strip()
            if line.startswith('•'):
                return line[1:].strip()
            if line.startswith('- '):
                return line[2:].strip()
            if line.startswith('* '):
                return line[2:].strip()
            if re.match(r'^\d+\.(\s|$)', line):
                return re.sub(r'^\d+\.\s*', '', line).strip()
            if re.match(r'^AC\s*\d+[:\.\s]+', line, re.IGNORECASE):
                return re.sub(r'^AC\s*\d+[:\.\s]+', '', line, flags=re.IGNORECASE)
            if re.match(r'^\[\s*[xX]?\s*\]\s*', line):
                return re.sub(r'^\[\s*[xX]?\s*\]\s*', '', line)
            return line

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            if is_bullet_start(line):
                if current_ac:
                    combined = ' '.join(current_ac)
                    if len(combined) >= 10:
                        bullets.append(combined)
                    current_ac = []

                clean_line = clean_bullet_prefix(line)
                if clean_line:
                    current_ac.append(clean_line)

            elif current_ac:
                current_ac.append(stripped)

            else:
                if len(stripped) > 15:
                    current_ac.append(stripped)

        if current_ac:
            combined = ' '.join(current_ac)
            if len(combined) >= 10:
                bullets.append(combined)

        return bullets


class JiraStoryRepository(IStoryRepository):
    """Jira implementation of story repository."""

    # Common custom field names for Acceptance Criteria in Jira
    AC_FIELD_NAMES = [
        'Acceptance Criteria',
        'AcceptanceCriteria',
        'acceptance_criteria',
        'customfield_10000',  # Common default
    ]

    def __init__(
        self,
        base_url: str,
        email: str,
        api_token: str,
        project_key: str,
        ac_field_name: Optional[str] = None,
        is_cloud: bool = True
    ):
        """Initialize repository with Jira configuration.

        Args:
            base_url: Jira instance URL
            email: User email
            api_token: API token
            project_key: Jira project key (e.g., "PROJ")
            ac_field_name: Custom field name for acceptance criteria
            is_cloud: True for Jira Cloud, False for Server
        """
        self._client = JiraHttpClient(
            base_url=base_url,
            email=email,
            api_token=api_token,
            is_cloud=is_cloud
        )
        self._project_key = project_key
        self._ac_field_name = ac_field_name
        self._ac_field_id = None  # Will be discovered if not provided
        self._parser = JiraHtmlParser()

    def _discover_ac_field(self) -> Optional[str]:
        """Discover the custom field ID for Acceptance Criteria."""
        if self._ac_field_id:
            return self._ac_field_id

        if self._ac_field_name:
            # If specific field name provided, use it directly
            self._ac_field_id = self._ac_field_name
            return self._ac_field_id

        try:
            # Get all fields and search for AC field
            fields = self._client.get("field")
            for field in fields:
                field_name = field.get('name', '').lower()
                field_id = field.get('id', '')

                for ac_name in self.AC_FIELD_NAMES:
                    if ac_name.lower() in field_name or field_name == ac_name.lower():
                        self._ac_field_id = field_id
                        return self._ac_field_id

        except Exception as e:
            print(f"Error discovering AC field: {e}")

        return None

    def get_story(self, story_id: int) -> Optional[UserStory]:
        """Retrieve a user story by ID.

        Note: story_id is expected to be the numeric part of the issue key,
        or the full issue key as a string can be passed.
        """
        # Convert numeric ID to issue key format
        if isinstance(story_id, int):
            issue_key = f"{self._project_key}-{story_id}"
        else:
            issue_key = str(story_id)

        try:
            # Discover AC field if not known
            self._discover_ac_field()

            # Get issue with rendered fields for HTML content
            issue = self._client.get_issue(
                issue_key,
                expand=['renderedFields']
            )

            fields = issue.get('fields', {})
            rendered_fields = issue.get('renderedFields', {})

            title = fields.get('summary', '')
            description = fields.get('description', '')
            description_html = rendered_fields.get('description', '')

            # Try to get description as text
            description_text = self._parser.normalize_to_text(
                description_html or description
            )

            # Get acceptance criteria from custom field or description
            ac_text = ''
            if self._ac_field_id:
                ac_content = fields.get(self._ac_field_id, '')
                ac_rendered = rendered_fields.get(self._ac_field_id, '')
                ac_text = self._parser.normalize_to_text(ac_rendered or ac_content)

            # Fallback: extract AC from description if it contains AC section
            if not ac_text:
                ac_text = self._extract_ac_from_description(description_text)

            # Parse AC bullets
            ac_bullets = self._parser.parse_acceptance_criteria(ac_text)

            # Extract numeric ID from issue key
            numeric_id = int(issue_key.split('-')[-1]) if '-' in issue_key else story_id

            return UserStory(
                story_id=numeric_id,
                title=title,
                description=description_text,
                acceptance_criteria_text=ac_text,
                acceptance_criteria=ac_bullets
            )

        except Exception as e:
            print(f"Error retrieving story {story_id}: {e}")
            return None

    def _extract_ac_from_description(self, description: str) -> str:
        """Extract AC section from description if present."""
        if not description:
            return ""

        # Common patterns for AC in description
        patterns = [
            r'(?:Acceptance\s*Criteria|AC)[:\s]*\n(.*?)(?:\n\n|\Z)',
            r'(?:Definition\s*of\s*Done|DoD)[:\s]*\n(.*?)(?:\n\n|\Z)',
            r'(?:Requirements|Criteria)[:\s]*\n(.*?)(?:\n\n|\Z)',
        ]

        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()

        return ""

    def get_qa_prep(self, story_id: int) -> Optional[str]:
        """Retrieve QA Prep content for a story.

        In Jira, QA Prep might be:
        - A linked issue
        - A sub-task
        - A custom field
        - A comment with specific label
        """
        if isinstance(story_id, int):
            issue_key = f"{self._project_key}-{story_id}"
        else:
            issue_key = str(story_id)

        try:
            # Get issue with linked issues
            issue = self._client.get_issue(issue_key)
            fields = issue.get('fields', {})

            # Check for QA-related sub-tasks
            subtasks = fields.get('subtasks', [])
            for subtask in subtasks:
                subtask_summary = subtask.get('fields', {}).get('summary', '')
                if 'qa prep' in subtask_summary.lower() or 'qa planning' in subtask_summary.lower():
                    # Get the subtask details
                    subtask_key = subtask.get('key', '')
                    if subtask_key:
                        subtask_data = self._client.get_issue(subtask_key)
                        subtask_desc = subtask_data.get('fields', {}).get('description', '')
                        return self._parser.normalize_to_text(subtask_desc)

            # Check linked issues
            issue_links = fields.get('issuelinks', [])
            for link in issue_links:
                linked_issue = link.get('outwardIssue') or link.get('inwardIssue')
                if linked_issue:
                    linked_summary = linked_issue.get('fields', {}).get('summary', '')
                    if 'qa prep' in linked_summary.lower():
                        linked_key = linked_issue.get('key', '')
                        if linked_key:
                            linked_data = self._client.get_issue(linked_key)
                            linked_desc = linked_data.get('fields', {}).get('description', '')
                            return self._parser.normalize_to_text(linked_desc)

            # Check first comment for QA Prep info
            comments = self._client.get_issue_comments(issue_key, max_results=5)
            for comment in comments.get('comments', []):
                body = comment.get('body', '')
                body_text = self._parser.normalize_to_text(body)
                if 'qa prep' in body_text.lower() or 'qa planning' in body_text.lower():
                    return body_text

            return None

        except Exception as e:
            print(f"Error retrieving QA Prep for story {story_id}: {e}")
            return None
