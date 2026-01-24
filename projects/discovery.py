"""
Application Discovery Module - Learns about new applications to generate appropriate test cases.
Uses LLM to understand application context and generate configuration.
"""
from typing import Dict, Optional, List, Any
from dataclasses import dataclass
import json
import os

from .project_config import ProjectConfig, ApplicationConfig, ADOProjectConfig, TestRulesConfig


@dataclass
class DiscoveredApplication:
    """Result of application discovery process."""
    name: str
    description: str
    app_type: str  # desktop, web, mobile, hybrid
    main_ui_surfaces: List[str]
    entry_point_mappings: Dict[str, str]
    supported_platforms: List[str]
    object_keywords: List[str]
    prereq_template: str
    launch_step: str
    launch_expected: str
    close_step: str
    confidence_score: float  # 0.0 to 1.0


class ApplicationDiscovery:
    """
    Discovers application characteristics through multiple methods:
    1. Story/User Story analysis - learns from ADO work items
    2. Interactive questionnaire - asks user questions
    3. LLM-based inference - uses AI to understand app context
    """

    # Default questions for interactive discovery
    DISCOVERY_QUESTIONS = [
        {
            "id": "app_type",
            "question": "What type of application is this?",
            "options": ["Desktop application", "Web application", "Mobile app", "Hybrid/Cross-platform"],
            "mapping": {"Desktop application": "desktop", "Web application": "web",
                        "Mobile app": "mobile", "Hybrid/Cross-platform": "hybrid"}
        },
        {
            "id": "platforms",
            "question": "Which platforms does this application support? (comma-separated)",
            "hint": "e.g., Windows 11, macOS, iPad, Android Tablet, Chrome, Safari",
            "type": "multi"
        },
        {
            "id": "main_ui",
            "question": "What are the main UI areas/surfaces in this application? (comma-separated)",
            "hint": "e.g., Dashboard, Settings, User Profile, Navigation Menu, Canvas",
            "type": "multi"
        },
        {
            "id": "launch_behavior",
            "question": "What happens when the application launches successfully?",
            "hint": "e.g., 'Login screen appears', 'Dashboard is displayed', 'Main canvas loads'"
        },
        {
            "id": "object_types",
            "question": "What types of objects/entities can users interact with? (comma-separated)",
            "hint": "e.g., documents, shapes, records, items, users",
            "type": "multi"
        }
    ]

    def __init__(self, llm_provider=None):
        """
        Initialize discovery module.

        Args:
            llm_provider: Optional LLM provider for AI-assisted discovery.
        """
        self.llm_provider = llm_provider

    def discover_from_stories(self, stories: List[Dict]) -> DiscoveredApplication:
        """
        Analyze ADO stories to discover application characteristics.

        Args:
            stories: List of story data from ADO (titles, descriptions, ACs).

        Returns:
            DiscoveredApplication with inferred characteristics.
        """
        # Collect all text for analysis
        all_text = []
        for story in stories:
            all_text.append(story.get('title', ''))
            all_text.append(story.get('description', ''))
            for ac in story.get('acceptance_criteria', []):
                all_text.append(ac)

        combined_text = ' '.join(all_text).lower()

        # Infer application type
        app_type = self._infer_app_type(combined_text)

        # Extract UI surfaces mentioned
        ui_surfaces = self._extract_ui_surfaces(combined_text)

        # Extract platform references
        platforms = self._extract_platforms(combined_text)

        # Extract object/entity types
        object_keywords = self._extract_object_keywords(combined_text)

        # Build entry point mappings from context
        entry_mappings = self._build_entry_mappings(combined_text, ui_surfaces)

        # Infer app name from story patterns
        app_name = self._infer_app_name(stories)

        return DiscoveredApplication(
            name=app_name,
            description=f"Application discovered from {len(stories)} stories",
            app_type=app_type,
            main_ui_surfaces=ui_surfaces,
            entry_point_mappings=entry_mappings,
            supported_platforms=platforms,
            object_keywords=object_keywords,
            prereq_template=f"Pre-req: The {app_name} is installed",
            launch_step=f"Launch the {app_name}.",
            launch_expected="Application loads successfully.",
            close_step=f"Close the {app_name}.",
            confidence_score=0.7 if len(stories) > 3 else 0.5
        )

    def discover_interactive(self, app_name: str, responses: Dict[str, str]) -> DiscoveredApplication:
        """
        Create discovery result from interactive questionnaire responses.

        Args:
            app_name: Name of the application.
            responses: Dictionary of question_id -> response.

        Returns:
            DiscoveredApplication with user-provided characteristics.
        """
        # Parse app type
        app_type_response = responses.get('app_type', 'Desktop application')
        app_type_mapping = {
            'Desktop application': 'desktop',
            'Web application': 'web',
            'Mobile app': 'mobile',
            'Hybrid/Cross-platform': 'hybrid'
        }
        app_type = app_type_mapping.get(app_type_response, 'desktop')

        # Parse platforms
        platforms_str = responses.get('platforms', 'Windows 11')
        platforms = [p.strip() for p in platforms_str.split(',') if p.strip()]

        # Parse UI surfaces
        ui_str = responses.get('main_ui', 'Main Menu, Dashboard')
        ui_surfaces = [s.strip() for s in ui_str.split(',') if s.strip()]

        # Parse object keywords
        obj_str = responses.get('object_types', '')
        object_keywords = [k.strip() for k in obj_str.split(',') if k.strip()]

        # Add common action keywords
        object_keywords.extend(['select', 'edit', 'delete', 'create', 'modify'])

        # Launch behavior
        launch_expected = responses.get('launch_behavior', 'Application loads successfully.')

        # Build entry point mappings
        entry_mappings = self._build_default_entry_mappings(ui_surfaces)

        return DiscoveredApplication(
            name=app_name,
            description=f"User-configured application",
            app_type=app_type,
            main_ui_surfaces=ui_surfaces,
            entry_point_mappings=entry_mappings,
            supported_platforms=platforms,
            object_keywords=object_keywords,
            prereq_template=f"Pre-req: The {app_name} is installed",
            launch_step=f"Launch the {app_name}.",
            launch_expected=launch_expected,
            close_step=f"Close the {app_name}.",
            confidence_score=0.9  # High confidence since user provided
        )

    async def discover_with_llm(self, app_name: str, context: str) -> DiscoveredApplication:
        """
        Use LLM to discover application characteristics from context.

        Args:
            app_name: Name of the application.
            context: Any context about the application (docs, stories, descriptions).

        Returns:
            DiscoveredApplication with LLM-inferred characteristics.
        """
        if not self.llm_provider:
            raise ValueError("LLM provider required for AI-assisted discovery")

        prompt = f"""Analyze this application and extract its characteristics for test case generation.

Application Name: {app_name}
Context: {context}

Return a JSON object with these fields:
- app_type: "desktop" | "web" | "mobile" | "hybrid"
- description: Brief description of the application
- ui_surfaces: List of main UI areas/surfaces (e.g., ["Dashboard", "Settings", "Navigation Menu"])
- platforms: List of supported platforms (e.g., ["Windows 11", "macOS", "iPad"])
- entry_point_mappings: Object mapping feature keywords to UI locations
- object_keywords: List of keywords indicating object interaction (e.g., ["record", "document", "item"])
- launch_expected: What happens when app launches successfully

Only return valid JSON, no explanation."""

        try:
            response = await self.llm_provider.generate(prompt)
            data = json.loads(response)

            return DiscoveredApplication(
                name=app_name,
                description=data.get('description', ''),
                app_type=data.get('app_type', 'desktop'),
                main_ui_surfaces=data.get('ui_surfaces', []),
                entry_point_mappings=data.get('entry_point_mappings', {}),
                supported_platforms=data.get('platforms', ['Windows 11']),
                object_keywords=data.get('object_keywords', []),
                prereq_template=f"Pre-req: The {app_name} is installed",
                launch_step=f"Launch the {app_name}.",
                launch_expected=data.get('launch_expected', 'Application loads successfully.'),
                close_step=f"Close the {app_name}.",
                confidence_score=0.8
            )
        except (json.JSONDecodeError, Exception) as e:
            print(f"LLM discovery failed: {e}")
            # Return minimal default
            return self._get_minimal_discovery(app_name)

    def create_project_config(
        self,
        discovery: DiscoveredApplication,
        project_id: str,
        ado_org: str,
        ado_project: str,
        area_path: str,
        **kwargs
    ) -> ProjectConfig:
        """
        Create a ProjectConfig from discovery results.

        Args:
            discovery: DiscoveredApplication result.
            project_id: Unique project identifier.
            ado_org: Azure DevOps organization.
            ado_project: Azure DevOps project name.
            area_path: ADO area path.
            **kwargs: Additional configuration options.

        Returns:
            Complete ProjectConfig ready for use.
        """
        application = ApplicationConfig(
            name=discovery.name,
            description=discovery.description,
            app_type=discovery.app_type,
            prereq_template=discovery.prereq_template,
            launch_step=discovery.launch_step,
            launch_expected=discovery.launch_expected,
            close_step=discovery.close_step,
            main_ui_surfaces=discovery.main_ui_surfaces,
            entry_point_mappings=discovery.entry_point_mappings,
            supported_platforms=discovery.supported_platforms,
            object_interaction_keywords=discovery.object_keywords,
        )

        ado = ADOProjectConfig(
            organization=ado_org,
            project=ado_project,
            area_path=area_path,
            assigned_to=kwargs.get('assigned_to', ''),
            default_state=kwargs.get('default_state', 'Design'),
            test_suite_pattern=kwargs.get('test_suite_pattern', '{story_id} : {story_name}'),
            qa_prep_pattern=kwargs.get('qa_prep_pattern'),
        )

        return ProjectConfig(
            project_id=project_id,
            application=application,
            ado=ado,
            output_dir=kwargs.get('output_dir', 'output'),
        )

    # ============ Private Helper Methods ============

    def _infer_app_type(self, text: str) -> str:
        """Infer application type from text content."""
        web_indicators = ['browser', 'website', 'web page', 'url', 'http', 'html', 'css', 'login page']
        mobile_indicators = ['tap', 'swipe', 'ios', 'android', 'phone', 'mobile app', 'gesture']
        desktop_indicators = ['install', 'desktop', 'window', 'menu bar', 'system tray']

        web_count = sum(1 for i in web_indicators if i in text)
        mobile_count = sum(1 for i in mobile_indicators if i in text)
        desktop_count = sum(1 for i in desktop_indicators if i in text)

        if web_count > mobile_count and web_count > desktop_count:
            return 'web'
        elif mobile_count > web_count and mobile_count > desktop_count:
            return 'mobile'
        else:
            return 'desktop'

    def _extract_ui_surfaces(self, text: str) -> List[str]:
        """Extract UI surface names from text."""
        surfaces = []
        common_surfaces = [
            'dashboard', 'settings', 'menu', 'toolbar', 'canvas', 'panel',
            'sidebar', 'header', 'footer', 'navigation', 'dialog', 'modal',
            'form', 'table', 'list', 'grid', 'workspace', 'editor'
        ]

        for surface in common_surfaces:
            if surface in text:
                surfaces.append(surface.title())

        # Also look for X Menu, X Panel patterns
        import re
        menu_pattern = r'\b(\w+)\s+menu\b'
        panel_pattern = r'\b(\w+)\s+panel\b'

        for match in re.finditer(menu_pattern, text):
            surfaces.append(f"{match.group(1).title()} Menu")

        for match in re.finditer(panel_pattern, text):
            surfaces.append(f"{match.group(1).title()} Panel")

        return list(set(surfaces))[:15]  # Limit to 15

    def _extract_platforms(self, text: str) -> List[str]:
        """Extract platform names from text."""
        platforms = []
        platform_map = {
            'windows 11': 'Windows 11',
            'windows 10': 'Windows 10',
            'windows': 'Windows',
            'macos': 'macOS',
            'mac os': 'macOS',
            'mac': 'macOS',
            'ipad': 'iPad',
            'ipados': 'iPad',
            'ios': 'iPhone',
            'iphone': 'iPhone',
            'android tablet': 'Android Tablet',
            'android phone': 'Android Phone',
            'android': 'Android',
            'chrome': 'Chrome',
            'firefox': 'Firefox',
            'safari': 'Safari',
            'edge': 'Edge',
        }

        for key, value in platform_map.items():
            if key in text:
                if value not in platforms:
                    platforms.append(value)

        return platforms if platforms else ['Windows 11']

    def _extract_object_keywords(self, text: str) -> List[str]:
        """Extract object/entity keywords that indicate interaction is needed."""
        keywords = []
        action_keywords = [
            'select', 'edit', 'delete', 'create', 'modify', 'move', 'resize',
            'rotate', 'copy', 'paste', 'drag', 'drop', 'click', 'update'
        ]

        for keyword in action_keywords:
            if keyword in text:
                keywords.append(keyword)

        return keywords

    def _infer_app_name(self, stories: List[Dict]) -> str:
        """Try to infer application name from story content."""
        # Look for common patterns in titles/descriptions
        for story in stories:
            title = story.get('title', '')
            # Look for "the X app" or "X application" patterns
            import re
            match = re.search(r'the\s+(\w+(?:\s+\w+)?)\s+(?:app|application)', title.lower())
            if match:
                return match.group(1).title()

        return "Application"

    def _build_entry_mappings(self, text: str, ui_surfaces: List[str]) -> Dict[str, str]:
        """Build entry point mappings based on context."""
        mappings = {}

        # Default mappings
        default_mappings = {
            'file': 'File Menu',
            'edit': 'Edit Menu',
            'view': 'View Menu',
            'tool': 'Tools Menu',
            'help': 'Help Menu',
            'setting': 'Settings',
            'preference': 'Settings',
        }

        for keyword, entry_point in default_mappings.items():
            if keyword in text:
                mappings[keyword] = entry_point

        # Add mappings based on discovered UI surfaces
        for surface in ui_surfaces:
            surface_lower = surface.lower()
            if 'menu' in surface_lower:
                # Extract the menu type
                menu_type = surface_lower.replace(' menu', '').strip()
                mappings[menu_type] = surface

        return mappings

    def _build_default_entry_mappings(self, ui_surfaces: List[str]) -> Dict[str, str]:
        """Build default entry point mappings from UI surfaces."""
        mappings = {
            'file': 'File Menu',
            'edit': 'Edit Menu',
            'view': 'View Menu',
            'setting': 'Settings',
        }

        for surface in ui_surfaces:
            surface_lower = surface.lower()
            if 'menu' in surface_lower:
                menu_type = surface_lower.replace(' menu', '').strip()
                mappings[menu_type] = surface
            elif 'panel' in surface_lower:
                panel_type = surface_lower.replace(' panel', '').strip()
                mappings[panel_type] = surface

        return mappings

    def _get_minimal_discovery(self, app_name: str) -> DiscoveredApplication:
        """Return minimal discovery result when LLM fails."""
        return DiscoveredApplication(
            name=app_name,
            description="",
            app_type="desktop",
            main_ui_surfaces=["Main Menu", "Toolbar", "Canvas"],
            entry_point_mappings={"file": "File Menu", "edit": "Edit Menu"},
            supported_platforms=["Windows 11"],
            object_keywords=["select", "edit", "delete"],
            prereq_template=f"Pre-req: The {app_name} is installed",
            launch_step=f"Launch the {app_name}.",
            launch_expected="Application loads successfully.",
            close_step=f"Close the {app_name}.",
            confidence_score=0.3
        )

    @staticmethod
    def get_discovery_questions() -> List[Dict]:
        """Get the list of discovery questions for interactive mode."""
        return ApplicationDiscovery.DISCOVERY_QUESTIONS
