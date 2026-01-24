"""
Test Plan and Test Suite Finder Module
Discovers ADO Test Plans and Test Suites for a given user story.
"""
from typing import Dict, List, Optional, Tuple
import requests
from src.ado_client import ADOClient
import config


class TestPlanFinder:
    """Finds Test Plans and Test Suites in ADO for a given user story."""
    
    def __init__(self, client: ADOClient):
        self.client = client
        self.base_url = client.base_url
    
    def find_plan_for_story(self, story_id: int, story_title: str) -> Optional[int]:
        """Find Test Plan that contains a suite matching the story ID.
        
        Strategy:
        1. First try to find plan with story ID in plan name
        2. If not found, check all plans for suites containing story ID
        3. Return the plan that contains a matching suite
        
        Args:
            story_id: The user story ID
            story_title: The user story title (for better matching)
            
        Returns:
            Test Plan ID if found, None otherwise
        """
        # List all test plans in the project
        url = f"{self.base_url}/_apis/testplan/plans?api-version=7.1-preview.1"
        
        try:
            response = requests.get(url, headers=self.client.headers)
            response.raise_for_status()
            
            data = response.json()
            plans = data.get('value', [])
            
            if not plans:
                print(f"  No test plans found in project")
                return None
            
            story_id_str = str(story_id)
            
            # First, try exact match on story ID in plan name
            for plan in plans:
                plan_name = plan.get('name', '')
                plan_id = plan.get('id')
                
                if story_id_str in plan_name:
                    print(f"  ✓ Found matching test plan: {plan_id} - {plan_name}")
                    return plan_id
            
            # If no plan name match, check suites within each plan
            print(f"  Plan name doesn't contain '{story_id_str}', checking suites in all plans...")
            for plan in plans:
                plan_id = plan.get('id')
                plan_name = plan.get('name', '')
                
                # Check if this plan has a suite with story ID
                suite_id, suite_name = self.find_suite_for_story(plan_id, story_id, story_title)
                if suite_id:
                    print(f"  ✓ Found plan containing matching suite: {plan_id} - {plan_name}")
                    return plan_id
            
            print(f"  ✗ No matching test plan found for story {story_id}")
            return None
            
        except Exception as e:
            print(f"  Error finding test plan: {e}")
            return None
    
    def find_suite_for_story(self, plan_id: int, story_id: int, story_title: str) -> Tuple[Optional[int], Optional[str]]:
        """Find Test Suite that matches the story ID (and optionally story title).
        
        SAFETY: Finds existing suites only - never creates or renames anything.
        Prefers suites that contain both story ID and title, but accepts suites with just story ID.
        
        Args:
            plan_id: The test plan ID
            story_id: The user story ID
            story_title: The user story title (for better matching)
            
        Returns:
            Test Suite ID if match found, None otherwise
        """
        # List all test suites in the plan
        # Try different API versions if one fails
        api_versions = ['7.1-preview.3', '7.1', '6.0-preview.2']
        suites = []
        
        for api_version in api_versions:
            url = f"{self.base_url}/_apis/testplan/Plans/{plan_id}/Suites?api-version={api_version}"
            
            try:
                response = requests.get(url, headers=self.client.headers)
                if response.status_code == 404:
                    # Plan might not exist or have no suites, skip silently
                    continue
                response.raise_for_status()
                
                data = response.json()
                suites = data.get('value', [])
                break  # Success, exit loop
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    # Plan doesn't exist or has no suites, try next API version or skip
                    continue
                raise  # Re-raise other HTTP errors
        
        if not suites:
            # No suites found (plan might not exist or have no suites)
            return None, None
        
        story_id_str = str(story_id)
        story_title_lower = story_title.lower()
        
        # First, try to find suite with BOTH story ID AND story title (best match)
        best_match_id = None
        best_match_name = None
        best_score = 0
        
        for suite in suites:
            suite_name = suite.get('name', '')
            suite_id = suite.get('id')
            suite_name_lower = suite_name.lower()
            
            score = 0
            # Must have story ID
            if story_id_str in suite_name:
                score += 10
            else:
                continue  # Skip suites without story ID
            
            # Bonus if also contains story title
            if story_title_lower in suite_name_lower:
                score += 5
            
            if score > best_score:
                best_score = score
                best_match_id = suite_id
                best_match_name = suite_name
        
        if best_match_id:
            print(f"  ✓ Found matching test suite: {best_match_id} - {best_match_name}")
            return best_match_id, best_match_name
        
        print(f"  ✗ No matching test suite found for story {story_id} in plan {plan_id}")
        print(f"    Required: Suite name must contain story ID '{story_id_str}'")
        return None, None
    
    def list_all_suites_for_plan(self, plan_id: int) -> List[Dict]:
        """List all test suites in a plan for error reporting.
        
        Args:
            plan_id: The test plan ID
            
        Returns:
            List of suite dictionaries with 'id' and 'name'
        """
        url = f"{self.base_url}/_apis/testplan/Plans/{plan_id}/Suites?api-version=7.1-preview.3"
        
        try:
            response = requests.get(url, headers=self.client.headers)
            response.raise_for_status()
            
            data = response.json()
            suites = data.get('value', [])
            
            return [{'id': s.get('id'), 'name': s.get('name', '')} for s in suites]
        except Exception as e:
            print(f"  Error listing suites: {e}")
            return []
    
    def find_plan_and_suite(self, story_id: int, story_title: str) -> Tuple[Optional[int], Optional[int], Optional[str], List[Dict], List[Dict]]:
        """Find both Test Plan and Test Suite for a story.
        
        SAFETY: Finds existing plans/suites only - never creates or renames anything.
        Suite must contain story ID; prefers suites that also contain story title.
        
        Returns:
            Tuple of (plan_id, suite_id, suite_name, candidate_plans, candidate_suites)
            Returns (None, None, None, plans, suites) if match not found for error reporting
        """
        plan_id = self.find_plan_for_story(story_id, story_title)
        candidate_plans = []
        candidate_suites = []
        suite_name = None
        
        if not plan_id:
            # List all plans for error reporting
            url = f"{self.base_url}/_apis/testplan/plans?api-version=7.1-preview.1"
            try:
                response = requests.get(url, headers=self.client.headers)
                response.raise_for_status()
                data = response.json()
                candidate_plans = [{'id': p.get('id'), 'name': p.get('name', '')} for p in data.get('value', [])]
            except:
                pass
            return None, None, None, candidate_plans, []
        
        suite_id, suite_name = self.find_suite_for_story(plan_id, story_id, story_title)
        if not suite_id:
            # List all suites in the plan for error reporting
            candidate_suites = self.list_all_suites_for_plan(plan_id)
        
        return plan_id, suite_id, suite_name, candidate_plans, candidate_suites
