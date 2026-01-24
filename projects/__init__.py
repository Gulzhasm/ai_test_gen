"""
Project configuration management for multi-project support.
This module enables the test generation framework to work with any application.
"""
from .project_config import ProjectConfig, ApplicationConfig, ADOProjectConfig
from .project_manager import ProjectManager
from .discovery import ApplicationDiscovery

__all__ = [
    'ProjectConfig',
    'ApplicationConfig',
    'ADOProjectConfig',
    'ProjectManager',
    'ApplicationDiscovery'
]
