"""
Azure DevOps repository implementations.

Implements repository interfaces for ADO data access.
"""
from typing import Optional, List, Dict, Any
import re
from bs4 import BeautifulSoup

from core.domain.story import UserStory
from core.domain.test_case import TestCase
from core.interfaces.repository import (
    IStoryRepository,
    ITestSuiteRepository,
    ITestCaseRepository
)
from core.interfaces.config_provider import IADOConfig
from .http_client import ADOHttpClient


class HtmlParser:
    """Utility class for parsing HTML content from ADO."""

    @staticmethod
    def normalize_to_text(html_content: str) -> str:
        """Convert HTML to plain text, preserving structure.

        Generic HTML-to-text converter that works with any ADO project's
        AC format. Handles ordered lists, unordered lists, and various
        HTML structures.

        Args:
            html_content: HTML string

        Returns:
            Plain text with preserved bullet points and line breaks
        """
        if not html_content:
            return ""

        soup = BeautifulSoup(html_content, 'html.parser')

        # Process lists - extract text content directly to avoid
        # line break issues from nested HTML elements
        for ul in soup.find_all(['ul', 'ol']):
            list_lines = []
            is_ordered = ul.name == 'ol'

            for idx, li in enumerate(ul.find_all('li', recursive=False), start=1):
                # Get text using space separator to flatten nested elements
                text = li.get_text(separator=' ').strip()
                # Clean up any extra whitespace
                text = ' '.join(text.split())

                if text:
                    # Prepend appropriate marker
                    if is_ordered:
                        list_lines.append(f'{idx}. {text}')
                    else:
                        list_lines.append(f'• {text}')

            # Replace list element with formatted text
            if list_lines:
                new_text = soup.new_string('\n'.join(list_lines))
                ul.replace_with(new_text)

        # Get text with newlines
        text = soup.get_text(separator='\n')

        # Clean up: merge lines that are clearly continuations
        lines = []
        for line in text.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue

            # Check if this line should be merged with previous
            # (starts lowercase, is a short fragment following content)
            if (lines and
                stripped and
                stripped[0].islower() and
                len(stripped) < 50 and
                not stripped.startswith(('•', '-', '*'))):
                # Merge with previous line
                lines[-1] = lines[-1] + ' ' + stripped
            else:
                lines.append(stripped)

        return '\n'.join(lines)

    @staticmethod
    def parse_acceptance_criteria(ac_text: str) -> List[str]:
        """Parse acceptance criteria text into list of meaningful AC bullets.

        Recognizes bullet patterns and groups continuation lines appropriately.

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
            """Check if line starts a new AC bullet.

            Generic bullet detection that works with various formats:
            - Bullet markers: •, -, *
            - Numbered: 1. 2. 3. (with or without space)
            - AC format: AC1:, AC 2., etc.
            - Checkbox: [ ] or [x]
            """
            stripped = line.strip()
            return (
                stripped.startswith('•') or
                stripped.startswith('- ') or
                re.match(r'^\d+\.(\s|$)', stripped) or  # "1. text" or "1." alone
                re.match(r'^AC\s*\d+[:\.]', stripped, re.IGNORECASE) or
                re.match(r'^\[\s*[xX]?\s*\]', stripped) or  # Checkbox style [ ] or [x]
                re.match(r'^\*\s', stripped)  # Asterisk bullet
            )

        def clean_bullet_prefix(line: str) -> str:
            """Remove bullet prefix from line.

            Returns empty string if the line is ONLY a bullet marker
            (like "1." alone), so we can detect this and merge with next line.
            """
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

        def is_fragment(line: str) -> bool:
            """Check if line is a meaningless fragment (single word, punctuation only)."""
            stripped = line.strip().rstrip('.,;:!?')  # Remove trailing punctuation for check

            # Empty after stripping
            if not stripped:
                return True

            # Just punctuation
            if re.match(r'^[.,;:!?\-]+$', line.strip()):
                return True

            # Single word of 12 chars or less (common fragments)
            if len(stripped) <= 12 and ' ' not in stripped:
                # Common article/conjunction words are fragments
                if stripped.lower() in ['given', 'when', 'then', 'and', 'or', 'the', 'a', 'an',
                                         'is', 'are', 'was', 'were', 'be', 'been', 'being',
                                         'have', 'has', 'had', 'do', 'does', 'did', 'will',
                                         'would', 'could', 'should', 'may', 'might', 'must',
                                         'shall', 'can', 'need', 'to', 'of', 'in', 'for',
                                         'on', 'with', 'at', 'by', 'from', 'as', 'into',
                                         'through', 'during', 'before', 'after', 'above',
                                         'below', 'between', 'under', 'again', 'further',
                                         'once', 'here', 'there', 'all', 'each', 'few',
                                         'more', 'most', 'other', 'some', 'such', 'no',
                                         'not', 'only', 'own', 'same', 'so', 'than', 'too',
                                         'very', 'just', 'also', 'now', 'logic', 'menu',
                                         'edit', 'view', 'file', 'help', 'tools', 'window']:
                    return True
                # Single capitalized word without context is likely a fragment
                if re.match(r'^[A-Z][a-z]*\.?$', line.strip()):
                    return True

            return False

        # Track if we just saw a bullet marker with no content (e.g., "1." alone)
        expecting_content = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Skip obvious fragments when not building an AC
            if is_fragment(stripped) and not current_ac and not expecting_content:
                continue

            if is_bullet_start(line):
                # Save previous AC if meaningful
                if current_ac:
                    combined = ' '.join(current_ac)
                    if len(combined) >= 10:  # Minimal length check
                        bullets.append(combined)
                    current_ac = []

                # Start new AC
                clean_line = clean_bullet_prefix(line)
                if clean_line and not is_fragment(clean_line):
                    current_ac.append(clean_line)
                    expecting_content = False
                else:
                    # Bullet marker alone (e.g., "1.") - content is on next line
                    expecting_content = True

            elif expecting_content:
                # This line is the content for a standalone bullet marker
                if stripped and not is_fragment(stripped):
                    current_ac.append(stripped)
                expecting_content = False

            elif current_ac:
                # Continuation of current AC
                clean_line = stripped
                # Clean any sub-bullet markers
                if clean_line.startswith('-') and len(clean_line) > 1:
                    clean_line = clean_line[1:].strip()

                if clean_line and not is_fragment(clean_line):
                    current_ac.append(clean_line)

            else:
                # No current AC and not a bullet - could be first line without bullet
                # Treat as new AC if it's meaningful content
                if len(stripped) > 15 and not is_fragment(stripped):
                    current_ac.append(stripped)

        # Don't forget the last AC
        if current_ac:
            combined = ' '.join(current_ac)
            if len(combined) >= 10:
                bullets.append(combined)

        return bullets


class ADOStoryRepository(IStoryRepository):
    """Azure DevOps implementation of story repository."""

    def __init__(self, config: IADOConfig):
        """Initialize repository with ADO configuration.

        Args:
            config: Azure DevOps configuration (implements IADOConfig)
        """
        self._config = config
        self._client = ADOHttpClient(
            organization=config.organization,
            project=config.project,
            pat=config.pat
        )
        self._parser = HtmlParser()

    def get_story(self, story_id: int) -> Optional[UserStory]:
        """Retrieve a user story by ID."""
        try:
            data = self._client.get(
                f"_apis/wit/workitems/{story_id}",
                params={"$expand": "all"}
            )

            fields = data.get('fields', {})
            title = fields.get('System.Title', '')
            description_html = fields.get('System.Description', '')
            ac_html = fields.get('Microsoft.VSTS.Common.AcceptanceCriteria', '')

            description = self._parser.normalize_to_text(description_html)
            ac_text = self._parser.normalize_to_text(ac_html)

            # Try comments if AC field is empty
            if not ac_text:
                ac_text = self._extract_ac_from_comments(story_id)

            ac_bullets = self._parser.parse_acceptance_criteria(ac_text)

            return UserStory(
                story_id=story_id,
                title=title,
                description=description,
                acceptance_criteria_text=ac_text,
                acceptance_criteria=ac_bullets
            )
        except Exception as e:
            print(f"Error retrieving story {story_id}: {e}")
            return None

    def get_qa_prep(self, story_id: int) -> Optional[str]:
        """
        Retrieve QA Prep content for a story.

        QA Prep should be a child task under the story. This method:
        1. Gets child work items linked to the story
        2. Finds the QA Prep task among them
        3. Returns the QA Planning Summary from the Description field
        """
        qa_prep_pattern = self._config.qa_prep_pattern
        if not qa_prep_pattern:
            return None

        qa_prep_title = qa_prep_pattern.format(story_id=story_id)

        try:
            # First, try to get QA Prep as a child task linked to the story
            # Get story with relations
            story_data = self._client.get(
                f"_apis/wit/workitems/{story_id}",
                params={"$expand": "relations"}
            )

            relations = story_data.get('relations', [])

            # Look for child links (System.LinkTypes.Hierarchy-Forward)
            child_ids = []
            for relation in relations:
                rel_type = relation.get('rel', '')
                # Child links are "System.LinkTypes.Hierarchy-Forward" or contains "Child"
                if 'Hierarchy-Forward' in rel_type or 'Child' in rel_type:
                    url = relation.get('url', '')
                    # Extract work item ID from URL
                    if '/workItems/' in url:
                        child_id = url.split('/workItems/')[-1]
                        try:
                            child_ids.append(int(child_id))
                        except ValueError:
                            pass

            # Check each child for QA Prep
            for child_id in child_ids:
                try:
                    child_data = self._client.get(f"_apis/wit/workitems/{child_id}")
                    child_fields = child_data.get('fields', {})
                    child_title = child_fields.get('System.Title', '')

                    # Check if this is the QA Prep task
                    if 'QA Prep' in child_title or child_title == qa_prep_title:
                        description = child_fields.get('System.Description', '')
                        if description:
                            return self._parser.normalize_to_text(description)
                except Exception:
                    continue

            # Fallback: Search by title pattern if no child QA Prep found
            query = (
                f"Select [System.Id], [System.Title] "
                f"From WorkItems "
                f"Where [System.Title] Contains 'QA Prep' "
                f"And [System.Title] Contains '{story_id}'"
            )

            result = self._client.execute_wiql(query)
            work_items = result.get('workItems', [])

            if work_items:
                work_item_id = work_items[0]['id']
                item_data = self._client.get(f"_apis/wit/workitems/{work_item_id}")
                description = item_data.get('fields', {}).get('System.Description', '')
                return self._parser.normalize_to_text(description)

            return None
        except Exception as e:
            print(f"Error retrieving QA Prep for story {story_id}: {e}")
            return None

    def update_qa_prep(self, story_id: int, summary_text: str) -> bool:
        """Update QA Prep child task Description with QA Planning Summary.

        Finds the QA Prep child task under the story and updates its
        Description field with the provided Markdown summary (converted to HTML).

        Args:
            story_id: Parent story ID
            summary_text: Markdown-formatted QA Planning Summary

        Returns:
            True if updated successfully, False otherwise
        """
        qa_prep_id = self._find_qa_prep_id(story_id)
        if not qa_prep_id:
            print(f"  No QA Prep task found for story {story_id}, skipping ADO update")
            return False

        # Convert Markdown to HTML for ADO
        html_content = self._markdown_to_html(summary_text)

        try:
            patch_doc = [
                {
                    "op": "add",
                    "path": "/fields/System.Description",
                    "value": html_content
                }
            ]

            self._client.patch(
                f"_apis/wit/workitems/{qa_prep_id}",
                data=patch_doc
            )
            print(f"  QA Summary uploaded to ADO QA Prep task #{qa_prep_id}")
            return True
        except Exception as e:
            print(f"  Failed to update QA Prep task #{qa_prep_id}: {e}")
            return False

    def _find_qa_prep_id(self, story_id: int) -> Optional[int]:
        """Find QA Prep child task ID for a story.

        Returns:
            Work item ID of the QA Prep task, or None if not found
        """
        qa_prep_pattern = self._config.qa_prep_pattern
        if not qa_prep_pattern:
            return None

        qa_prep_title = qa_prep_pattern.format(story_id=story_id)

        try:
            # Get story with relations
            story_data = self._client.get(
                f"_apis/wit/workitems/{story_id}",
                params={"$expand": "relations"}
            )

            relations = story_data.get('relations', [])

            # Look for child links
            child_ids = []
            for relation in relations:
                rel_type = relation.get('rel', '')
                if 'Hierarchy-Forward' in rel_type or 'Child' in rel_type:
                    url = relation.get('url', '')
                    if '/workItems/' in url:
                        child_id = url.split('/workItems/')[-1]
                        try:
                            child_ids.append(int(child_id))
                        except ValueError:
                            pass

            # Check each child for QA Prep
            for child_id in child_ids:
                try:
                    child_data = self._client.get(f"_apis/wit/workitems/{child_id}")
                    child_title = child_data.get('fields', {}).get('System.Title', '')
                    if 'QA Prep' in child_title or child_title == qa_prep_title:
                        return child_id
                except Exception:
                    continue

            # Fallback: WIQL search
            query = (
                f"Select [System.Id], [System.Title] "
                f"From WorkItems "
                f"Where [System.Title] Contains 'QA Prep' "
                f"And [System.Title] Contains '{story_id}'"
            )

            result = self._client.execute_wiql(query)
            work_items = result.get('workItems', [])
            if work_items:
                return work_items[0]['id']

            return None
        except Exception as e:
            print(f"  Error finding QA Prep task for story {story_id}: {e}")
            return None

    @staticmethod
    def _bold_to_html(text: str) -> str:
        """Convert **bold** Markdown to <b>bold</b> HTML."""
        return re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)

    @staticmethod
    def _markdown_to_html(markdown_text: str) -> str:
        """Convert Markdown QA summary to HTML for ADO Description field.

        Handles: **bold**, - bullets, indented - sub-bullets, paragraphs.
        """
        bold = ADOStoryRepository._bold_to_html
        lines = markdown_text.split('\n')
        html_parts = []
        in_list = False
        in_sublist = False

        for line in lines:
            stripped = line.strip()

            # Empty line = close lists and add paragraph break
            if not stripped:
                if in_sublist:
                    html_parts.append('</ul></li>')
                    in_sublist = False
                if in_list:
                    html_parts.append('</ul>')
                    in_list = False
                continue

            # Sub-bullet (indented with spaces/tab + -)
            if re.match(r'^(\s{2,}|\t)-\s+', line):
                content = re.sub(r'^(\s{2,}|\t)-\s+', '', line).strip()
                content = bold(content)
                if not in_sublist:
                    if not in_list:
                        html_parts.append('<ul>')
                        in_list = True
                    html_parts.append('<li><ul>')
                    in_sublist = True
                html_parts.append(f'<li>{content}</li>')
                continue

            # Top-level bullet
            if stripped.startswith('- '):
                content = stripped[2:].strip()
                content = bold(content)
                if in_sublist:
                    html_parts.append('</ul></li>')
                    in_sublist = False
                if not in_list:
                    html_parts.append('<ul>')
                    in_list = True
                html_parts.append(f'<li>{content}</li>')
                continue

            # Regular text (close any open lists first)
            if in_sublist:
                html_parts.append('</ul></li>')
                in_sublist = False
            if in_list:
                html_parts.append('</ul>')
                in_list = False

            # Convert bold and wrap in div
            content = bold(stripped)
            html_parts.append(f'<div>{content}</div>')

        # Close any remaining open lists
        if in_sublist:
            html_parts.append('</ul></li>')
        if in_list:
            html_parts.append('</ul>')

        return '\n'.join(html_parts)

    def _extract_ac_from_comments(self, story_id: int) -> str:
        """Extract AC from the FIRST work item comment only.

        Only retrieves the first comment to get the original AC,
        filtering out subsequent comments which are typically
        discussion/noise from team members.
        """
        try:
            comments = self._client.get(f"_apis/wit/workitems/{story_id}/comments")
            comment_list = comments.get('comments', [])

            # Only process the FIRST comment (oldest)
            # Comments are typically ordered by date, first is the original
            if comment_list:
                # Get the first comment only
                first_comment = comment_list[0]
                text = first_comment.get('text', '')
                if text:
                    return self._parser.normalize_to_text(text)
        except Exception:
            pass
        return ""


class ADOTestSuiteRepository(ITestSuiteRepository):
    """Azure DevOps implementation of test suite repository."""

    def __init__(self, config: IADOConfig):
        """Initialize repository with ADO configuration."""
        self._config = config
        self._client = ADOHttpClient(
            organization=config.organization,
            project=config.project,
            pat=config.pat
        )

    def find_suite_by_story_id(self, story_id: int) -> Optional[Dict[str, Any]]:
        """Find test suite matching story ID pattern."""
        prefix = f"{story_id} :"

        try:
            # Get all test plans
            plans = self._client.get("_apis/testplan/plans")

            for plan in plans.get('value', []):
                plan_id = plan['id']
                suites = self._get_all_suites(plan_id)

                for suite in suites:
                    if suite.get('name', '').startswith(prefix):
                        return {
                            'id': suite['id'],
                            'name': suite['name'],
                            'plan_id': plan_id
                        }
        except Exception as e:
            print(f"Error finding test suite for story {story_id}: {e}")

        return None

    def _get_all_suites(self, plan_id: int) -> List[Dict]:
        """Get all suites in a test plan recursively."""
        suites = []
        try:
            result = self._client.get(f"_apis/testplan/Plans/{plan_id}/suites")
            suites.extend(result.get('value', []))
        except Exception:
            pass
        return suites

    def create_suite(
        self,
        plan_id: int,
        suite_name: str,
        story_id: int
    ) -> Optional[Dict[str, Any]]:
        """Create a new test suite."""
        try:
            # Get root suite
            plan = self._client.get(f"_apis/testplan/Plans/{plan_id}")
            root_suite_id = plan.get('rootSuite', {}).get('id', plan_id)

            # Create suite
            result = self._client.post(
                f"_apis/testplan/Plans/{plan_id}/suites/{root_suite_id}",
                data={
                    "suiteType": "staticTestSuite",
                    "name": suite_name
                }
            )

            return {
                'id': result['id'],
                'name': result['name'],
                'plan_id': plan_id
            }
        except Exception as e:
            print(f"Error creating test suite: {e}")
            return None

    def add_test_case_to_suite(
        self,
        plan_id: int,
        suite_id: int,
        test_case_id: int
    ) -> bool:
        """Add a test case to a test suite."""
        try:
            self._client.post(
                f"_apis/testplan/Plans/{plan_id}/Suites/{suite_id}/TestCase",
                data=[{'workItem': {'id': test_case_id}}]
            )
            return True
        except Exception as e:
            print(f"Error adding test case to suite: {e}")
            return False

    def get_test_cases_in_suite(
        self,
        plan_id: int,
        suite_id: int
    ) -> List[Dict[str, Any]]:
        """Get all test cases in a test suite.

        Returns:
            List of dicts with 'ado_id' and 'title' keys for each test case.
        """
        test_cases = []
        try:
            result = self._client.get(
                f"_apis/testplan/Plans/{plan_id}/Suites/{suite_id}/TestCase"
            )

            for item in result.get('value', []):
                work_item = item.get('workItem', {})
                test_cases.append({
                    'ado_id': work_item.get('id'),
                    'title': work_item.get('name', '')
                })
        except Exception as e:
            print(f"Error getting test cases from suite: {e}")

        return test_cases


class ADOTestCaseRepository(ITestCaseRepository):
    """Azure DevOps implementation of test case repository."""

    def __init__(self, config: IADOConfig):
        """Initialize repository with ADO configuration."""
        self._config = config
        self._client = ADOHttpClient(
            organization=config.organization,
            project=config.project,
            pat=config.pat
        )

    def create_test_case(
        self,
        title: str,
        steps: List[Dict[str, str]],
        objective: str,
        **kwargs
    ) -> Optional[int]:
        """Create a test case work item in Design state.

        Test cases are always created in 'Design' state.
        State transition to 'Ready' happens later via update-objectives workflow.
        """
        try:
            steps_xml = self._build_steps_xml(steps)

            patch_doc = [
                {"op": "add", "path": "/fields/System.Title", "value": title},
                {"op": "add", "path": "/fields/Microsoft.VSTS.TCM.Steps", "value": steps_xml}
            ]

            # Add optional fields
            if kwargs.get('assigned_to') or self._config.assigned_to:
                patch_doc.append({
                    "op": "add",
                    "path": "/fields/System.AssignedTo",
                    "value": kwargs.get('assigned_to', self._config.assigned_to)
                })

            if kwargs.get('area_path') or self._config.area_path:
                patch_doc.append({
                    "op": "add",
                    "path": "/fields/System.AreaPath",
                    "value": kwargs.get('area_path', self._config.area_path)
                })

            if objective:
                patch_doc.append({
                    "op": "add",
                    "path": "/fields/System.Description",
                    "value": objective
                })

            result = self._client.patch(
                "_apis/wit/workitems/$Test Case",
                data=patch_doc
            )

            return result.get('id')
        except Exception as e:
            print(f"Error creating test case: {e}")
            return None

    def update_test_case(
        self,
        test_case_id: int,
        fields: Dict[str, Any]
    ) -> bool:
        """Update a test case."""
        try:
            patch_doc = []
            for field, value in fields.items():
                patch_doc.append({
                    "op": "replace",
                    "path": f"/fields/{field}",
                    "value": value
                })

            self._client.patch(
                f"_apis/wit/workitems/{test_case_id}",
                data=patch_doc
            )
            return True
        except Exception as e:
            print(f"Error updating test case {test_case_id}: {e}")
            return False

    def get_test_case(self, test_case_id: int) -> Optional[Dict[str, Any]]:
        """Get a test case by ID."""
        try:
            return self._client.get(f"_apis/wit/workitems/{test_case_id}")
        except Exception as e:
            print(f"Error getting test case {test_case_id}: {e}")
            return None

    def _build_steps_xml(self, steps: List[Dict[str, str]]) -> str:
        """Build XML for test steps."""
        if not steps:
            return ""

        xml_parts = [f'<steps id="0" last="{len(steps)}">']

        for idx, step in enumerate(steps, start=1):
            action = self._escape_xml(step.get('action', ''))
            expected = self._escape_xml(step.get('expected', ''))

            xml_parts.append(f'  <step id="{idx}" type="ValidateStep">')
            xml_parts.append(
                f'    <parameterizedString isformatted="true">'
                f'&lt;DIV&gt;&lt;P&gt;{action}&lt;/P&gt;&lt;/DIV&gt;'
                f'</parameterizedString>'
            )
            xml_parts.append(
                f'    <parameterizedString isformatted="true">'
                f'&lt;DIV&gt;&lt;P&gt;{expected}&lt;/P&gt;&lt;/DIV&gt;'
                f'</parameterizedString>'
            )
            xml_parts.append('    <description/>')
            xml_parts.append('  </step>')

        xml_parts.append('</steps>')
        return '\n'.join(xml_parts)

    @staticmethod
    def _escape_xml(text: str) -> str:
        """Escape special XML characters."""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&apos;'))
