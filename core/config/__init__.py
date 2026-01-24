"""
Configuration management - externalized and extensible.
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass


@dataclass
class ADOConfig:
    """Azure DevOps configuration."""
    org: str
    project: str
    pat: Optional[str]
    area_path: str
    base_url: str
    
    @classmethod
    def from_env(cls) -> 'ADOConfig':
        """Create config from environment variables."""
        org = os.getenv("ADO_ORG", "cdpinc")
        project = os.getenv("ADO_PROJECT", "Env")
        pat = os.getenv("ADO_PAT")
        area_path = os.getenv("ADO_AREA_PATH", "Env\\ENV Kanda")
        base_url = f"https://dev.azure.com/{org}/{project}"
        return cls(org=org, project=project, pat=pat, area_path=area_path, base_url=base_url)


@dataclass
class TestCaseConfig:
    """Test case generation configuration."""
    assigned_to: str
    default_state: str
    forbidden_words: List[str]
    forbidden_area_terms: List[str]
    allowed_areas: List[str]
    objective_key_terms: List[str]
    
    @classmethod
    def default(cls) -> 'TestCaseConfig':
        """Create default test case configuration."""
        return cls(
            assigned_to=os.getenv("TEST_ASSIGNED_TO", "Gulzhas Mailybayeva <gulzhas.mailybayeva@kandasoft.com>"),
            default_state=os.getenv("TEST_DEFAULT_STATE", "Design"),
            forbidden_words=[
                'or / OR', 'if available', 'if supported', 'ambiguous'
            ],
            forbidden_area_terms=[
                'Functionality', 'Accessibility', 'Behavior', 'Validation', 'General', 'System'
            ],
            allowed_areas=[
                'File Menu', 'Edit Menu', 'Tools Menu', 'Properties Panel',
                'Dimensions Panel', 'Canvas', 'Dialog Window', 'Modal Window',
                'Top Action Toolbar'
            ],
            objective_key_terms=[]  # Will be populated dynamically based on feature
        )


@dataclass
class OutputConfig:
    """Output configuration."""
    output_dir: str
    
    @classmethod
    def default(cls) -> 'OutputConfig':
        """Create default output configuration."""
        return cls(output_dir=os.getenv("OUTPUT_DIR", "output"))


@dataclass
class AppConfig:
    """Application-wide configuration."""
    ado: ADOConfig
    test_case: TestCaseConfig
    output: OutputConfig
    
    @classmethod
    def load(cls) -> 'AppConfig':
        """Load application configuration."""
        return cls(
            ado=ADOConfig.from_env(),
            test_case=TestCaseConfig.default(),
            output=OutputConfig.default()
        )
