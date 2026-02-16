"""
Project configuration data classes for multi-project support.
Defines the structure for application-specific configurations.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from pathlib import Path
import yaml
import os
import re


@dataclass
class ApplicationConfig:
    """Configuration for the application under test."""
    name: str  # e.g., "ENV QuickDraw", "MediaPedia", "MyApp"
    description: str = ""
    app_type: str = "desktop"  # desktop, web, mobile, hybrid

    # Step templates (these replace hardcoded ENV QuickDraw references)
    prereq_template: str = "Pre-req: The {app_name} is installed"
    launch_step: str = "Launch the {app_name}."
    launch_expected: str = "Application loads successfully."

    # Create file step - IMPORTANT: Most menus require a file/drawing to be open first
    create_file_step: str = "Create a new file/document."
    create_file_expected: str = "A new blank file is created."

    close_step: str = "Close the {app_name}."

    # Feature constraints - CRITICAL for accurate test generation
    # Features that DO NOT exist in this application (prevents generating impossible tests)
    unavailable_features: List[str] = field(default_factory=list)
    # Example: ["multi-object selection", "batch processing", "cloud sync"]

    # INCORRECT UI TERMS - terminology that does NOT exist in the app
    # LLM should NEVER use these terms in generated tests
    forbidden_ui_terms: List[str] = field(default_factory=list)
    # Example: ["Left Toolbar", "Side Panel"] - these UI elements don't exist

    # Feature aliases - map AC terminology to actual feature names
    feature_aliases: Dict[str, str] = field(default_factory=dict)
    # Example: {"multi-select": "single object selection only", "GPS": "Set Base Coordinates"}

    # Feature notes - warnings/notes about feature limitations
    feature_notes: Dict[str, str] = field(default_factory=dict)
    # Example: {"rotate": "Only 90-degree rotations supported"}

    # UI-specific configuration
    main_ui_surfaces: List[str] = field(default_factory=lambda: [
        'Main Menu', 'Toolbar', 'Canvas', 'Properties Panel', 'Dialog Window'
    ])

    # Entry point mappings (feature keywords -> UI locations)
    entry_point_mappings: Dict[str, str] = field(default_factory=lambda: {
        'import': 'File Menu',
        'export': 'File Menu',
        'save': 'File Menu',
        'open': 'File Menu',
        'new': 'File Menu',
        'undo': 'Edit Menu',
        'redo': 'Edit Menu',
        'copy': 'Edit Menu',
        'paste': 'Edit Menu',
        'cut': 'Edit Menu',
        'view': 'View Menu',
        'zoom': 'View Menu',
        'tool': 'Tools Menu',
        'setting': 'Settings',
        'preference': 'Settings',
    })

    # Platform support
    supported_platforms: List[str] = field(default_factory=lambda: [
        'Windows 11', 'iPad', 'Android Tablet'
    ])

    # Object interaction keywords (determines if object setup is needed)
    object_interaction_keywords: List[str] = field(default_factory=lambda: [
        'rotate', 'move', 'delete', 'select', 'resize', 'modify', 'edit',
        'transform', 'flip', 'mirror', 'duplicate', 'copy', 'scale', 'reposition',
        'label', 'labels', 'properties panel', 'object boundary'
    ])

    def get_prereq_step(self) -> str:
        """Get formatted prereq step for this application."""
        return self.prereq_template.format(app_name=self.name)

    def get_launch_step(self) -> str:
        """Get formatted launch step for this application."""
        return self.launch_step.format(app_name=self.name)

    def get_create_file_step(self) -> str:
        """Get the create file/drawing step for this application."""
        return self.create_file_step

    def get_create_file_expected(self) -> str:
        """Get the expected result for create file step."""
        return self.create_file_expected

    def get_close_step(self) -> str:
        """Get formatted close step for this application."""
        return self.close_step.format(app_name=self.name)

    def determine_entry_point(self, feature_name: str, hints: List[str] = None) -> str:
        """Determine the most appropriate entry point for a feature.

        Priority order:
        1. Config mapping match on feature name (most specific)
        2. Hints passed from QA details
        3. Default fallback

        Uses prefix-stem matching (leading \\b only) so stems like
        'dimension' also match 'dimensions', 'propert' matches 'properties', etc.
        Keywords are tried longest-first to prefer specific matches.
        """
        feature_lower = feature_name.lower()

        # FIRST: Check config mapping for feature name (highest priority)
        # Sort by keyword length descending — longer (more specific) keywords first
        for keyword, entry_point in sorted(self.entry_point_mappings.items(), key=lambda kv: len(kv[0]), reverse=True):
            # Leading \b prevents substring false positives ('cut' won't match 'executed')
            # No trailing \b so stems match plurals ('dimension' → 'dimensions')
            pattern = rf'\b{re.escape(keyword)}'
            if re.search(pattern, feature_lower):
                return entry_point

        # SECOND: Use hints if no direct mapping found
        if hints:
            return hints[0]

        return 'Application Menu'

    def requires_object_interaction(self, text: str) -> bool:
        """Determine if the text indicates object interaction is needed.

        Uses word boundary matching to avoid false positives.
        """
        text_lower = text.lower()
        for keyword in self.object_interaction_keywords:
            pattern = rf'\b{re.escape(keyword)}\b'
            if re.search(pattern, text_lower):
                return True
        return False

    def is_feature_available(self, feature_text: str) -> bool:
        """Check if a feature is available in this application.

        Uses word boundary matching to avoid false positives.
        """
        text_lower = feature_text.lower()
        for unavailable in self.unavailable_features:
            # Use word boundary matching for multi-word phrases
            pattern = rf'\b{re.escape(unavailable.lower())}\b'
            if re.search(pattern, text_lower):
                return False
        return True

    def get_feature_warning(self, feature_text: str) -> Optional[str]:
        """Get any warnings/notes about a feature."""
        text_lower = feature_text.lower()
        for feature_key, note in self.feature_notes.items():
            if feature_key.lower() in text_lower:
                return note
        return None

    def resolve_feature_alias(self, ac_text: str) -> str:
        """Replace AC terminology with actual feature names if aliases exist."""
        result = ac_text
        for alias, actual in self.feature_aliases.items():
            if alias.lower() in ac_text.lower():
                # Add note about the alias
                result = result + f" [Note: {alias} → {actual}]"
        return result

    def check_ac_feasibility(self, ac_text: str) -> Dict[str, Any]:
        """
        Check if an AC can be tested with this application's capabilities.

        Returns:
            Dict with 'feasible' bool, 'warnings' list, and 'blocked_reasons' list
        """
        result = {
            'feasible': True,
            'warnings': [],
            'blocked_reasons': [],
            'notes': []
        }

        text_lower = ac_text.lower()

        # Check for unavailable features
        for unavailable in self.unavailable_features:
            if unavailable.lower() in text_lower:
                result['feasible'] = False
                result['blocked_reasons'].append(
                    f"Feature '{unavailable}' is not available in {self.name}"
                )

        # Check for feature notes/warnings
        for feature_key, note in self.feature_notes.items():
            if feature_key.lower() in text_lower:
                result['warnings'].append(note)

        # Check for aliases
        for alias, actual in self.feature_aliases.items():
            if alias.lower() in text_lower:
                result['notes'].append(f"'{alias}' maps to '{actual}'")

        return result


@dataclass
class IntegrationConfig:
    """
    Integration platform configuration.

    Supports multiple platforms: Azure DevOps, Jira, TestRail, etc.
    This allows the framework to be extended to different test management systems.
    """
    platform: str = "ado"  # ado, jira, testrail

    # Base URL template - use placeholders for org/project
    # ADO: "https://dev.azure.com/{organization}/{project}"
    # Jira: "https://{organization}.atlassian.net"
    # TestRail: "https://{organization}.testrail.io"
    base_url_template: str = "https://dev.azure.com/{organization}/{project}"

    # API version (platform-specific)
    api_version: str = "7.1"

    def get_base_url(self, organization: str, project: str = "") -> str:
        """Build the base URL from template and parameters."""
        return self.base_url_template.format(
            organization=organization,
            project=project
        )


@dataclass
class ADOProjectConfig:
    """Azure DevOps project configuration."""
    organization: str  # e.g., "cdpinc", "contoso"
    project: str  # e.g., "Env", "MediaPedia"
    area_path: str  # e.g., "Env\\ENV Kanda", "MediaPedia\\US Team"
    pat: Optional[str] = None  # Personal Access Token (from env var)

    # User assignment
    assigned_to: str = ""
    default_state: str = "Design"

    # Test suite naming pattern
    test_suite_pattern: str = "{story_id} : {story_name}"

    # QA Prep task naming pattern (None means no QA Prep exists)
    qa_prep_pattern: Optional[str] = "Story {story_id}: QA Prep"

    # Integration platform config (for URL customization)
    integration: Optional[IntegrationConfig] = None

    @property
    def base_url(self) -> str:
        """Get the base URL for ADO API calls."""
        if self.integration:
            return self.integration.get_base_url(self.organization, self.project)
        return f"https://dev.azure.com/{self.organization}/{self.project}"

    def get_test_suite_prefix(self, story_id: str) -> str:
        """Get the test suite name prefix for searching."""
        return f"{story_id} :"


@dataclass
class JiraProjectConfig:
    """Jira project configuration."""
    base_url: str  # e.g., "https://company.atlassian.net"
    project_key: str  # e.g., "PROJ", "TEST"
    email: str  # User email for authentication
    api_token: Optional[str] = None  # API token (from env var)

    # Jira Cloud vs Server
    is_cloud: bool = True

    # Custom field for Acceptance Criteria (None to auto-discover)
    ac_field_name: Optional[str] = None

    # QA Prep configuration - subtask type or linked issue type
    qa_prep_issue_type: Optional[str] = "Sub-task"
    qa_prep_label: Optional[str] = "qa-prep"

    @property
    def organization(self) -> str:
        """Extract organization from base URL for compatibility."""
        # Extract subdomain from URL like "https://company.atlassian.net"
        import re
        match = re.search(r'https?://([^.]+)', self.base_url)
        return match.group(1) if match else ''


@dataclass
class TestRailConfig:
    """TestRail configuration."""
    base_url: str  # e.g., "https://company.testrail.io"
    email: str  # User email for authentication
    api_key: Optional[str] = None  # API key (from env var)

    # TestRail project and suite IDs
    project_id: int = 0
    suite_id: Optional[int] = None  # None for single-suite projects

    # Default section for new test cases (None to create per story)
    default_section_id: Optional[int] = None

    # Test case defaults
    default_priority_id: int = 2  # 1=Low, 2=Medium, 3=High, 4=Critical
    default_type_id: Optional[int] = None  # Test type

    @property
    def organization(self) -> str:
        """Extract organization from base URL for compatibility."""
        import re
        match = re.search(r'https?://([^.]+)', self.base_url)
        return match.group(1) if match else ''


@dataclass
class TestRulesConfig:
    """Test case generation rules configuration."""
    # Forbidden words that must not appear in test output
    forbidden_words: List[str] = field(default_factory=lambda: [
        'or / OR', 'if available', 'if supported', 'ambiguous'
    ])

    # Generic area terms that should not be used as scenarios
    forbidden_area_terms: List[str] = field(default_factory=lambda: [
        'Functionality', 'Accessibility', 'Behavior', 'Validation', 'General', 'System'
    ])

    # Allowed area terms (UI surfaces)
    allowed_areas: List[str] = field(default_factory=lambda: [
        'File Menu', 'Edit Menu', 'Tools Menu', 'View Menu', 'Help Menu',
        'Properties Panel', 'Canvas', 'Dialog Window', 'Modal Window', 'Toolbar'
    ])

    # Cancelled/out-of-scope indicators
    cancelled_indicators: List[str] = field(default_factory=lambda: [
        'cancelled', 'out of scope', 'to be cancelled', 'removed', 'not implemented',
        'deprecated', 'superseded', 'will not be implemented'
    ])

    # Test ID configuration
    first_test_id: str = "AC1"  # ID for the first test case
    test_id_increment: int = 5  # Increment for subsequent test IDs (005, 010, 015...)


@dataclass
class ProjectConfig:
    """
    Complete project configuration combining application, platform, and rules settings.
    This is the main configuration class that projects use.

    Supports multiple source platforms (ADO, Jira) and target platforms (ADO, TestRail).
    """
    # Project identifier (used for config file naming)
    project_id: str  # e.g., "env-quickdraw", "mediapedia-us"

    # Sub-configurations
    application: ApplicationConfig
    ado: ADOProjectConfig
    rules: TestRulesConfig = field(default_factory=TestRulesConfig)

    # Platform configurations (optional - for Jira/TestRail integration)
    jira: Optional[JiraProjectConfig] = None  # Source: Jira stories
    testrail: Optional[TestRailConfig] = None  # Target: TestRail test cases

    # Source platform for fetching stories: "ado" or "jira"
    source_platform: str = "ado"

    # Target platform for uploading test cases: "ado" or "testrail"
    target_platform: str = "ado"

    # Output configuration
    output_dir: str = "output"

    # LLM configuration (inherited from global config by default)
    llm_enabled: bool = True
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"

    # Objective formatting - key terms to bold
    objective_key_term_patterns: List[str] = field(default_factory=lambda: [
        # UI Surfaces
        r'\b(?:File|Edit|Tools|View|Help|Insert|Format|Window) Menu\b',
        r'\bProperties Panel\b',
        r'\bToolbar\b',
        r'\bCanvas\b',
        r'\bDialog(?:\s+Window)?\b',
        r'\bModal(?:\s+Window)?\b',
        # Actions
        r'\b(?:Undo|Redo|Cut|Copy|Paste|Delete|Duplicate)\b',
        r'\b(?:Rotate|Mirror|Flip|Transform|Scale|Move|Resize)\b',
        # Platforms
        r'\b(?:Windows 11|Windows 10|iPad|Android Tablet|iPhone|Android Phone)\b',
        # Accessibility
        r'\bAccessibility Insights(?:\s+for\s+Windows)?\b',
        r'\bVoiceOver\b',
        r'\bAccessibility Scanner\b',
        r'\bWCAG\s+\d+\.\d+\s+(?:A|AA|AAA)\b',
        # States
        r'\b(?:enabled|disabled|visible|hidden|selected|deselected)\b',
    ])

    @classmethod
    def load_from_yaml(cls, yaml_path: str) -> 'ProjectConfig':
        """Load project configuration from a YAML file."""
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectConfig':
        """Create ProjectConfig from a dictionary."""
        # Extract application config
        app_data = data.get('application', {})
        application = ApplicationConfig(
            name=app_data.get('name', 'Application'),
            description=app_data.get('description', ''),
            app_type=app_data.get('type', 'desktop'),
            prereq_template=app_data.get('prereq_template', 'Pre-req: The {app_name} is installed'),
            launch_step=app_data.get('launch_step', 'Launch the {app_name}.'),
            launch_expected=app_data.get('launch_expected', 'Application loads successfully.'),
            # Create file step - menus require a file/drawing to be open first
            create_file_step=app_data.get('create_file_step', 'Create a new file/document.'),
            create_file_expected=app_data.get('create_file_expected', 'A new blank file is created.'),
            close_step=app_data.get('close_step', 'Close the {app_name}.'),
            main_ui_surfaces=app_data.get('ui_surfaces', []),
            entry_point_mappings=app_data.get('entry_point_mappings', {}),
            supported_platforms=app_data.get('platforms', ['Windows 11']),
            object_interaction_keywords=app_data.get('object_keywords', []),
            # Feature constraints - critical for accurate test generation
            unavailable_features=app_data.get('unavailable_features', []),
            forbidden_ui_terms=app_data.get('forbidden_ui_terms', []),
            feature_aliases=app_data.get('feature_aliases', {}),
            feature_notes=app_data.get('feature_notes', {}),
        )

        # Extract integration config (for URL customization and future Jira/TestRail support)
        integration_data = data.get('integration', {})
        integration = None
        if integration_data:
            integration = IntegrationConfig(
                platform=integration_data.get('platform', 'ado'),
                base_url_template=integration_data.get('base_url_template',
                    'https://dev.azure.com/{organization}/{project}'),
                api_version=integration_data.get('api_version', '7.1')
            )

        # Extract ADO config
        ado_data = data.get('ado', {})
        ado = ADOProjectConfig(
            organization=ado_data.get('organization', os.getenv('ADO_ORG', '')),
            project=ado_data.get('project', os.getenv('ADO_PROJECT', '')),
            area_path=ado_data.get('area_path', os.getenv('ADO_AREA_PATH', '')),
            pat=os.getenv('ADO_PAT'),  # Always from env for security
            assigned_to=ado_data.get('assigned_to', os.getenv('ASSIGNED_TO', '')),
            default_state=ado_data.get('default_state', os.getenv('DEFAULT_STATE', 'Design')),
            test_suite_pattern=ado_data.get('test_suite_pattern', '{story_id} : {story_name}'),
            qa_prep_pattern=ado_data.get('qa_prep_pattern', 'Story {story_id}: QA Prep'),
            integration=integration
        )

        # Extract rules config
        rules_data = data.get('rules', {})
        rules = TestRulesConfig(
            forbidden_words=rules_data.get('forbidden_words', []),
            forbidden_area_terms=rules_data.get('forbidden_area_terms', []),
            allowed_areas=rules_data.get('allowed_areas', []),
            cancelled_indicators=rules_data.get('cancelled_indicators', []),
            first_test_id=rules_data.get('first_test_id', 'AC1'),
            test_id_increment=rules_data.get('test_id_increment', 5)
        )

        # Extract Jira config (optional)
        jira_data = data.get('jira', {})
        jira = None
        if jira_data:
            jira = JiraProjectConfig(
                base_url=jira_data.get('base_url', os.getenv('JIRA_BASE_URL', '')),
                project_key=jira_data.get('project_key', os.getenv('JIRA_PROJECT_KEY', '')),
                email=jira_data.get('email', os.getenv('JIRA_EMAIL', '')),
                api_token=os.getenv('JIRA_API_TOKEN'),  # Always from env for security
                is_cloud=jira_data.get('is_cloud', True),
                ac_field_name=jira_data.get('ac_field_name'),
                qa_prep_issue_type=jira_data.get('qa_prep_issue_type', 'Sub-task'),
                qa_prep_label=jira_data.get('qa_prep_label', 'qa-prep'),
            )

        # Extract TestRail config (optional)
        testrail_data = data.get('testrail', {})
        testrail = None
        if testrail_data:
            # Helper to safely parse int from env var or YAML (handles empty strings and None)
            def safe_int(value, env_var: str = None, default: int = 0) -> int:
                """Safely convert value to int, with fallback to env var and default."""
                if value is not None and value != '':
                    try:
                        return int(value)
                    except (ValueError, TypeError):
                        pass
                if env_var:
                    env_value = os.getenv(env_var, '')
                    if env_value and env_value.strip():
                        try:
                            return int(env_value)
                        except (ValueError, TypeError):
                            pass
                return default

            def safe_optional_int(value, env_var: str = None) -> Optional[int]:
                """Safely convert value to int, returning None if not valid."""
                if value is not None and value != '':
                    try:
                        return int(value)
                    except (ValueError, TypeError):
                        pass
                if env_var:
                    env_value = os.getenv(env_var, '')
                    if env_value and env_value.strip():
                        try:
                            return int(env_value)
                        except (ValueError, TypeError):
                            pass
                return None

            testrail = TestRailConfig(
                base_url=testrail_data.get('base_url', os.getenv('TESTRAIL_BASE_URL', '')),
                email=testrail_data.get('email', os.getenv('TESTRAIL_EMAIL', '')),
                api_key=os.getenv('TESTRAIL_API_KEY'),  # Always from env for security
                project_id=safe_int(testrail_data.get('project_id'), 'TESTRAIL_PROJECT_ID', 0),
                suite_id=safe_optional_int(testrail_data.get('suite_id'), 'TESTRAIL_SUITE_ID'),
                default_section_id=safe_optional_int(testrail_data.get('default_section_id'), 'TESTRAIL_DEFAULT_SECTION_ID'),
                default_priority_id=safe_int(testrail_data.get('default_priority_id'), None, 2),
                default_type_id=safe_optional_int(testrail_data.get('default_type_id'), 'TESTRAIL_DEFAULT_TYPE_ID'),
            )

        # Determine source and target platforms
        source_platform = data.get('source_platform', 'ado')
        target_platform = data.get('target_platform', 'ado')

        # Auto-detect from integration config if not explicitly set
        if integration_data and 'platform' in integration_data:
            platform = integration_data.get('platform', 'ado')
            if platform == 'jira':
                source_platform = 'jira'
            elif platform == 'testrail':
                target_platform = 'testrail'

        return cls(
            project_id=data.get('project_id', 'default'),
            application=application,
            ado=ado,
            rules=rules,
            jira=jira,
            testrail=testrail,
            source_platform=source_platform,
            target_platform=target_platform,
            output_dir=data.get('output_dir', 'output'),
            llm_enabled=data.get('llm_enabled', True),
            llm_provider=data.get('llm_provider', 'openai'),
            llm_model=data.get('llm_model', 'gpt-4o-mini'),
            objective_key_term_patterns=data.get('objective_patterns', [])
        )

    def to_yaml(self) -> str:
        """Serialize configuration to YAML string."""
        data = {
            'project_id': self.project_id,
            'application': {
                'name': self.application.name,
                'description': self.application.description,
                'type': self.application.app_type,
                'prereq_template': self.application.prereq_template,
                'launch_step': self.application.launch_step,
                'launch_expected': self.application.launch_expected,
                'close_step': self.application.close_step,
                'ui_surfaces': self.application.main_ui_surfaces,
                'entry_point_mappings': self.application.entry_point_mappings,
                'platforms': self.application.supported_platforms,
                'object_keywords': self.application.object_interaction_keywords,
            },
            'ado': {
                'organization': self.ado.organization,
                'project': self.ado.project,
                'area_path': self.ado.area_path,
                'assigned_to': self.ado.assigned_to,
                'default_state': self.ado.default_state,
                'test_suite_pattern': self.ado.test_suite_pattern,
                'qa_prep_pattern': self.ado.qa_prep_pattern,
            },
            'rules': {
                'forbidden_words': self.rules.forbidden_words,
                'forbidden_area_terms': self.rules.forbidden_area_terms,
                'allowed_areas': self.rules.allowed_areas,
                'cancelled_indicators': self.rules.cancelled_indicators,
                'first_test_id': self.rules.first_test_id,
                'test_id_increment': self.rules.test_id_increment,
            },
            'output_dir': self.output_dir,
            'llm_enabled': self.llm_enabled,
            'llm_provider': self.llm_provider,
            'llm_model': self.llm_model,
            'objective_patterns': self.objective_key_term_patterns,
        }

        # Add integration config if present
        if self.ado.integration:
            data['integration'] = {
                'platform': self.ado.integration.platform,
                'base_url_template': self.ado.integration.base_url_template,
                'api_version': self.ado.integration.api_version,
            }

        # Add Jira config if present
        if self.jira:
            data['jira'] = {
                'base_url': self.jira.base_url,
                'project_key': self.jira.project_key,
                'email': self.jira.email,
                'is_cloud': self.jira.is_cloud,
                'ac_field_name': self.jira.ac_field_name,
                'qa_prep_issue_type': self.jira.qa_prep_issue_type,
                'qa_prep_label': self.jira.qa_prep_label,
            }

        # Add TestRail config if present
        if self.testrail:
            data['testrail'] = {
                'base_url': self.testrail.base_url,
                'email': self.testrail.email,
                'project_id': self.testrail.project_id,
                'suite_id': self.testrail.suite_id,
                'default_section_id': self.testrail.default_section_id,
                'default_priority_id': self.testrail.default_priority_id,
                'default_type_id': self.testrail.default_type_id,
            }

        # Add platform selection
        data['source_platform'] = self.source_platform
        data['target_platform'] = self.target_platform

        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    def save(self, path: str = None) -> str:
        """Save configuration to YAML file."""
        if path is None:
            path = f"projects/configs/{self.project_id}.yaml"

        # Ensure directory exists
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w') as f:
            f.write(self.to_yaml())

        return path


# Predefined configurations for known projects
def get_env_quickdraw_config() -> ProjectConfig:
    """Get the default ENV QuickDraw configuration (current project)."""
    return ProjectConfig(
        project_id="env-quickdraw",
        application=ApplicationConfig(
            name="ENV QuickDraw",
            description="Drawing and dimensioning application",
            app_type="desktop",
            prereq_template="Pre-req: The {app_name} App is installed",
            launch_step="Launch the {app_name} application.",
            launch_expected="Model space(Gray) and Canvas(white) space should be displayed",
            close_step="Close the {app_name} App",
            # FEATURE CONSTRAINTS - Critical for accurate test generation
            unavailable_features=[
                "multi-object selection",
                "multi-select",
                "batch processing",
                "cloud sync",
                "real-time collaboration",
                "version history",
            ],
            feature_aliases={
                "GPS": "Set Base Coordinates dialog",
                "coordinates": "Set Base Coordinates dialog",
            },
            feature_notes={
                "rotate": "Rotation uses system default logic (typically 90-degree increments)",
                "mirror": "Mirror operations preserve relative positions",
                "transform": "Commands are only enabled when at least one object is selected",
            },
            main_ui_surfaces=[
                'File Menu', 'Edit Menu', 'Tools Menu', 'Dimensions Menu',
                'Properties Panel', 'Dimensions Panel', 'Canvas',
                'Dialog Window', 'Modal Window', 'Top Action Toolbar'
            ],
            entry_point_mappings={
                'import': 'File Menu',
                'export': 'File Menu',
                'save': 'File Menu',
                'open': 'File Menu',
                'new': 'File Menu',
                'undo': 'Edit Menu',
                'redo': 'Edit Menu',
                'copy': 'Edit Menu',
                'paste': 'Edit Menu',
                'cut': 'Edit Menu',
                'view': 'View Menu',
                'zoom': 'View Menu',
                'pan': 'View Menu',
                'tool': 'Tools Menu',
                'draw': 'Tools Menu',
                'shape': 'Tools Menu',
                'dimension': 'Dimensions Menu',
                'measure': 'Dimensions Menu',
                'diameter': 'Dimensions Menu',
                'propert': 'Properties Panel',
                'setting': 'Settings',
                'preference': 'Settings',
            },
            supported_platforms=['Windows 11', 'iPad', 'Android Tablet'],
        ),
        ado=ADOProjectConfig(
            organization="cdpinc",
            project="Env",
            area_path="Env\\ENV Kanda",
            assigned_to="gulzhas.mailybayeva@kandasoft.com",
            default_state="Design",
            test_suite_pattern="{story_id} : {story_name}",
            qa_prep_pattern="Story {story_id}: QA Prep",
        ),
        rules=TestRulesConfig(
            forbidden_words=['or / OR', 'if available', 'if supported', 'ambiguous'],
            forbidden_area_terms=['Functionality', 'Accessibility', 'Behavior', 'Validation', 'General', 'System'],
            allowed_areas=[
                'File Menu', 'Edit Menu', 'Tools Menu', 'Dimensions Menu',
                'Properties Panel', 'Dimensions Panel', 'Canvas',
                'Dialog Window', 'Modal Window', 'Top Action Toolbar'
            ],
        ),
    )


def create_new_project_config(
    project_id: str,
    app_name: str,
    ado_org: str,
    ado_project: str,
    area_path: str,
    **kwargs
) -> ProjectConfig:
    """
    Create a new project configuration with minimal required parameters.
    Additional parameters can be customized via kwargs.
    """
    return ProjectConfig(
        project_id=project_id,
        application=ApplicationConfig(
            name=app_name,
            description=kwargs.get('description', ''),
            app_type=kwargs.get('app_type', 'desktop'),
            prereq_template=kwargs.get('prereq_template', f"Pre-req: The {app_name} is installed"),
            launch_step=kwargs.get('launch_step', f"Launch the {app_name}."),
            launch_expected=kwargs.get('launch_expected', 'Application loads successfully.'),
            close_step=kwargs.get('close_step', f"Close the {app_name}."),
            main_ui_surfaces=kwargs.get('ui_surfaces', []),
            entry_point_mappings=kwargs.get('entry_point_mappings', {}),
            supported_platforms=kwargs.get('platforms', ['Windows 11']),
        ),
        ado=ADOProjectConfig(
            organization=ado_org,
            project=ado_project,
            area_path=area_path,
            assigned_to=kwargs.get('assigned_to', ''),
            default_state=kwargs.get('default_state', 'Design'),
            test_suite_pattern=kwargs.get('test_suite_pattern', '{story_id} : {story_name}'),
            qa_prep_pattern=kwargs.get('qa_prep_pattern'),  # None if not using QA Prep
        ),
        output_dir=kwargs.get('output_dir', 'output'),
    )
