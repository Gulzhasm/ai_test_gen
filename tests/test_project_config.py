"""
Unit tests for Project Configuration module.

Tests project configuration loading and management.
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from projects.project_config import (
    ProjectConfig,
    ApplicationConfig,
    ADOProjectConfig,
    TestRulesConfig,
    get_env_quickdraw_config,
    create_new_project_config
)


class TestApplicationConfig:
    """Test ApplicationConfig dataclass."""

    def test_creation_minimal(self):
        """Test ApplicationConfig instantiation with minimal params."""
        config = ApplicationConfig(name="Test App")

        assert config.name == "Test App"
        assert config.app_type == "desktop"  # Default

    def test_creation_full(self):
        """Test ApplicationConfig with all params."""
        config = ApplicationConfig(
            name="Test App",
            description="Test description",
            app_type="web",
            prereq_template="PRE-REQ: App installed",
            launch_step="Launch the app",
            launch_expected="App opens",
            close_step="Close the app",
            main_ui_surfaces=["Menu", "Toolbar"],
            entry_point_mappings={"feature": "Menu"},
            supported_platforms=["Windows", "Mac"],
            object_interaction_keywords=["rotate", "move"]
        )

        assert config.name == "Test App"
        assert config.app_type == "web"
        assert "Windows" in config.supported_platforms

    def test_determine_entry_point_with_hint(self):
        """Test entry point determination with hints."""
        config = ApplicationConfig(
            name="Test App",
            main_ui_surfaces=["Menu", "Toolbar", "Panel"]
        )

        # Should use hint if available
        entry = config.determine_entry_point("SomeFeature", ["Toolbar"])
        assert entry == "Toolbar"

    def test_determine_entry_point_with_mapping(self):
        """Test entry point from feature mapping."""
        config = ApplicationConfig(
            name="Test App",
            entry_point_mappings={"edit": "Edit Menu", "file": "File Menu"}
        )

        entry = config.determine_entry_point("Edit Tools")
        assert entry == "Edit Menu"

    def test_determine_entry_point_default(self):
        """Test entry point default."""
        config = ApplicationConfig(
            name="Test App",
            entry_point_mappings={}
        )

        entry = config.determine_entry_point("Unknown Feature")
        assert entry == "Application Menu"  # Default

    def test_requires_object_interaction(self):
        """Test object interaction detection."""
        config = ApplicationConfig(
            name="Test App",
            object_interaction_keywords=["rotate", "move", "scale"]
        )

        assert config.requires_object_interaction("Rotate the object")
        assert config.requires_object_interaction("Move the selection")
        assert not config.requires_object_interaction("Open the menu")

    def test_get_prereq_step(self):
        """Test formatted prereq step."""
        config = ApplicationConfig(
            name="MyApp",
            prereq_template="Pre-req: The {app_name} is installed"
        )

        assert "MyApp" in config.get_prereq_step()

    def test_get_launch_step(self):
        """Test formatted launch step."""
        config = ApplicationConfig(
            name="MyApp",
            launch_step="Launch the {app_name}."
        )

        assert "MyApp" in config.get_launch_step()

    def test_get_close_step(self):
        """Test formatted close step."""
        config = ApplicationConfig(
            name="MyApp",
            close_step="Close the {app_name}."
        )

        assert "MyApp" in config.get_close_step()


class TestADOProjectConfig:
    """Test ADOProjectConfig dataclass."""

    def test_creation(self):
        """Test ADOProjectConfig instantiation."""
        config = ADOProjectConfig(
            organization="myorg",
            project="myproject",
            area_path="Project\\Area"
        )

        assert config.organization == "myorg"
        assert config.project == "myproject"
        assert config.base_url == "https://dev.azure.com/myorg/myproject"

    def test_default_values(self):
        """Test default values."""
        config = ADOProjectConfig(
            organization="org",
            project="proj",
            area_path="path"
        )

        assert config.default_state == "Design"
        assert config.test_suite_pattern == "{story_id} : {story_name}"

    def test_get_test_suite_prefix(self):
        """Test test suite prefix generation."""
        config = ADOProjectConfig(
            organization="org",
            project="proj",
            area_path="path"
        )

        prefix = config.get_test_suite_prefix("12345")
        assert prefix == "12345 :"


class TestTestRulesConfig:
    """Test TestRulesConfig dataclass."""

    def test_creation_defaults(self):
        """Test TestRulesConfig with defaults."""
        config = TestRulesConfig()

        assert len(config.forbidden_words) > 0
        assert config.first_test_id == "AC1"
        assert config.test_id_increment == 5

    def test_creation_custom(self):
        """Test TestRulesConfig with custom values."""
        config = TestRulesConfig(
            forbidden_words=["word1", "word2"],
            first_test_id="TC1",
            test_id_increment=10
        )

        assert "word1" in config.forbidden_words
        assert config.first_test_id == "TC1"
        assert config.test_id_increment == 10


class TestProjectConfig:
    """Test ProjectConfig dataclass."""

    def test_creation(self):
        """Test ProjectConfig instantiation."""
        app_config = ApplicationConfig(name="Test App")
        ado_config = ADOProjectConfig(
            organization="org",
            project="proj",
            area_path="path"
        )

        config = ProjectConfig(
            project_id="test-project",
            application=app_config,
            ado=ado_config
        )

        assert config.project_id == "test-project"
        assert config.application.name == "Test App"

    def test_default_rules(self):
        """Test default rules config."""
        app_config = ApplicationConfig(name="Test")
        ado_config = ADOProjectConfig(
            organization="org",
            project="proj",
            area_path="path"
        )

        config = ProjectConfig(
            project_id="test",
            application=app_config,
            ado=ado_config
        )

        # Should have default TestRulesConfig
        assert config.rules is not None
        assert config.rules.first_test_id == "AC1"


class TestGetEnvQuickdrawConfig:
    """Test ENV QuickDraw default configuration."""

    def test_returns_project_config(self):
        """Test returns valid ProjectConfig."""
        config = get_env_quickdraw_config()

        assert isinstance(config, ProjectConfig)
        assert config.project_id == "env-quickdraw"

    def test_application_config(self):
        """Test application configuration values."""
        config = get_env_quickdraw_config()

        assert "QuickDraw" in config.application.name
        assert config.application.app_type == "desktop"

    def test_ado_config(self):
        """Test ADO configuration values."""
        config = get_env_quickdraw_config()

        assert config.ado.organization == "cdpinc"
        assert config.ado.project == "Env"

    def test_rules_config(self):
        """Test rules configuration values."""
        config = get_env_quickdraw_config()

        assert len(config.rules.forbidden_words) > 0
        assert config.rules.first_test_id == "AC1"
        assert config.rules.test_id_increment == 5

    def test_ui_surfaces(self):
        """Test UI surfaces configuration."""
        config = get_env_quickdraw_config()

        surfaces = config.application.main_ui_surfaces
        assert 'File Menu' in surfaces
        assert 'Properties Panel' in surfaces


class TestCreateNewProjectConfig:
    """Test new project configuration creation."""

    def test_create_minimal_config(self):
        """Test creating minimal project config."""
        config = create_new_project_config(
            project_id="new-project",
            app_name="New App",
            ado_org="org",
            ado_project="proj",
            area_path="path"
        )

        assert isinstance(config, ProjectConfig)
        assert config.project_id == "new-project"
        assert config.application.name == "New App"

    def test_create_with_options(self):
        """Test creating config with optional parameters."""
        config = create_new_project_config(
            project_id="new-project",
            app_name="New App",
            ado_org="org",
            ado_project="proj",
            area_path="Proj\\Area",
            app_type="web"
        )

        assert config.application.app_type == "web"
        assert config.ado.area_path == "Proj\\Area"

    def test_default_templates(self):
        """Test default templates are set."""
        config = create_new_project_config(
            project_id="test",
            app_name="Test App",
            ado_org="org",
            ado_project="proj",
            area_path="path"
        )

        # Should have app name in templates
        prereq = config.application.get_prereq_step()
        launch = config.application.get_launch_step()
        assert "Test App" in prereq
        assert "Test App" in launch


class TestProjectConfigEdgeCases:
    """Test edge cases for project configuration."""

    def test_empty_ui_surfaces(self):
        """Test handling of empty UI surfaces."""
        config = ApplicationConfig(
            name="Test",
            main_ui_surfaces=[]
        )

        # Should handle gracefully
        entry = config.determine_entry_point("Feature")
        assert entry == "Application Menu"  # Default

    def test_object_keywords_in_text(self):
        """Test object keywords match in lowercased text."""
        config = ApplicationConfig(
            name="Test",
            object_interaction_keywords=["rotate", "move"]
        )

        assert config.requires_object_interaction("Rotate the object")
        assert config.requires_object_interaction("MOVE the shape")
