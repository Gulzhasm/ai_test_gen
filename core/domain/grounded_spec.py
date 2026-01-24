"""
GroundedSpec: Evidence-backed specification extractor.

This module extracts ONLY explicit information from AC and QA Prep,
preventing the generator from inventing context.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
import re


@dataclass
class EntryPoint:
    """Represents an explicit entry point extracted from evidence."""
    path: str  # e.g., "View → Full Screen Mode", "Dimensions → Diameter"
    surface: str  # e.g., "View Menu", "Dimensions Menu"
    evidence_ref: str  # AC or QA Prep bullet ID


@dataclass
class Control:
    """Represents an explicit control mentioned in evidence."""
    name: str  # e.g., "Create", "Close", "ESC", "Diameter toggle"
    control_type: str  # e.g., "button", "toggle", "menu_item", "hotkey"
    evidence_ref: str


@dataclass
class PlatformRequirement:
    """Represents platform/device requirements from AC/QA Prep."""
    platform: str  # e.g., "Windows 11", "iPad", "Android Tablet"
    interaction_model: str  # e.g., "mouse/keyboard", "touch", "stylus"
    accessibility_tool: Optional[str] = None  # e.g., "Accessibility Insights", "VoiceOver"
    evidence_ref: str = ""


@dataclass
class GroundedSpec:
    """
    Evidence-backed specification that prevents invented context.

    This is the ONLY source of truth for:
    - Entry points (where the feature is accessed)
    - UI surfaces (menus, panels, dialogs)
    - Controls (buttons, toggles, etc.)
    - Platform requirements
    - Out-of-scope items

    If something is not in GroundedSpec, it MUST NOT appear in tests.
    """
    story_id: int
    feature_name: str

    # Explicit entry points from evidence
    entry_points: List[EntryPoint] = field(default_factory=list)

    # Explicit UI surfaces from evidence
    surfaces: Set[str] = field(default_factory=set)

    # Explicit controls from evidence
    controls: List[Control] = field(default_factory=list)

    # Platform requirements
    platform_requirements: List[PlatformRequirement] = field(default_factory=list)

    # Explicit out-of-scope items
    out_of_scope: Set[str] = field(default_factory=set)

    # Explicit constraints
    constraints: List[str] = field(default_factory=list)

    # Explicit object type requirements
    object_types: Set[str] = field(default_factory=set)

    # Explicit actions mentioned in AC
    actions: List[str] = field(default_factory=list)

    # Explicit negative scenarios
    negative_scenarios: Set[str] = field(default_factory=set)

    # Evidence bullets (for reference)
    ac_bullets: Dict[str, str] = field(default_factory=dict)  # {id: text}
    qa_prep_bullets: Dict[str, str] = field(default_factory=dict)  # {id: text}

    @classmethod
    def from_story_data(cls, story_data: Dict, criteria: List[str], qa_prep_content: Optional[str] = None) -> 'GroundedSpec':
        """
        Build GroundedSpec from story data and evidence.

        This method extracts ONLY explicit information from AC and QA Prep.
        """
        story_id = story_data.get('story_id') or story_data.get('id')
        feature_name = cls._extract_feature_name(story_data.get('title', ''))

        spec = cls(story_id=story_id, feature_name=feature_name)

        # FIRST: Extract primary entry point from description "Location: X → Y"
        description = story_data.get('description_text', '')
        primary_entry = cls._extract_location_from_description(description)
        if primary_entry:
            # Add as first entry point/surface
            spec.surfaces.add(primary_entry)
            # Also add as entry point if it's a menu/panel
            if any(word in primary_entry for word in ['Menu', 'Panel', 'Toolbar']):
                spec.entry_points.insert(0, EntryPoint(
                    path=primary_entry,
                    surface=primary_entry,
                    evidence_ref="Description"
                ))

        # Parse AC bullets
        for idx, ac_text in enumerate(criteria):
            ac_id = f"AC{idx + 1}"
            spec.ac_bullets[ac_id] = ac_text
            spec._extract_from_bullet(ac_text, ac_id)

        # Parse QA Prep bullets
        if qa_prep_content:
            qa_bullets = spec._parse_qa_prep_bullets(qa_prep_content)
            for idx, qa_text in enumerate(qa_bullets):
                qa_id = f"QA-{idx + 1}"
                spec.qa_prep_bullets[qa_id] = qa_text
                spec._extract_from_bullet(qa_text, qa_id)

        # FILTER OUT test tool names from surfaces (critical fix)
        spec._filter_test_tools()

        return spec

    def _extract_from_bullet(self, text: str, evidence_ref: str):
        """Extract explicit information from a single bullet."""
        text_lower = text.lower()

        # Extract entry points (patterns like "X → Y", "from X", "via X")
        self._extract_entry_points(text, evidence_ref)

        # Extract UI surfaces
        self._extract_surfaces(text, evidence_ref)

        # Extract controls
        self._extract_controls(text, evidence_ref)

        # Extract platform requirements
        self._extract_platform_requirements(text, evidence_ref)

        # Extract out-of-scope items
        self._extract_out_of_scope(text, evidence_ref)

        # Extract constraints
        self._extract_constraints(text, evidence_ref)

        # Extract object types
        self._extract_object_types(text, evidence_ref)

        # Extract actions
        self._extract_actions(text, evidence_ref)

        # Extract negative scenarios
        self._extract_negative_scenarios(text, evidence_ref)

    def _extract_entry_points(self, text: str, evidence_ref: str):
        """Extract explicit entry points like 'View → Full Screen Mode'."""
        # Whitelist of known menu names to prevent over-extraction
        KNOWN_MENUS = ['View', 'Edit', 'File', 'Tools', 'Window', 'Help', 'Dimensions', 'Properties']

        # Pattern 1: Menu arrow notation (View → Full Screen Mode)
        # Use whitelist to match only known menu names
        for menu in KNOWN_MENUS:
            # Match: "Menu → Option" where Menu is whitelisted
            pattern = rf'\b{menu}\s*[→\->]\s*([A-Z][a-zA-Z\s]+?)(?:\.|,|\n|$)'
            for match in re.finditer(pattern, text, re.IGNORECASE):
                option = match.group(1).strip()
                # Clean up option text (remove trailing punctuation, line breaks)
                option = re.sub(r'[,\.\n].*$', '', option).strip()

                path = f"{menu} → {option}"
                surface = f"{menu} Menu"

                self.entry_points.append(EntryPoint(
                    path=path,
                    surface=surface,
                    evidence_ref=evidence_ref
                ))
                self.surfaces.add(surface)
                break  # Only take first match per menu type

        # Pattern 2: "from the X menu/panel"
        from_pattern = r'from (?:the )?([A-Z][a-zA-Z\s]+?(?:menu|panel|toolbar|dialog|screen))'
        for match in re.finditer(from_pattern, text, re.IGNORECASE):
            surface = match.group(1).strip()
            # Normalize surface name
            if not any(word in surface.lower() for word in ['menu', 'panel', 'toolbar', 'dialog', 'screen']):
                surface = f"{surface} Menu"

            self.surfaces.add(surface)

        # Pattern 3: "via the X menu/panel"
        via_pattern = r'via (?:the )?([A-Z][a-zA-Z\s]+?(?:menu|panel|toolbar|dialog))'
        for match in re.finditer(via_pattern, text, re.IGNORECASE):
            surface = match.group(1).strip()
            self.surfaces.add(surface)

        # Pattern 4: "in the X menu/panel"
        in_pattern = r'in (?:the )?([A-Z][a-zA-Z\s]+?(?:menu|panel|toolbar|dialog))'
        for match in re.finditer(in_pattern, text, re.IGNORECASE):
            surface = match.group(1).strip()
            self.surfaces.add(surface)

    def _extract_surfaces(self, text: str, evidence_ref: str):
        """Extract UI surfaces (menus, panels, dialogs, etc.)."""
        surface_pattern = r'([A-Z][a-zA-Z\s]+?(?:Menu|Panel|Toolbar|Dialog|Screen|Window))'
        for match in re.finditer(surface_pattern, text):
            surface = match.group(1).strip()
            self.surfaces.add(surface)

    def _extract_controls(self, text: str, evidence_ref: str):
        """Extract explicit controls (buttons, toggles, etc.)."""
        text_lower = text.lower()

        # Toggle controls
        toggle_pattern = r'([A-Z][a-zA-Z\s]+?)\s+toggle'
        for match in re.finditer(toggle_pattern, text, re.IGNORECASE):
            control_name = match.group(1).strip() + " toggle"
            self.controls.append(Control(
                name=control_name,
                control_type="toggle",
                evidence_ref=evidence_ref
            ))

        # Button controls (look for action verbs + context)
        if 'create' in text_lower or 'close' in text_lower:
            if 'create' in text_lower:
                self.controls.append(Control(name="Create", control_type="button", evidence_ref=evidence_ref))
            if 'close' in text_lower:
                self.controls.append(Control(name="Close", control_type="button", evidence_ref=evidence_ref))

        # Hotkeys (ESC, Ctrl+Z, etc.)
        hotkey_pattern = r'\b(ESC|Enter|Ctrl\+\w+|Cmd\+\w+)\b'
        for match in re.finditer(hotkey_pattern, text, re.IGNORECASE):
            hotkey = match.group(1)
            self.controls.append(Control(
                name=hotkey,
                control_type="hotkey",
                evidence_ref=evidence_ref
            ))

    def _extract_platform_requirements(self, text: str, evidence_ref: str):
        """Extract platform/device requirements."""
        text_lower = text.lower()

        # Windows
        if any(word in text_lower for word in ['windows', 'win11', 'mouse', 'keyboard']):
            # Check if accessibility tool is mentioned
            accessibility_tool = None
            if 'accessibility insights' in text_lower:
                accessibility_tool = 'Accessibility Insights for Windows'

            # Only add if not already present
            if not any(p.platform == 'Windows 11' for p in self.platform_requirements):
                self.platform_requirements.append(PlatformRequirement(
                    platform='Windows 11',
                    interaction_model='mouse/keyboard',
                    accessibility_tool=accessibility_tool,
                    evidence_ref=evidence_ref
                ))

        # iPad
        if 'ipad' in text_lower or 'ipados' in text_lower:
            accessibility_tool = None
            if 'voiceover' in text_lower:
                accessibility_tool = 'VoiceOver'

            if not any(p.platform == 'iPad' for p in self.platform_requirements):
                self.platform_requirements.append(PlatformRequirement(
                    platform='iPad',
                    interaction_model='touch',
                    accessibility_tool=accessibility_tool,
                    evidence_ref=evidence_ref
                ))

        # Android Tablet
        if 'android' in text_lower and 'tablet' in text_lower:
            accessibility_tool = None
            if 'accessibility scanner' in text_lower or 'talkback' in text_lower:
                accessibility_tool = 'Accessibility Scanner'

            if not any(p.platform == 'Android Tablet' for p in self.platform_requirements):
                self.platform_requirements.append(PlatformRequirement(
                    platform='Android Tablet',
                    interaction_model='touch',
                    accessibility_tool=accessibility_tool,
                    evidence_ref=evidence_ref
                ))

    def _extract_out_of_scope(self, text: str, evidence_ref: str):
        """Extract explicit out-of-scope items."""
        text_lower = text.lower()

        # Look for "out of scope", "not included", "excluded", etc.
        if 'out of scope' in text_lower or 'not included' in text_lower:
            # Extract what's out of scope
            out_of_scope_pattern = r'(?:out of scope|not included|excluded)[:\s]+([^.]+)'
            for match in re.finditer(out_of_scope_pattern, text_lower):
                item = match.group(1).strip()
                self.out_of_scope.add(item)

        # Common out-of-scope items
        if 'template' in text_lower and ('out of scope' in text_lower or 'not' in text_lower):
            self.out_of_scope.add('templates')
        if 'tooltip' in text_lower and ('out of scope' in text_lower or 'not' in text_lower):
            self.out_of_scope.add('tooltips')
        if 'hotkey' in text_lower and ('out of scope' in text_lower or 'not' in text_lower):
            self.out_of_scope.add('hotkey hints')
        if 'landscape' in text_lower and ('out of scope' in text_lower or 'not' in text_lower):
            self.out_of_scope.add('landscape mode')

    def _extract_constraints(self, text: str, evidence_ref: str):
        """Extract explicit constraints."""
        text_lower = text.lower()

        # Fixed placement
        if 'cannot be' in text_lower and 'reposition' in text_lower:
            self.constraints.append('Fixed placement - cannot be repositioned')

        # Angle constraints (0-360, wrap, etc.)
        if '360' in text or 'wrap' in text_lower:
            self.constraints.append('Angle wraps at 360°')

        # Maximum/minimum constraints
        max_pattern = r'maximum\s+(?:of\s+)?(\d+|\w+)'
        for match in re.finditer(max_pattern, text_lower):
            value = match.group(1)
            self.constraints.append(f'Maximum: {value}')

        min_pattern = r'minimum\s+(?:of\s+)?(\d+|\w+)'
        for match in re.finditer(min_pattern, text_lower):
            value = match.group(1)
            self.constraints.append(f'Minimum: {value}')

    def _extract_object_types(self, text: str, evidence_ref: str):
        """Extract explicit object type requirements."""
        text_lower = text.lower()

        # Standard object types
        object_keywords = {
            'ellipse': 'ellipse',
            'circle': 'circle',
            'rectangle': 'rectangle',
            'square': 'square',
            'triangle': 'triangle',
            'arrow': 'arrow',
            'line': 'line',
            'polygon': 'polygon',
            'text': 'text'
        }

        for keyword, obj_type in object_keywords.items():
            if keyword in text_lower:
                self.object_types.add(obj_type)

    def _extract_actions(self, text: str, evidence_ref: str):
        """Extract explicit actions mentioned in AC."""
        text_lower = text.lower()

        # Action verbs
        action_verbs = [
            'create', 'add', 'remove', 'delete', 'enable', 'disable',
            'toggle', 'activate', 'deactivate', 'show', 'hide',
            'move', 'rotate', 'scale', 'resize', 'flip', 'mirror',
            'undo', 'redo', 'select', 'deselect'
        ]

        for verb in action_verbs:
            if verb in text_lower:
                self.actions.append(verb)

    def _extract_negative_scenarios(self, text: str, evidence_ref: str):
        """Extract explicit negative scenarios."""
        text_lower = text.lower()

        # No selection
        if 'no selection' in text_lower or 'without selection' in text_lower or 'no object selected' in text_lower:
            self.negative_scenarios.add('no_selection')

        # Empty canvas
        if 'empty canvas' in text_lower or 'no objects' in text_lower:
            self.negative_scenarios.add('empty_canvas')

        # Wrong object type
        if 'non-ellipse' in text_lower or 'wrong object' in text_lower or 'incompatible object' in text_lower:
            self.negative_scenarios.add('wrong_object_type')

        # Invalid input
        if 'invalid' in text_lower or 'incorrect' in text_lower:
            self.negative_scenarios.add('invalid_input')

    def _parse_qa_prep_bullets(self, qa_prep: str) -> List[str]:
        """Parse QA Prep content into individual bullets."""
        bullets = []
        for line in qa_prep.split('\n'):
            line = line.strip()
            if line and (line.startswith('-') or line.startswith('•') or line.startswith('*')):
                bullet_text = re.sub(r'^[-•*]\s*', '', line)
                if bullet_text:
                    bullets.append(bullet_text)
            elif line and len(line) > 10:
                bullets.append(line)
        return bullets

    @staticmethod
    def _extract_feature_name(story_title: str) -> str:
        """Extract feature name from story title."""
        title = story_title.strip()
        for prefix in ['As a', 'As an', 'I want', 'I need', 'User can', 'Users can']:
            if title.lower().startswith(prefix.lower()):
                parts = title.split(',')
                if len(parts) > 1:
                    title = parts[1].strip() if 'so that' not in parts[1].lower() else parts[0].replace(prefix, '').strip()
                else:
                    title = title.replace(prefix, '').strip()
                break
        return title

    @staticmethod
    def _extract_location_from_description(description: str) -> Optional[str]:
        """
        Extract primary entry point from 'Location: X → Y' or 'Location: X' in description.

        Returns the primary location (e.g., 'Properties Panel', 'Tools Menu').
        """
        if not description:
            return None

        # Pattern 1: "Location: Properties Panel → Typography"
        # We want "Properties Panel" as the primary entry
        location_pattern = r'Location:\s*([^→\n]+?)(?:\s*→\s*([^\n]+?))?(?:\n|$)'
        match = re.search(location_pattern, description, re.IGNORECASE)
        if match:
            primary_location = match.group(1).strip()
            # Clean up (remove trailing punctuation)
            primary_location = re.sub(r'[,;].*$', '', primary_location).strip()
            return primary_location

        # Pattern 2: "Menu → Tools" at start of line
        # Extract "Tools Menu" as entry point
        menu_pattern = r'(?:^|\n)Menu\s*→\s*([A-Z][a-zA-Z\s]+)'
        match = re.search(menu_pattern, description)
        if match:
            menu_name = match.group(1).strip()
            # Remove trailing punctuation/newlines
            menu_name = re.sub(r'[,\.\n].*$', '', menu_name).strip()
            return f"{menu_name} Menu"

        return None

    def _filter_test_tools(self):
        """
        Remove test tool names from surfaces.

        Test tools should not appear as test title areas.
        """
        TEST_TOOLS = [
            'Accessibility Insights',
            'VoiceOver',
            'Accessibility Scanner',
            'Narrator',
            'TalkBack',
            'JAWS',
            'NVDA'
        ]

        # Filter surfaces
        filtered_surfaces = set()
        for surface in self.surfaces:
            is_test_tool = any(tool in surface for tool in TEST_TOOLS)
            if not is_test_tool:
                filtered_surfaces.add(surface)

        self.surfaces = filtered_surfaces

    def get_primary_entry_point(self) -> Optional[str]:
        """Get the primary entry point surface, or None if not found."""
        if self.entry_points:
            return self.entry_points[0].surface
        elif self.surfaces:
            return list(self.surfaces)[0]
        return None

    def has_entry_point(self, surface: str) -> bool:
        """Check if a surface is a valid entry point."""
        return surface in self.surfaces or any(ep.surface == surface for ep in self.entry_points)

    def get_platforms(self) -> List[str]:
        """Get list of platform names."""
        return [pr.platform for pr in self.platform_requirements]

    def has_platform(self, platform: str) -> bool:
        """Check if a platform is mentioned in evidence."""
        return any(pr.platform == platform for pr in self.platform_requirements)

    def is_out_of_scope(self, item: str) -> bool:
        """Check if an item is explicitly out of scope."""
        return item.lower() in {s.lower() for s in self.out_of_scope}

    def get_evidence_summary(self) -> str:
        """Get a summary of extracted evidence for debugging."""
        summary = f"GroundedSpec for Story {self.story_id}: {self.feature_name}\n"
        summary += f"  Entry Points: {len(self.entry_points)}\n"
        for ep in self.entry_points:
            summary += f"    - {ep.path} (from {ep.evidence_ref})\n"
        summary += f"  Surfaces: {', '.join(self.surfaces) or 'None'}\n"
        summary += f"  Controls: {len(self.controls)}\n"
        summary += f"  Platforms: {', '.join(self.get_platforms()) or 'None'}\n"
        summary += f"  Object Types: {', '.join(self.object_types) or 'None'}\n"
        summary += f"  Out of Scope: {', '.join(self.out_of_scope) or 'None'}\n"
        summary += f"  Negative Scenarios: {', '.join(self.negative_scenarios) or 'None'}\n"
        return summary
