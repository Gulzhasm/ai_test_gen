"""
Configuration provider interfaces.

Abstracts configuration access to enable dependency injection and testability.
"""
from abc import ABC, abstractmethod


class IApplicationConfig(ABC):
    """Interface for application-specific configuration."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Application name."""

    @property
    @abstractmethod
    def app_type(self) -> str:
        """Application type (desktop, web, mobile, hybrid)."""

    @property
    @abstractmethod
    def prereq_template(self) -> str:
        """Template for prerequisite step."""

    @property
    @abstractmethod
    def launch_step(self) -> str:
        """Template for launch step."""

    @property
    @abstractmethod
    def launch_expected(self) -> str:
        """Expected result for launch step."""

    @property
    @abstractmethod
    def close_step(self) -> str:
        """Template for close step."""

    @property
    @abstractmethod
    def supported_platforms(self) -> list[str]:
        """List of supported platforms."""

    @property
    @abstractmethod
    def ui_surfaces(self) -> list[str]:
        """List of main UI surfaces."""

    @abstractmethod
    def get_entry_point(self, feature_name: str, hints: list[str] = None) -> str:
        """Determine entry point for a feature.

        Args:
            feature_name: Name of the feature
            hints: Optional hints from QA Prep

        Returns:
            Entry point name (e.g., 'File Menu', 'Settings')
        """

    @abstractmethod
    def requires_object_interaction(self, text: str) -> bool:
        """Check if text indicates object interaction is needed.

        Args:
            text: Text to analyze

        Returns:
            True if object setup is needed
        """


class IADOConfig(ABC):
    """Interface for Azure DevOps configuration."""

    @property
    @abstractmethod
    def organization(self) -> str:
        """ADO organization name."""

    @property
    @abstractmethod
    def project(self) -> str:
        """ADO project name."""

    @property
    @abstractmethod
    def pat(self) -> str | None:
        """Personal Access Token."""

    @property
    @abstractmethod
    def area_path(self) -> str:
        """Default area path."""

    @property
    @abstractmethod
    def assigned_to(self) -> str:
        """Default assignee."""

    @property
    @abstractmethod
    def default_state(self) -> str:
        """Default test case state."""

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Base URL for ADO API."""

    @property
    @abstractmethod
    def test_suite_pattern(self) -> str:
        """Pattern for test suite names."""

    @property
    @abstractmethod
    def qa_prep_pattern(self) -> str | None:
        """Pattern for QA Prep task names (None if not used)."""


class IRulesConfig(ABC):
    """Interface for test generation rules configuration."""

    @property
    @abstractmethod
    def forbidden_words(self) -> list[str]:
        """Words that must not appear in test output."""

    @property
    @abstractmethod
    def forbidden_area_terms(self) -> list[str]:
        """Generic area terms to avoid."""

    @property
    @abstractmethod
    def allowed_areas(self) -> list[str]:
        """Allowed area terms (UI surfaces)."""

    @property
    @abstractmethod
    def cancelled_indicators(self) -> list[str]:
        """Words indicating cancelled/out-of-scope."""

    @property
    @abstractmethod
    def first_test_id(self) -> str:
        """ID for the first test case (e.g., 'AC1')."""

    @property
    @abstractmethod
    def test_id_increment(self) -> int:
        """Increment for subsequent test IDs."""


class IConfigProvider(ABC):
    """Main interface for accessing all configuration."""

    @property
    @abstractmethod
    def project_id(self) -> str:
        """Project identifier."""

    @property
    @abstractmethod
    def application(self) -> IApplicationConfig:
        """Application configuration."""

    @property
    @abstractmethod
    def ado(self) -> IADOConfig:
        """ADO configuration."""

    @property
    @abstractmethod
    def rules(self) -> IRulesConfig:
        """Test generation rules."""

    @property
    @abstractmethod
    def output_dir(self) -> str:
        """Output directory for generated files."""

    @property
    @abstractmethod
    def llm_enabled(self) -> bool:
        """Whether LLM correction is enabled."""

    @property
    @abstractmethod
    def llm_model(self) -> str:
        """LLM model to use."""

    @property
    @abstractmethod
    def objective_patterns(self) -> list[str]:
        """Regex patterns for key terms to bold in objectives."""
