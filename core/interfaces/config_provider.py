"""
Configuration provider interfaces.

Abstracts configuration access to enable dependency injection and testability.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class IApplicationConfig(ABC):
    """Interface for application-specific configuration."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Application name."""
        pass

    @property
    @abstractmethod
    def app_type(self) -> str:
        """Application type (desktop, web, mobile, hybrid)."""
        pass

    @property
    @abstractmethod
    def prereq_template(self) -> str:
        """Template for prerequisite step."""
        pass

    @property
    @abstractmethod
    def launch_step(self) -> str:
        """Template for launch step."""
        pass

    @property
    @abstractmethod
    def launch_expected(self) -> str:
        """Expected result for launch step."""
        pass

    @property
    @abstractmethod
    def close_step(self) -> str:
        """Template for close step."""
        pass

    @property
    @abstractmethod
    def supported_platforms(self) -> List[str]:
        """List of supported platforms."""
        pass

    @property
    @abstractmethod
    def ui_surfaces(self) -> List[str]:
        """List of main UI surfaces."""
        pass

    @abstractmethod
    def get_entry_point(self, feature_name: str, hints: List[str] = None) -> str:
        """Determine entry point for a feature.

        Args:
            feature_name: Name of the feature
            hints: Optional hints from QA Prep

        Returns:
            Entry point name (e.g., 'File Menu', 'Settings')
        """
        pass

    @abstractmethod
    def requires_object_interaction(self, text: str) -> bool:
        """Check if text indicates object interaction is needed.

        Args:
            text: Text to analyze

        Returns:
            True if object setup is needed
        """
        pass


class IADOConfig(ABC):
    """Interface for Azure DevOps configuration."""

    @property
    @abstractmethod
    def organization(self) -> str:
        """ADO organization name."""
        pass

    @property
    @abstractmethod
    def project(self) -> str:
        """ADO project name."""
        pass

    @property
    @abstractmethod
    def pat(self) -> Optional[str]:
        """Personal Access Token."""
        pass

    @property
    @abstractmethod
    def area_path(self) -> str:
        """Default area path."""
        pass

    @property
    @abstractmethod
    def assigned_to(self) -> str:
        """Default assignee."""
        pass

    @property
    @abstractmethod
    def default_state(self) -> str:
        """Default test case state."""
        pass

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Base URL for ADO API."""
        pass

    @property
    @abstractmethod
    def test_suite_pattern(self) -> str:
        """Pattern for test suite names."""
        pass

    @property
    @abstractmethod
    def qa_prep_pattern(self) -> Optional[str]:
        """Pattern for QA Prep task names (None if not used)."""
        pass


class IRulesConfig(ABC):
    """Interface for test generation rules configuration."""

    @property
    @abstractmethod
    def forbidden_words(self) -> List[str]:
        """Words that must not appear in test output."""
        pass

    @property
    @abstractmethod
    def forbidden_area_terms(self) -> List[str]:
        """Generic area terms to avoid."""
        pass

    @property
    @abstractmethod
    def allowed_areas(self) -> List[str]:
        """Allowed area terms (UI surfaces)."""
        pass

    @property
    @abstractmethod
    def cancelled_indicators(self) -> List[str]:
        """Words indicating cancelled/out-of-scope."""
        pass

    @property
    @abstractmethod
    def first_test_id(self) -> str:
        """ID for the first test case (e.g., 'AC1')."""
        pass

    @property
    @abstractmethod
    def test_id_increment(self) -> int:
        """Increment for subsequent test IDs."""
        pass


class IConfigProvider(ABC):
    """Main interface for accessing all configuration."""

    @property
    @abstractmethod
    def project_id(self) -> str:
        """Project identifier."""
        pass

    @property
    @abstractmethod
    def application(self) -> IApplicationConfig:
        """Application configuration."""
        pass

    @property
    @abstractmethod
    def ado(self) -> IADOConfig:
        """ADO configuration."""
        pass

    @property
    @abstractmethod
    def rules(self) -> IRulesConfig:
        """Test generation rules."""
        pass

    @property
    @abstractmethod
    def output_dir(self) -> str:
        """Output directory for generated files."""
        pass

    @property
    @abstractmethod
    def llm_enabled(self) -> bool:
        """Whether LLM correction is enabled."""
        pass

    @property
    @abstractmethod
    def llm_model(self) -> str:
        """LLM model to use."""
        pass

    @property
    @abstractmethod
    def objective_patterns(self) -> List[str]:
        """Regex patterns for key terms to bold in objectives."""
        pass
