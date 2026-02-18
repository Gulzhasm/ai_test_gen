#!/usr/bin/env python3
"""
Fetch user stories from ADO board columns and create a CSV summary.

Queries specific board columns (Most Wanted, Development, Quality Assurance),
counts linked test cases per story, and outputs a CSV report.

Usage:
    python scripts/fetch_board_stories.py
"""
import csv
import os
import sys
from pathlib import Path
from urllib.parse import quote

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from infrastructure.ado.http_client import ADOHttpClient


def get_stories_from_board(client: ADOHttpClient, team: str, columns: list[str], area_path: str) -> list[dict]:
    """Fetch user stories from specific board columns using WIQL.

    Args:
        client: ADO HTTP client
        team: Team name (required for board column queries)
        columns: List of board column names to include
        area_path: Area path to filter by (e.g., 'Env\\ENV Kanda')

    Returns:
        List of work item stubs with 'id' and 'url'
    """
    columns_clause = ', '.join(f"'{col}'" for col in columns)

    wiql = f"""
    SELECT [System.Id], [System.Title], [System.BoardColumn]
    FROM WorkItems
    WHERE [System.WorkItemType] = 'User Story'
    AND [System.AreaPath] UNDER '{area_path}'
    AND [System.BoardColumn] IN ({columns_clause})
    AND [System.State] <> 'Removed'
    ORDER BY [System.BoardColumn] ASC, [System.Id] ASC
    """

    # Board column fields require team-scoped WIQL endpoint
    team_encoded = quote(team)
    result = client.post(
        f"{team_encoded}/_apis/wit/wiql",
        data={"query": wiql}
    )

    return result.get('workItems', [])


def fetch_story_details(client: ADOHttpClient, story_ids: list[int]) -> list[dict]:
    """Fetch work item details with relations in batches.

    Args:
        client: ADO HTTP client
        story_ids: List of work item IDs

    Returns:
        List of work item data dictionaries
    """
    all_items = []

    # ADO batch limit is 200
    for i in range(0, len(story_ids), 200):
        batch_ids = story_ids[i:i + 200]
        ids_str = ','.join(str(sid) for sid in batch_ids)

        result = client.get(
            "_apis/wit/workitems",
            params={
                "ids": ids_str,
                "$expand": "relations"
            }
        )

        all_items.extend(result.get('value', []))

    return all_items


def count_test_cases_from_relations(item: dict) -> int:
    """Count test cases linked via TestedBy relations.

    Args:
        item: Work item data with relations

    Returns:
        Number of linked test cases
    """
    count = 0
    relations = item.get('relations', []) or []
    for rel in relations:
        rel_type = rel.get('rel', '')
        # TestedBy-Forward = story is tested by test case
        if 'TestedBy' in rel_type:
            count += 1
    return count


def count_test_cases_from_suite(client: ADOHttpClient, story_id: int) -> int:
    """Count test cases by finding the story's test suite.

    Fallback method when TestedBy relations aren't populated.

    Args:
        client: ADO HTTP client
        story_id: Story work item ID

    Returns:
        Number of test cases in the suite
    """
    try:
        plans = client.get("_apis/testplan/plans")

        for plan in plans.get('value', []):
            plan_id = plan['id']
            suites = client.get(f"_apis/testplan/Plans/{plan_id}/suites")

            for suite in suites.get('value', []):
                if suite.get('name', '').startswith(f"{story_id} :"):
                    # Found the suite, count test cases
                    tc_result = client.get(
                        f"_apis/testplan/Plans/{plan_id}/Suites/{suite['id']}/TestCase"
                    )
                    return len(tc_result.get('value', []))
    except Exception as e:
        print(f"  Warning: Could not check test suite for {story_id}: {e}")

    return 0


def main():
    # ADO configuration
    org = os.getenv('ADO_ORG', 'cdpinc')
    project = os.getenv('ADO_PROJECT', 'Env')
    pat = os.getenv('ADO_PAT')
    area_path = os.getenv('ADO_AREA_PATH', 'Env\\ENV Kanda')
    team = 'ENV Kanda'

    if not pat:
        print("Error: ADO_PAT not set in environment")
        sys.exit(1)

    client = ADOHttpClient(organization=org, project=project, pat=pat)

    # Board columns to include
    target_columns = ['Most Wanted', 'Development', 'Quality Assurance']

    print(f"Fetching user stories from board columns: {', '.join(target_columns)}")
    print(f"Team: {team} | Area Path: {area_path}\n")

    # Step 1: Query board for user stories (filtered by area path)
    work_items = get_stories_from_board(client, team, target_columns, area_path)
    print(f"Found {len(work_items)} user stories")

    if not work_items:
        print("No stories found. Check board column names and team context.")
        return

    # Step 2: Fetch details with relations
    story_ids = [item['id'] for item in work_items]
    items = fetch_story_details(client, story_ids)

    # Step 3: Build story data and count test cases
    stories = []

    # Cache test plans for suite-based counting (fetched once)
    test_plans_cache = None

    for item in items:
        fields = item.get('fields', {})
        title = fields.get('System.Title', '')
        board_column = fields.get('System.BoardColumn', '')
        story_id = item.get('id', '')

        # Skip [Out of Scope] in title
        if '[Out of Scope]' in title:
            continue

        # Count test cases via relations first
        test_count = count_test_cases_from_relations(item)

        # If no relations found, try test suite lookup
        if test_count == 0:
            test_count = count_test_cases_from_suite(client, story_id)

        stories.append({
            'id': story_id,
            'title': title,
            'board_column': board_column,
            'test_case_count': test_count,
        })

        print(f"  {story_id}: {title[:60]}... ({test_count} tests)")

    # Sort by board column order, then by ID
    column_order = {col: idx for idx, col in enumerate(target_columns)}
    stories.sort(key=lambda s: (column_order.get(s['board_column'], 99), s['id']))

    # Print summary
    print(f"\n{'=' * 100}")
    print(f"{'Story ID':<10} {'Board Column':<22} {'# Tests':<10} {'Title'}")
    print(f"{'=' * 100}")

    for story in stories:
        print(f"{story['id']:<10} {story['board_column']:<22} {story['test_case_count']:<10} {story['title'][:55]}")

    # Write CSV
    output_path = project_root / 'output' / 'board_stories_summary.csv'
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['User Story Title', '# Test Cases', 'Tablet Testing Needed'])

        for story in stories:
            writer.writerow([
                f"{story['id']}: {story['title']}",
                story['test_case_count'],
                ''  # Empty - needs info from dev team
            ])

    print(f"\n{'=' * 100}")
    print(f"CSV saved to: {output_path}")
    print(f"Total stories: {len(stories)}")

    # Column breakdown
    for col in target_columns:
        col_stories = [s for s in stories if s['board_column'] == col]
        total_tests = sum(s['test_case_count'] for s in col_stories)
        print(f"  {col}: {len(col_stories)} stories, {total_tests} test cases")


if __name__ == '__main__':
    main()
