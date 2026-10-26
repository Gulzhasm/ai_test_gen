"""
Project Manager - Handles loading, switching, and managing project configurations.
"""
import os
from pathlib import Path

from .project_config import ProjectConfig, get_env_quickdraw_config


class ProjectManager:
    """
    Manages multiple project configurations.
    Allows loading from YAML files, switching between projects, and
    provides the active project configuration to the rest of the system.
    """

    # Default configs directory
    CONFIGS_DIR = Path(__file__).parent / "configs"

    def __init__(self):
        self._projects: dict[str, ProjectConfig] = {}
        self._active_project_id: str | None = None
        # Project IDs whose config came from hardcoded Python built-ins
        # (not from a YAML file in projects/configs/).
        self._builtin_ids: set = set()

        # Ensure configs directory exists
        self.CONFIGS_DIR.mkdir(parents=True, exist_ok=True)

        # Load built-in configurations
        self._load_builtin_configs()

    def _load_builtin_configs(self):
        """Load built-in project configurations."""
        # Original project kept as a built-in fallback only.
        env_config = get_env_quickdraw_config()
        self._projects[env_config.project_id] = env_config
        self._builtin_ids.add(env_config.project_id)

    def _warn_if_builtin_shadow(self, config: ProjectConfig | None) -> None:
        """Warn loudly when a config resolves from built-in Python defaults
        and no corresponding YAML file exists in projects/configs/.

        Built-ins silently shadowing a missing YAML has hidden accidental
        YAML deletions in the past; this makes that state visible.
        """
        if config is None:
            return
        project_id = config.project_id
        if project_id not in self._builtin_ids:
            return
        yaml_path = self.CONFIGS_DIR / f"{project_id}.yaml"
        if not yaml_path.exists():
            print(
                f"WARNING: project '{project_id}' resolved from built-in defaults — "
                f"no YAML found at projects/configs/{project_id}.yaml; "
                f"built-ins may be stale. Create the YAML to silence this."
            )

    def load_from_directory(self, directory: str = None) -> int:
        """
        Load all YAML project configurations from a directory.

        Args:
            directory: Path to configs directory. Defaults to projects/configs.

        Returns:
            Number of configurations loaded.
        """
        config_dir = Path(directory) if directory else self.CONFIGS_DIR
        loaded = 0

        if not config_dir.exists():
            return loaded

        for yaml_file in config_dir.glob("*.yaml"):
            try:
                config = ProjectConfig.load_from_yaml(str(yaml_file))
                self._projects[config.project_id] = config
                self._builtin_ids.discard(config.project_id)
                loaded += 1
                print(f"  Loaded project config: {config.project_id}")
            except Exception as e:
                print(f"  Warning: Could not load {yaml_file}: {e}")

        return loaded

    def load_project(self, yaml_path: str) -> ProjectConfig:
        """
        Load a specific project configuration from YAML.

        Args:
            yaml_path: Path to the YAML configuration file.

        Returns:
            The loaded ProjectConfig.
        """
        config = ProjectConfig.load_from_yaml(yaml_path)
        self._projects[config.project_id] = config
        self._builtin_ids.discard(config.project_id)
        return config

    def get_project(self, project_id: str) -> ProjectConfig | None:
        """Get a project configuration by ID."""
        config = self._projects.get(project_id)
        self._warn_if_builtin_shadow(config)
        return config

    def set_active_project(self, project_id: str) -> bool:
        """
        Set the active project.

        Args:
            project_id: ID of the project to activate.

        Returns:
            True if project was found and activated, False otherwise.
        """
        if project_id in self._projects:
            self._active_project_id = project_id
            return True
        return False

    @property
    def active_project(self) -> ProjectConfig | None:
        """Get the currently active project configuration."""
        if self._active_project_id:
            config = self._projects.get(self._active_project_id)
            self._warn_if_builtin_shadow(config)
            return config
        # Default to first project if none active
        if self._projects:
            first_id = next(iter(self._projects))
            config = self._projects[first_id]
            self._warn_if_builtin_shadow(config)
            return config
        return None

    def list_projects(self) -> list[str]:
        """List all available project IDs."""
        return list(self._projects.keys())

    def register_project(self, config: ProjectConfig) -> None:
        """Register a new project configuration."""
        self._projects[config.project_id] = config
        self._builtin_ids.discard(config.project_id)

    def save_project(self, project_id: str, path: str = None) -> str:
        """
        Save a project configuration to YAML.

        Args:
            project_id: ID of the project to save.
            path: Optional custom path. Defaults to configs/{project_id}.yaml.

        Returns:
            Path where the file was saved.
        """
        config = self._projects.get(project_id)
        if not config:
            raise ValueError(f"Project not found: {project_id}")

        if path is None:
            path = str(self.CONFIGS_DIR / f"{project_id}.yaml")

        return config.save(path)

    def create_project_from_env(self, project_id: str, app_name: str) -> ProjectConfig:
        """
        Create a new project configuration using environment variables for ADO settings.

        Args:
            project_id: Unique identifier for the project.
            app_name: Name of the application under test.

        Returns:
            The created ProjectConfig.
        """
        from .project_config import create_new_project_config

        config = create_new_project_config(
            project_id=project_id,
            app_name=app_name,
            ado_org=os.getenv('ADO_ORG', ''),
            ado_project=os.getenv('ADO_PROJECT', ''),
            area_path=os.getenv('ADO_AREA_PATH', ''),
            assigned_to=os.getenv('ASSIGNED_TO', ''),
        )

        self._projects[project_id] = config
        return config

    def get_or_create_default(self) -> ProjectConfig:
        """
        Get the active project or create a default one from environment.

        Returns:
            The active or newly created ProjectConfig.
        """
        if self.active_project:
            return self.active_project

        # Try to create from environment
        app_name = os.getenv('APP_NAME', 'Application')
        return self.create_project_from_env('default', app_name)


# Global project manager instance
_project_manager: ProjectManager | None = None


def get_project_manager() -> ProjectManager:
    """Get the global project manager instance."""
    global _project_manager
    if _project_manager is None:
        _project_manager = ProjectManager()
    return _project_manager


def get_active_config() -> ProjectConfig:
    """Convenience function to get the active project configuration."""
    return get_project_manager().get_or_create_default()
