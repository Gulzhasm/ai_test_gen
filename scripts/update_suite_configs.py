#!/usr/bin/env python3
"""
Bulk update test suite configurations in ADO.

Keeps only the specified configuration and removes all others from
each story's test suite. Also updates individual test case point assignments.

Usage:
    # Dry run (preview changes without applying)
    python scripts/update_suite_configs.py \\
        --project env-quickdraw \\
        --stories 270171,270172,270471 \\
        --keep-config "MS Store-Win11-Desktop" \\
        --dry-run

    # Apply changes
    python scripts/update_suite_configs.py \\
        --project env-quickdraw \\
        --stories 270171,270172,270471 \\
        --keep-config "MS Store-Win11-Desktop"
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts._shared import create_base_parser, load_project_config, create_ado_client
from infrastructure.ado.http_client import ADOHttpClient


def get_all_configurations(client: ADOHttpClient) -> list[dict]:
    """Fetch all test configurations in the project."""
    result = client.get("_apis/testplan/configurations")
    return result.get('value', [])


def find_suite_for_story(client: ADOHttpClient, story_id: int, plans_cache: list[dict]) -> dict | None:
    """Find the test suite matching a story ID.

    Args:
        client: ADO HTTP client
        story_id: Story work item ID
        plans_cache: Cached list of test plans

    Returns:
        Dict with suite_id, plan_id, name or None if not found
    """
    prefix = f"{story_id} :"

    for plan in plans_cache:
        plan_id = plan['id']
        try:
            suites = client.get(f"_apis/testplan/Plans/{plan_id}/suites")
            for suite in suites.get('value', []):
                if suite.get('name', '').startswith(prefix):
                    return {
                        'suite_id': suite['id'],
                        'plan_id': plan_id,
                        'name': suite['name']
                    }
        except Exception:
            continue

    return None


def get_suite_details(client: ADOHttpClient, plan_id: int, suite_id: int) -> dict:
    """Get full suite details including configurations."""
    return client.get(f"_apis/testplan/Plans/{plan_id}/suites/{suite_id}")


def update_suite_configurations(
    client: ADOHttpClient,
    plan_id: int,
    suite_id: int,
    keep_configs: list[dict]
) -> bool:
    """Update suite default configurations to only keep specified configs.

    Args:
        client: ADO HTTP client
        plan_id: Test plan ID
        suite_id: Test suite ID
        keep_configs: List of configuration references to keep [{id, name}]

    Returns:
        True if successful
    """
    body = {
        "inheritDefaultConfigurations": False,
        "defaultConfigurations": [{"id": c["id"]} for c in keep_configs]
    }

    client.patch(
        f"_apis/testplan/Plans/{plan_id}/suites/{suite_id}",
        data=body,
        content_type='application/json'
    )
    return True


def update_test_case_configs(
    client: ADOHttpClient,
    plan_id: int,
    suite_id: int,
    keep_config_ids: list[int]
) -> int:
    """Update individual test case point assignments in a suite.

    Args:
        client: ADO HTTP client
        plan_id: Test plan ID
        suite_id: Test suite ID
        keep_config_ids: List of configuration IDs to keep

    Returns:
        Number of test cases updated
    """
    # Get all test cases in the suite
    result = client.get(
        f"_apis/testplan/Plans/{plan_id}/Suites/{suite_id}/TestCase"
    )
    test_cases = result.get('value', [])

    if not test_cases:
        return 0

    # Build update payload - set each test case to only the kept configs
    update_payload = []
    for tc in test_cases:
        work_item = tc.get('workItem', {})
        tc_id = work_item.get('id')
        if tc_id:
            update_payload.append({
                "workItem": {"id": tc_id},
                "pointAssignments": [
                    {"configurationId": cid} for cid in keep_config_ids
                ]
            })

    if not update_payload:
        return 0

    # PATCH test cases with updated configurations
    client.patch(
        f"_apis/testplan/Plans/{plan_id}/Suites/{suite_id}/TestCase",
        data=update_payload,
        content_type='application/json'
    )

    return len(update_payload)


def parse_story_ids(stories_str: str) -> list[int]:
    """Parse comma-separated story IDs from CLI argument.

    Args:
        stories_str: Comma-separated story IDs (e.g., '270171,270172,270471')

    Returns:
        List of integer story IDs
    """
    ids = []
    for part in stories_str.split(','):
        part = part.strip()
        if part:
            try:
                ids.append(int(part))
            except ValueError:
                print(f"Warning: Skipping invalid story ID: '{part}'")
    return ids


def main():
    parser = create_base_parser("Bulk update test suite configurations in ADO")
    parser.add_argument(
        '--stories',
        required=True,
        help='Comma-separated story IDs (e.g., 270171,270172,270471)'
    )
    parser.add_argument(
        '--keep-config',
        required=True,
        help='Name of the configuration to KEEP (all others will be removed)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without applying them'
    )
    args = parser.parse_args()

    # Load project config and create client
    config = load_project_config(args.project)
    client = create_ado_client(config)

    # Parse story IDs
    story_ids = parse_story_ids(args.stories)
    if not story_ids:
        print("Error: No valid story IDs provided")
        sys.exit(1)

    keep_config_name = args.keep_config

    mode = "DRY RUN" if args.dry_run else "LIVE"
    print(f"{'=' * 70}")
    print(f"  Test Suite Configuration Update — {mode}")
    print(f"  Project: {config.project_id}")
    print(f"  Stories to process: {len(story_ids)}")
    print(f"  Keep config: {keep_config_name}")
    print(f"{'=' * 70}\n")

    # Step 1: Fetch all project configurations
    print("Fetching project configurations...")
    all_configs = get_all_configurations(client)
    print(f"  Found {len(all_configs)} total configurations:")

    # Find the config to keep and determine what to remove
    keep_configs = []
    remove_configs = []

    for cfg in all_configs:
        if cfg['name'] == keep_config_name:
            keep_configs.append({"id": cfg['id'], "name": cfg['name']})
            print(f"    ID={cfg['id']}: {cfg['name']}  [KEEP]")
        else:
            remove_configs.append(cfg)
            print(f"    ID={cfg['id']}: {cfg['name']}  [REMOVE]")

    keep_config_ids = [c['id'] for c in keep_configs]

    if not keep_configs:
        print(f"\nERROR: '{keep_config_name}' not found in project configurations!")
        print(f"Available: {[c['name'] for c in all_configs]}")
        sys.exit(1)

    print(f"\n  KEEP:   {[c['name'] for c in keep_configs]}")
    print(f"  REMOVE: {[c['name'] for c in remove_configs]}")

    # Step 2: Cache test plans (fetched once)
    print("\nFetching test plans...")
    plans = client.get("_apis/testplan/plans")
    plans_list = plans.get('value', [])
    print(f"  Found {len(plans_list)} test plans")

    # Step 3: Process each story
    print(f"\n{'—' * 70}")
    print("Processing stories...\n")

    updated = 0
    skipped = 0
    not_found = 0
    errors = 0

    for story_id in story_ids:
        print(f"  [{story_id}] ", end="")

        # Find the test suite
        suite_info = find_suite_for_story(client, story_id, plans_list)
        if not suite_info:
            print("No test suite found — SKIPPED")
            not_found += 1
            continue

        plan_id = suite_info['plan_id']
        suite_id = suite_info['suite_id']
        suite_name = suite_info['name']

        # Get current suite configurations
        try:
            suite_details = get_suite_details(client, plan_id, suite_id)
        except Exception as e:
            print(f"Error fetching suite details: {e}")
            errors += 1
            continue

        current_configs = suite_details.get('defaultConfigurations', []) or []
        inherits = suite_details.get('inheritDefaultConfigurations', False)

        if inherits:
            print(f"Suite inherits configs (plan={plan_id}, suite={suite_id})")

        # Check if already set to only the keep config
        current_names = [c.get('name', '?') for c in current_configs]
        already_correct = (
            not inherits and
            len(current_configs) == len(keep_configs) and
            all(c.get('name') == keep_config_name for c in current_configs)
        )

        if already_correct:
            print(f"Already {current_names} — SKIPPED")
            skipped += 1
            continue

        # Show what we'd change
        keep_names = [c['name'] for c in keep_configs]
        print(f"Suite: {suite_name[:50]}")
        print(f"         Current: {current_names}")
        print(f"         Target:  {keep_names}")

        if args.dry_run:
            print(f"         [DRY RUN] Would update suite + test cases")
            updated += 1
            continue

        # Apply changes
        try:
            # Update suite default configurations
            update_suite_configurations(client, plan_id, suite_id, keep_configs)

            # Update individual test case point assignments
            tc_count = update_test_case_configs(client, plan_id, suite_id, keep_config_ids)

            print(f"         UPDATED (suite configs + {tc_count} test cases)")
            updated += 1
        except Exception as e:
            print(f"         ERROR: {e}")
            errors += 1

    # Summary
    print(f"\n{'=' * 70}")
    print(f"  Summary ({mode})")
    print(f"{'=' * 70}")
    print(f"  Updated:   {updated}")
    print(f"  Skipped:   {skipped} (already correct)")
    print(f"  Not found: {not_found} (no test suite)")
    print(f"  Errors:    {errors}")
    print(f"  Total:     {len(story_ids)}")


if __name__ == '__main__':
    main()
