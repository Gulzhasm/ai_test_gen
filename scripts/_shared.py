"""
Shared utilities for scripts.

Provides common boilerplate: argument parsing, config loading, ADO client creation.
"""
import argparse
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from projects.project_manager import get_project_manager
from projects.project_config import ProjectConfig
from infrastructure.ado.http_client import ADOHttpClient


def create_base_parser(description: str) -> argparse.ArgumentParser:
    """Create argument parser with common --project flag.

    Args:
        description: Script description for help text.

    Returns:
        ArgumentParser with --project already added.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        '--project',
        default='env-quickdraw',
        help='Project config ID from projects/configs/ (default: env-quickdraw)'
    )
    return parser


def load_project_config(project_id: str) -> ProjectConfig:
    """Load a project configuration by ID.

    Args:
        project_id: Project identifier (e.g., 'env-quickdraw').

    Returns:
        Loaded ProjectConfig.

    Raises:
        SystemExit: If project not found.
    """
    manager = get_project_manager()

    # Suppress verbose "Loaded project config:" messages during directory scan
    import io
    _stdout = sys.stdout
    sys.stdout = io.StringIO()
    manager.load_from_directory()
    sys.stdout = _stdout

    config = manager.get_project(project_id)
    if not config:
        available = manager.list_projects()
        print(f"Error: Project '{project_id}' not found.")
        print(f"Available projects: {available}")
        sys.exit(1)

    return config


def create_ado_client(config: ProjectConfig) -> ADOHttpClient:
    """Create an ADO HTTP client from project config.

    PAT is always read from the ADO_PAT environment variable.

    Args:
        config: Project configuration.

    Returns:
        Configured ADOHttpClient.

    Raises:
        SystemExit: If ADO_PAT is not set.
    """
    pat = os.getenv('ADO_PAT')
    if not pat:
        print("Error: ADO_PAT not set in environment")
        sys.exit(1)

    return ADOHttpClient(
        organization=config.ado.organization,
        project=config.ado.project,
        pat=pat
    )
