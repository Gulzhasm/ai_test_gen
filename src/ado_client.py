"""
Azure DevOps API Client Module
Handles all interactions with Azure DevOps REST API.
"""
import base64
import re
from typing import Dict, List, Optional, Any
import requests
from bs4 import BeautifulSoup

import config


class ADOClient:
    """Client for interacting with Azure DevOps REST API."""
    
    def __init__(self):
        if not config.ADO_PAT:
            raise ValueError("ADO_PAT environment variable is required")
        self.base_url = config.BASE_URL
        self.headers = self._get_auth_headers()
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for ADO API."""
        credentials = base64.b64encode(f":{config.ADO_PAT}".encode()).decode()
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {credentials}'
        }
    
    def normalize_html_to_text(self, html_content: str) -> str:
        """Convert HTML to plain text, preserving bullet order, line breaks, and structure."""
        if not html_content:
            return ""
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Convert lists to bullet points
        for ul in soup.find_all(['ul', 'ol']):
            for li in ul.find_all('li', recursive=False):
                text = li.get_text().strip()
                if not text.startswith('•') and not text.startswith('-'):
                    li.insert(0, '• ')
        
        text = soup.get_text(separator='\n')
        
        # Clean up excessive whitespace while preserving structure
        lines = []
        for line in text.split('\n'):
            cleaned = line.strip()
            if cleaned:
                lines.append(cleaned)
        
        return '\n'.join(lines)
    
    def extract_story_data(self, story_id: int) -> Dict[str, str]:
        """Extract User Story data from ADO including description, acceptance criteria, and QA Prep subtask.
        
        Checks both the AcceptanceCriteria field and comments section for AC.
        Retrieves QA Prep subtask titled "Story {StoryId}: QA Prep".
        
        Returns:
            Dict with story_id, title, description_text, acceptance_criteria_text, qa_prep_text
        """
        url = f"{self.base_url}/_apis/wit/workitems/{story_id}?$expand=all&api-version=7.1-preview.3"
        
        print(f"Extracting story {story_id} from ADO...")
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        data = response.json()
        fields = data.get('fields', {})
        
        title = fields.get('System.Title', '')
        description_html = fields.get('System.Description', '')
        acceptance_criteria_html = fields.get('Microsoft.VSTS.Common.AcceptanceCriteria', '')
        
        description_text = self.normalize_html_to_text(description_html)
        acceptance_criteria_text = self.normalize_html_to_text(acceptance_criteria_html)
        
        # Check comments section ONLY if AcceptanceCriteria field is empty
        # Use FIRST COMMENT ONLY that contains acceptance criteria
        if not acceptance_criteria_text or not acceptance_criteria_text.strip():
            comments_ac = self._extract_ac_from_comments(story_id)
            if comments_ac:
                acceptance_criteria_text = comments_ac
                print(f"  Using AC from first comment (AC field was empty)")
        else:
            print(f"  Using AC from dedicated field (ignoring comments)")
        
        # Retrieve QA Prep subtask
        qa_prep_text = self.retrieve_qa_prep_subtask(story_id)
        
        print(f"✓ Extracted story: {title}")
        print(f"  Description: {len(description_text)} chars")
        print(f"  Acceptance Criteria: {len(acceptance_criteria_text)} chars")
        if qa_prep_text:
            print(f"  QA Prep: {len(qa_prep_text)} chars")
        else:
            print(f"  QA Prep: Not found")
        
        return {
            'story_id': story_id,
            'title': title,
            'description_text': description_text,
            'acceptance_criteria_text': acceptance_criteria_text,
            'qa_prep_text': qa_prep_text
        }
    
    def retrieve_qa_prep_subtask(self, story_id: int) -> str:
        """Retrieve QA Prep subtask titled 'Story {StoryId}: QA Prep' from ADO.
        
        The QA Prep subtask is authoritative for test design intent, coverage depth, and edge cases.
        
        Search strategy:
        1. Try exact title match: "Story {story_id}: QA Prep"
        2. Try contains search: title contains story_id and "QA Prep"
        3. Try searching child work items of the parent story
        
        Args:
            story_id: The user story ID
            
        Returns:
            QA Prep content as plain text, or empty string if not found
        """
        qa_prep_title_exact = f"Story {story_id}: QA Prep"
        story_id_str = str(story_id)
        
        url = f"{self.base_url}/_apis/wit/wiql?api-version=7.1"
        
        # Strategy 1: Try exact title match
        try:
            wiql_query = {
                'query': (
                    f"Select [System.Id], [System.Title], [System.Description] "
                    f"From WorkItems "
                    f"Where [System.Title] = '{qa_prep_title_exact}' "
                    f"And [System.WorkItemType] = 'Sub-task'"
                )
            }
            
            response = requests.post(url, headers=self.headers, json=wiql_query)
            response.raise_for_status()
            
            data = response.json()
            work_items = data.get('workItems', [])
            
            if work_items:
                work_item_id = work_items[0]['id']
                return self._fetch_qa_prep_content(work_item_id, qa_prep_title_exact)
        except Exception as e:
            pass  # Try next strategy
        
        # Strategy 2: Try contains search (more flexible)
        try:
            wiql_query = {
                'query': (
                    f"Select [System.Id], [System.Title], [System.Description] "
                    f"From WorkItems "
                    f"Where [System.Title] Contains '{story_id_str}' "
                    f"And [System.Title] Contains 'QA Prep' "
                    f"And [System.WorkItemType] = 'Sub-task'"
                )
            }
            
            response = requests.post(url, headers=self.headers, json=wiql_query)
            response.raise_for_status()
            
            data = response.json()
            work_items = data.get('workItems', [])
            
            if work_items:
                # Find the one that best matches our pattern
                for item in work_items:
                    work_item_id = item['id']
                    # Fetch to check title
                    item_url = f"{self.base_url}/_apis/wit/workitems/{work_item_id}?api-version=7.1"
                    item_response = requests.get(item_url, headers=self.headers)
                    if item_response.status_code == 200:
                        item_data = item_response.json()
                        item_title = item_data.get('fields', {}).get('System.Title', '')
                        # Check if it matches our pattern (contains story ID and "QA Prep")
                        if story_id_str in item_title and 'qa prep' in item_title.lower():
                            return self._fetch_qa_prep_content(work_item_id, item_title)
        except Exception as e:
            pass  # Try next strategy
        
        # Strategy 3: Try searching child work items of the parent story
        try:
            # Get child work items of the story using $expand=relations
            story_url = f"{self.base_url}/_apis/wit/workitems/{story_id}?$expand=relations&api-version=7.1"
            story_response = requests.get(story_url, headers=self.headers)
            if story_response.status_code == 200:
                story_data = story_response.json()
                relations = story_data.get('relations', [])
                
                # Debug: print relation types found
                relation_types_found = [r.get('rel', '') for r in relations]
                
                # Look for child relations - try both forward and reverse hierarchy links
                for relation in relations:
                    rel_type = relation.get('rel', '')
                    # Child link can be Hierarchy-Forward (parent->child) or Hierarchy-Reverse (child->parent from child's perspective)
                    if 'Hierarchy' in rel_type:
                        child_url = relation.get('url', '')
                        if child_url:
                            # Extract work item ID from URL
                            child_id_match = re.search(r'/workitems/(\d+)', child_url)
                            if child_id_match:
                                child_id = int(child_id_match.group(1))
                                # Fetch child item to check if it's QA Prep
                                child_item_url = f"{self.base_url}/_apis/wit/workitems/{child_id}?api-version=7.1"
                                child_item_response = requests.get(child_item_url, headers=self.headers)
                                if child_item_response.status_code == 200:
                                    child_item_data = child_item_response.json()
                                    child_fields = child_item_data.get('fields', {})
                                    child_title = child_fields.get('System.Title', '')
                                    child_type = child_fields.get('System.WorkItemType', '')
                                    
                                    # Check if it's a Sub-task with QA Prep in title (case-insensitive)
                                    if child_type == 'Sub-task':
                                        child_title_lower = child_title.lower()
                                        if story_id_str in child_title and ('qa prep' in child_title_lower or 'qa_prep' in child_title_lower):
                                            return self._fetch_qa_prep_content(child_id, child_title)
        except Exception as e:
            pass  # Try next strategy or fail gracefully
        
        # Strategy 4: Search all subtasks/tasks in project and filter by title pattern
        try:
            # Try Sub-task first
            for work_item_type in ['Sub-task', 'Task']:
                wiql_query = {
                    'query': (
                        f"Select [System.Id], [System.Title] "
                        f"From WorkItems "
                        f"Where [System.WorkItemType] = '{work_item_type}' "
                        f"And [System.Title] Contains '{story_id_str}'"
                    )
                }
                
                response = requests.post(url, headers=self.headers, json=wiql_query)
                response.raise_for_status()
                
                data = response.json()
                work_items = data.get('workItems', [])
                
                if work_items:
                    # Fetch details for each candidate to check title
                    for item in work_items:
                        work_item_id = item['id']
                        item_url = f"{self.base_url}/_apis/wit/workitems/{work_item_id}?api-version=7.1"
                        item_response = requests.get(item_url, headers=self.headers)
                        if item_response.status_code == 200:
                            item_data = item_response.json()
                            item_title = item_data.get('fields', {}).get('System.Title', '')
                            item_type = item_data.get('fields', {}).get('System.WorkItemType', '')
                            
                            # Check if it matches QA Prep pattern (case-insensitive, flexible)
                            item_title_lower = item_title.lower()
                            if (story_id_str in item_title and 
                                ('qa prep' in item_title_lower or 'qa_prep' in item_title_lower or 'qa-prep' in item_title_lower)):
                                return self._fetch_qa_prep_content(work_item_id, item_title)
        except Exception as e:
            pass  # Fail gracefully
        
        # If all strategies fail
        print(f"  QA Prep subtask not found: '{qa_prep_title_exact}'")
        print(f"  Tried: exact match, contains search, child work items, and project-wide subtask search")
        return ""
    
    def _fetch_qa_prep_content(self, work_item_id: int, title: str) -> str:
        """Fetch QA Prep content from a work item.
        
        Args:
            work_item_id: The work item ID
            title: The work item title (for logging)
            
        Returns:
            QA Prep content as plain text, or empty string if error
        """
        try:
            # Fetch the work item details
            item_url = f"{self.base_url}/_apis/wit/workitems/{work_item_id}?$expand=all&api-version=7.1-preview.3"
            item_response = requests.get(item_url, headers=self.headers)
            item_response.raise_for_status()
            
            item_data = item_response.json()
            item_fields = item_data.get('fields', {})
            description_html = item_fields.get('System.Description', '')
            
            qa_prep_text = self.normalize_html_to_text(description_html)
            print(f"  ✓ Found QA Prep subtask: {work_item_id} - {title}")
            
            # Extract only the "QA Planning Summary for this Work Item" section
            summary_section = self._extract_qa_planning_summary(qa_prep_text)
            if summary_section:
                return summary_section
            else:
                # If section not found, return full text (fallback)
                print(f"  Warning: Could not find 'QA Planning Summary for this Work Item' section, using full description")
                return qa_prep_text
            
        except Exception as e:
            print(f"  Warning: Error fetching QA Prep content from work item {work_item_id}: {e}")
            return ""
    
    def _extract_qa_planning_summary(self, qa_prep_text: str) -> str:
        """Extract the 'QA Planning Summary for this Work Item' section from QA Prep text.
        
        Args:
            qa_prep_text: Full QA Prep description text
            
        Returns:
            The QA Planning Summary section, or empty string if not found
        """
        if not qa_prep_text:
            return ""
        
        # Look for the section header
        section_marker = "QA Planning Summary for this Work Item"
        lines = qa_prep_text.split('\n')
        
        # Find the section start
        start_idx = None
        for i, line in enumerate(lines):
            if section_marker.lower() in line.lower():
                start_idx = i
                break
        
        if start_idx is None:
            return ""
        
        # Extract from section start to end (or next major section)
        # Look for common section markers that might indicate end
        end_markers = [
            "Testing will focus",
            "Functional dependencies",
            "Accessibility testing",
            "Tests will be executed"
        ]
        
        summary_lines = []
        for i in range(start_idx, len(lines)):
            line = lines[i].strip()
            # Stop if we hit another major section (but include the first line of that section)
            if i > start_idx and any(marker.lower() in line.lower() for marker in end_markers if marker != "Testing will focus"):
                break
            summary_lines.append(line)
        
        return '\n'.join(summary_lines).strip()
    
    def _extract_ac_from_comments(self, story_id: int) -> str:
        """Extract acceptance criteria from comments section.
        
        Returns ONLY the FIRST comment that contains acceptance criteria patterns.
        Ignores all subsequent comments to avoid irrelevant content.
        """
        try:
            url = f"{self.base_url}/_apis/wit/workitems/{story_id}/comments?api-version=7.1-preview.3"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code != 200:
                return ""
            
            data = response.json()
            comments = data.get('comments', [])
            
            # Sort comments by creation date (oldest first) to get the first AC comment
            # Comments are typically returned in reverse chronological order
            sorted_comments = sorted(comments, key=lambda x: x.get('createdDate', ''))
            
            # Find the FIRST comment that looks like acceptance criteria
            for comment in sorted_comments:
                text = comment.get('text', '')
                if text:
                    normalized = self.normalize_html_to_text(text)
                    # Check if comment contains AC-like content
                    if self._looks_like_ac(normalized):
                        # Return only the first matching comment
                        return normalized
            
            return ""
        except Exception as e:
            print(f"  Warning: Could not extract AC from comments: {e}")
            return ""
    
    def _looks_like_ac(self, text: str) -> bool:
        """Check if text looks like acceptance criteria.
        
        Filters out conversational comments and only matches structured AC content.
        """
        text_lower = text.lower().strip()
        
        # Skip very short text (likely not AC)
        if len(text_lower) < 20:
            return False
        
        # Skip conversational patterns
        conversational_patterns = [
            'thank you', 'thanks', 'hi ', 'hello ', '@', 'very helpful',
            'i agree', 'i think', 'copy-paste', 'typo', 'updated the',
            'based on all your', 'clarifications', 'regards', 'best regards'
        ]
        if any(pattern in text_lower for pattern in conversational_patterns):
            return False
        
        # Look for AC indicators - must have strong indicators
        strong_ac_indicators = [
            'acceptance criteria', 'acceptance criterion', 'ac:',
            'user can', 'user should', 'system must', 'system should',
            'verify that', 'ensure that'
        ]
        
        # Also check for bullet points or numbered lists (structured format)
        has_bullets = text.startswith('•') or text.startswith('-') or bool(re.match(r'^\d+[\.\)]\s*', text))
        
        # Must have strong indicators OR structured format with AC keywords
        has_strong_indicator = any(indicator in text_lower for indicator in strong_ac_indicators)
        
        if has_strong_indicator:
            return True
        
        # If structured format, check for AC-related keywords
        if has_bullets:
            ac_keywords = ['displays', 'shows', 'contains', 'includes', 'appears', 'opens', 'closes']
            return any(keyword in text_lower for keyword in ac_keywords)
        
        return False
    
    def parse_acceptance_criteria(self, ac_text: str) -> List[str]:
        """Parse acceptance criteria into individual bullets, preserving order."""
        if not ac_text:
            return []
        
        lines = ac_text.split('\n')
        criteria = []
        current = []
        
        for line in lines:
            line = line.strip()
            if not line:
                if current:
                    criteria.append('\n'.join(current))
                    current = []
                continue
            
            # Check if it's a new bullet point
            if line.startswith('•') or line.startswith('-') or re.match(r'^\d+[\.\)]\s*', line):
                if current:
                    criteria.append('\n'.join(current))
                # Remove bullet marker
                cleaned = re.sub(r'^[•\-\d+\.\)]\s*', '', line)
                current = [cleaned]
            else:
                if current:
                    current.append(line)
                else:
                    # First line without bullet - treat as new criterion
                    current = [line]
        
        if current:
            criteria.append('\n'.join(current))
        
        return [c.strip() for c in criteria if c.strip()]
    
    def retrieve_test_cases_for_story(self, story_id: int) -> List[Dict[str, any]]:
        """Retrieve all test cases for a given story ID from ADO.
        
        Uses WIQL (Work Item Query Language) to find test cases with titles
        containing the story ID.
        
        Args:
            story_id: The user story ID to search for
            
        Returns:
            List of dictionaries containing test case information:
            [
                {
                    'id': <test_case_id>,
                    'title': <test_case_title>,
                    'state': <state>,
                    'url': <work_item_url>
                },
                ...
            ]
        """
        # Query ADO using WIQL to find test cases for this story
        wiql_query = {
            'query': (
                f"Select [System.Id], [System.Title], [System.State] "
                f"From WorkItems "
                f"Where [System.WorkItemType]='Test Case' "
                f"And [System.Title] Contains '{story_id}' "
                f"Order By [System.Id] Desc"
            )
        }
        
        url = f"{self.base_url}/_apis/wit/wiql?api-version=7.1"
        
        print(f"Querying ADO for test cases containing '{story_id}'...")
        response = requests.post(url, headers=self.headers, json=wiql_query)
        response.raise_for_status()
        
        data = response.json()
        work_items = data.get('workItems', [])
        
        if not work_items:
            print(f"  No test cases found for story {story_id}")
            return []
        
        # Get detailed information for each test case
        test_cases = []
        work_item_ids = [wi['id'] for wi in work_items]
        
        # Batch fetch work items (ADO supports up to 200 IDs per request)
        batch_size = 200
        for i in range(0, len(work_item_ids), batch_size):
            batch_ids = work_item_ids[i:i + batch_size]
            ids_str = ','.join(map(str, batch_ids))
            
            url = f"{self.base_url}/_apis/wit/workitems?ids={ids_str}&api-version=7.1"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            batch_data = response.json()
            for work_item in batch_data.get('value', []):
                fields = work_item.get('fields', {})
                test_case = {
                    'id': work_item.get('id'),
                    'title': fields.get('System.Title', 'N/A'),
                    'state': fields.get('System.State', 'N/A'),
                    'work_item_type': fields.get('System.WorkItemType', 'N/A'),
                    'url': work_item.get('url', '')
                }
                test_cases.append(test_case)
        
        # Sort by ID descending (newest first)
        test_cases.sort(key=lambda x: x['id'], reverse=True)
        
        print(f"  Found {len(test_cases)} test case(s)")
        return test_cases
    
    def verify_test_cases_exist(self, story_id: int, expected_test_case_ids: List[int] = None) -> Dict[str, any]:
        """Verify that test cases exist in ADO for a given story ID.
        
        Args:
            story_id: The user story ID to verify
            expected_test_case_ids: Optional list of expected test case IDs to verify
            
        Returns:
            Dictionary with verification results:
            {
                'story_id': <story_id>,
                'total_found': <count>,
                'test_cases': [<list of test cases>],
                'verified_ids': [<list of verified IDs>],
                'missing_ids': [<list of missing IDs if expected_test_case_ids provided>],
                'all_exist': <bool>
            }
        """
        test_cases = self.retrieve_test_cases_for_story(story_id)
        
        result = {
            'story_id': story_id,
            'total_found': len(test_cases),
            'test_cases': test_cases,
            'verified_ids': [tc['id'] for tc in test_cases],
            'missing_ids': [],
            'all_exist': True
        }
        
        # If expected IDs provided, check which ones are missing
        if expected_test_case_ids:
            found_ids = set(result['verified_ids'])
            expected_set = set(expected_test_case_ids)
            result['missing_ids'] = list(expected_set - found_ids)
            result['all_exist'] = len(result['missing_ids']) == 0
        
        return result
    def fetch_story_comprehensive(self, story_id: int) -> Dict[str, Any]:
        """Fetch story data in comprehensive format for test generation.

        Returns structured data with parsed acceptance criteria as a list.

        Args:
            story_id: The user story ID

        Returns:
            Dictionary with:
            {
                'story_id': <int>,
                'title': <str>,
                'description': <str>,
                'acceptance_criteria': [<list of AC bullets as strings>],
                'qa_prep': <str>
            }
        """
        # Use existing extract_story_data method
        story_data = self.extract_story_data(story_id)

        # Parse acceptance criteria into list of bullets
        ac_text = story_data.get('acceptance_criteria_text', '')
        ac_list = self.parse_acceptance_criteria(ac_text)

        # Return in comprehensive format
        return {
            'story_id': story_data['story_id'],
            'title': story_data['title'],
            'description': story_data['description_text'],
            'acceptance_criteria': ac_list,
            'qa_prep': story_data.get('qa_prep_text', '')
        }

    def update_work_item_field(self, work_item_id: int, field_name: str, field_value: str, operation: str = "replace") -> Optional[Dict[str, Any]]:
        """Update a field in a work item using JSON Patch operation.

        Args:
            work_item_id: The ID of the work item to update
            field_name: The name of the field to update (e.g., 'System.Description')
            field_value: The new value for the field
            operation: The patch operation (default: 'replace')

        Returns:
            Updated work item data if successful, None otherwise
        """
        url = f"{self.base_url}/_apis/wit/workitems/{work_item_id}?api-version=7.1"
        
        patch_document = [
            {
                "op": operation,
                "path": f"/fields/{field_name}",
                "value": field_value
            }
        ]
        
        headers_patch = self.headers.copy()
        headers_patch['Content-Type'] = 'application/json-patch+json'
        
        try:
            response = requests.patch(url, headers=headers_patch, json=patch_document)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    error_msg += f" - {error_detail.get('message', e.response.text[:200])}"
                except:
                    error_msg += f" - {e.response.text[:200]}"
            print(f"    Error updating work item {work_item_id} field {field_name}: {error_msg}")
            return None
