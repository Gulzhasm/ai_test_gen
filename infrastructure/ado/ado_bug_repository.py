"""Azure DevOps Bug work item repository.

Creates Bug work items in ADO using the PATCH _apis/wit/workitems/$Bug endpoint.
Follows the same JSON Patch pattern as ADOTestCaseRepository.
"""
from typing import Optional

from core.domain.bug_report import BugReport
from core.interfaces.config_provider import IADOConfig
from .http_client import ADOHttpClient


class ADOBugRepository:
    """Creates and manages Bug work items in Azure DevOps."""

    def __init__(self, config: IADOConfig):
        self._config = config
        self._client = ADOHttpClient(
            organization=config.organization,
            project=config.project,
            pat=config.pat
        )

    def create_bug(
        self,
        bug: BugReport,
        repro_steps_html: str,
        iteration_path: Optional[str] = None
    ) -> Optional[int]:
        """Create a Bug work item in ADO.

        Args:
            bug: BugReport domain object
            repro_steps_html: Pre-formatted HTML for ReproSteps field
            iteration_path: Optional ADO iteration path

        Returns:
            Work item ID if created, None on failure
        """
        try:
            patch_doc = [
                {"op": "add", "path": "/fields/System.Title", "value": bug.title},
                {"op": "add", "path": "/fields/Microsoft.VSTS.TCM.ReproSteps", "value": repro_steps_html},
            ]

            if self._config.area_path:
                patch_doc.append({
                    "op": "add",
                    "path": "/fields/System.AreaPath",
                    "value": self._config.area_path
                })

            if self._config.assigned_to:
                patch_doc.append({
                    "op": "add",
                    "path": "/fields/System.AssignedTo",
                    "value": self._config.assigned_to
                })

            if bug.severity:
                patch_doc.append({
                    "op": "add",
                    "path": "/fields/Microsoft.VSTS.Common.Severity",
                    "value": bug.severity
                })

            if iteration_path:
                # Iteration path must be a full ADO path (e.g., "Env\Sprint 42")
                # If it doesn't contain a backslash, prepend the project name
                if '\\' not in iteration_path:
                    iteration_path = f"{self._config.project}\\{iteration_path}"
                patch_doc.append({
                    "op": "add",
                    "path": "/fields/System.IterationPath",
                    "value": iteration_path
                })

            result = self._client.patch(
                "_apis/wit/workitems/$Bug",
                data=patch_doc
            )

            return result.get('id')
        except Exception as e:
            print(f"  Error creating bug: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    print(f"  ADO Response: {e.response.text[:500]}")
                except Exception:
                    pass
            return None

    def link_bug_to_story(self, bug_id: int, story_id: int) -> bool:
        """Link a bug work item to a parent story.

        Uses System.LinkTypes.Hierarchy-Reverse (child -> parent).
        """
        try:
            patch_doc = [{
                "op": "add",
                "path": "/relations/-",
                "value": {
                    "rel": "System.LinkTypes.Hierarchy-Reverse",
                    "url": (
                        f"https://dev.azure.com/{self._config.organization}/"
                        f"{self._config.project}/_apis/wit/workitems/{story_id}"
                    ),
                    "attributes": {"comment": "Linked during bug creation"}
                }
            }]

            self._client.patch(
                f"_apis/wit/workitems/{bug_id}",
                data=patch_doc
            )
            return True
        except Exception as e:
            print(f"  Error linking bug {bug_id} to story {story_id}: {e}")
            return False

    def get_bug_url(self, bug_id: int) -> str:
        """Get the ADO web URL for a bug work item."""
        return (
            f"https://dev.azure.com/{self._config.organization}/"
            f"{self._config.project}/_workitems/edit/{bug_id}"
        )
