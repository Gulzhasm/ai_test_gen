"""
Project configuration management for multi-project support.
This module enables the test generation framework to work with any application.
"""
from .discovery import ApplicationDiscovery
from .project_config import ADOProjectConfig, ApplicationConfig, ProjectConfig
from .project_manager import ProjectManager, get_project_manager

__all__ = [
    'ADOProjectConfig',
    'ApplicationConfig',
    'ApplicationDiscovery',
    'ProjectConfig',
    'ProjectManager',
    'get_project_manager'
]
