"""
QA Planning Summary Generator Module
Generates QA Planning Summary for user stories following approved format.

Refactored to use SummaryPlan pattern with evidence-based guardrails.
"""
import re
from typing import Dict, List, Tuple, Optional, Set
from models import SummaryPlan, UserStory, TestCase


class QASummaryGenerator:
    """Generates QA Planning Summary from user story and test cases."""
    
    # Forbidden speculative language (always forbidden)
    FORBIDDEN_SPECULATIVE = [
        'assumingly', 'likely', 'generally', 'presumably', 'should', 'may',
        'expected behavior', 'correct functionality', 'feature works',
        'all requirements', 'basic information', 'general behavior',
        'should be correct', 'no issues found', 'works as expected',
        'as expected'
    ]
    
    # Valid UI surfaces (only mention if in evidence)
    VALID_UI_SURFACES = [
        'File Menu', 'Edit Menu', 'Tools Menu', 'Help Menu',
        'Properties Panel', 'Dimensions Panel', 'Canvas',
        'Dialog Window', 'Modal Window', 'Top Action Toolbar'
    ]
    
    def __init__(self, debug: bool = False):
        """Initialize generator.
        
        Args:
            debug: Enable debug mode to print extraction details
        """
        self.debug = debug
    
    def generate_summary(self, story_data: Dict, test_cases: List[Dict]) -> str:
        """Generate QA Planning Summary from story data and test cases.
        
        Args:
            story_data: Dict with story_id, title, description_text, acceptance_criteria_text
            test_cases: List of test case dicts with id, title, steps, area, is_accessibility, device
        
        Returns:
            Formatted QA Planning Summary text
        """
        # Convert to UserStory model
        story = UserStory(
            story_id=story_data.get('story_id', 0),
            title=story_data.get('title', ''),
            description=story_data.get('description_text', ''),
            acceptance_criteria=story_data.get('acceptance_criteria_text', '') or story_data.get('acceptance_criteria', '')
        )
        
        # Convert test cases to TestCase models
        test_case_models = self._convert_test_cases(test_cases)
        
        # Phase A: Build deterministic SummaryPlan
        plan = self._build_summary_plan(story, test_case_models)
        
        # Phase B: Render summary
        summary_text = self._render_summary(plan)
        
        # Lint and validate
        lint_errors = self._lint_summary(summary_text, story, test_case_models)
        if lint_errors:
            if self.debug:
                print(f"[DEBUG] Lint errors found: {lint_errors}")
            # Regenerate plan if lint fails
            plan = self._build_summary_plan(story, test_case_models)
            summary_text = self._render_summary(plan)
        
        return summary_text
    
    def _convert_test_cases(self, test_cases: List[Dict]) -> List[TestCase]:
        """Convert dict test cases to TestCase models."""
        result = []
        for tc in test_cases:
            steps = []
            for i, step in enumerate(tc.get('steps', []), 1):
                from models import TestStep
                steps.append(TestStep(
                    index=i,
                    action=step.get('action', ''),
                    expected=step.get('expected', '')
                ))
            
            result.append(TestCase(
                test_id=tc.get('id', ''),
                title=tc.get('title', ''),
                steps=steps,
                area=tc.get('area', ''),
                requires_object=tc.get('requires_object', False),
                is_accessibility=tc.get('is_accessibility', False),
                device=tc.get('device')
            ))
        return result
    
    def _build_summary_plan(self, story: UserStory, test_cases: List[TestCase]) -> SummaryPlan:
        """Phase A: Build deterministic SummaryPlan from evidence.
        
        Args:
            story: UserStory model
            test_cases: List of TestCase models
            
        Returns:
            SummaryPlan with all sections populated
        """
        # Build evidence
        evidence_text = f"{story.description} {story.acceptance_criteria}".lower()
        test_titles = [tc.title.lower() for tc in test_cases]
        
        # Extract intro
        intro = self._build_intro(story, evidence_text)
        
        # Extract and normalize bullets
        bullets = self._build_bullets(story, evidence_text, test_titles)
        
        # Extract dependencies
        dependencies = self._extract_dependencies(evidence_text, test_titles)
        
        # Build accessibility clause
        accessibility_clause = self._build_accessibility_clause(evidence_text, test_cases)
        
        # Fixed platform clause
        platform_clause = (
            "Tests will be executed on Windows 11 and tablet devices "
            "(iOS iPad and Android Tablet) to validate consistent behavior "
            "across mouse-based and touch-based interaction models."
        )
        
        return SummaryPlan(
            intro_facts=intro,
            bullet_themes=bullets,
            dependencies=dependencies,
            accessibility_clause=accessibility_clause,
            platform_clause=platform_clause
        )
    
    def _build_intro(self, story: UserStory, evidence_text: str) -> str:
        """Build intro paragraph (1-2 sentences, ChatGPT-style polished).
        
        Rules:
        - No quotes
        - No "Acceptance Criteria"
        - Polished, professional language
        - Describes feature purpose and intent
        """
        # Extract feature name from title
        feature_name = self._extract_feature_name(story.title)
        
        # Extract primary capability and purpose from description/AC
        capability_desc = self._extract_capability_description(story.description, evidence_text, feature_name)
        
        # Extract UI entry points (evidence-based only)
        entry_points = self._extract_entry_points_evidence(evidence_text, feature_name)
        
        # Build polished intro matching ChatGPT style
        if 'about' in feature_name.lower() or 'information' in evidence_text.lower():
            # About/Info features - clean up feature name
            clean_feature_name = feature_name
            if ':' in clean_feature_name:
                # Extract part after colon (e.g., "Help: About App" -> "About App")
                parts = clean_feature_name.split(':', 1)
                if len(parts) > 1:
                    clean_feature_name = parts[1].strip()
            
            # Fix article (an vs a)
            article = "an" if clean_feature_name.lower().startswith(('a', 'e', 'i', 'o', 'u')) else "a"
            
            if entry_points:
                # Use proper menu name or generic
                if len(entry_points) == 1:
                    menu_name = entry_points[0]
                    if 'help' in menu_name.lower():
                        entry_text = "the Help menu"
                    elif 'tools' in menu_name.lower():
                        entry_text = "the Tools menu"
                    else:
                        entry_text = menu_name.lower()
                else:
                    entry_text = 'a standard menu entry'
                intro = (
                    f"This work item introduces {article} {clean_feature_name} informational view that provides users "
                    f"with essential application details through {entry_text}. "
                    f"The feature is intended to offer clear, read-only visibility into version and support "
                    f"information without altering application state or workflow."
                )
            else:
                intro = (
                    f"This work item introduces {article} {clean_feature_name} informational view that provides users "
                    f"with essential application details. "
                    f"The feature is intended to offer clear, read-only visibility into version and support "
                    f"information without altering application state or workflow."
                )
        else:
            # Generic features (tools, actions, etc.) - ChatGPT-style professional intro
            clean_feature_name = feature_name
            if ':' in clean_feature_name:
                # Extract part after colon if present
                parts = clean_feature_name.split(':', 1)
                if len(parts) > 1:
                    clean_feature_name = parts[1].strip()
            
            # Build professional intro based on capability
            if entry_points:
                if len(entry_points) == 1:
                    entry_text = entry_points[0].lower()
                    if 'menu' in entry_text:
                        intro = (
                            f"This work item introduces {clean_feature_name} that provides users with "
                            f"{capability_desc} through {entry_text}. "
                            f"The feature enables precise manipulation and control of selected objects "
                            f"within the application workspace."
                        )
                    else:
                        intro = (
                            f"This work item introduces {clean_feature_name} that provides users with "
                            f"{capability_desc} through {entry_text}. "
                            f"The feature enables precise manipulation and control of selected objects "
                            f"within the application workspace."
                        )
                else:
                    entry_text = ', '.join(entry_points[:-1]) + f', and {entry_points[-1]}'
                    intro = (
                        f"This work item introduces {clean_feature_name} that provides users with "
                        f"{capability_desc} through {entry_text}. "
                        f"The feature enables precise manipulation and control of selected objects "
                        f"within the application workspace."
                    )
            else:
                intro = (
                    f"This work item introduces {clean_feature_name} that provides users with "
                    f"{capability_desc}. "
                    f"The feature enables precise manipulation and control of selected objects "
                    f"within the application workspace."
                )
        
        # Ensure 1-2 sentences max
        sentences = [s.strip() for s in intro.split('.') if s.strip()]
        if len(sentences) > 2:
            intro = '. '.join(sentences[:2]) + '.'
        
        return intro
    
    def _extract_feature_name(self, title: str) -> str:
        """Extract feature name from story title."""
        # Remove common prefixes
        title_clean = title.strip()
        for prefix in ['As a', 'As an', 'I want', 'I need']:
            if title_clean.lower().startswith(prefix.lower()):
                # Extract after comma or colon
                if ',' in title_clean:
                    title_clean = title_clean.split(',', 1)[1].strip()
                elif ':' in title_clean:
                    title_clean = title_clean.split(':', 1)[1].strip()
                else:
                    title_clean = title_clean[len(prefix):].strip()
                break
        
        # Clean up
        title_clean = title_clean.strip('.,;')
        return title_clean if title_clean else title
    
    def _extract_capability_description(self, description: str, evidence_text: str, feature_name: str) -> str:
        """Extract capability description for intro (ChatGPT-style polished)."""
        feature_lower = feature_name.lower()
        desc_lower = description.lower()
        evidence_lower = evidence_text.lower()
        
        # Tool features - check for rotation and movement
        if 'rotate' in evidence_lower and 'move' in evidence_lower:
            return "rotating and moving selected objects"
        elif 'rotate' in evidence_lower:
            return "rotating selected objects"
        elif 'move' in evidence_lower and 'object' in evidence_lower:
            return "moving selected objects"
        
        # Check for explicit capabilities
        if 'view' in evidence_lower or 'display' in evidence_lower or 'show' in evidence_lower:
            if 'about' in feature_lower or 'information' in evidence_lower:
                return "viewing application information"
            return "viewing content"
        elif 'flip' in evidence_lower:
            if 'horizontally' in evidence_lower or 'vertically' in evidence_lower:
                return "flipping objects horizontally or vertically"
            return "flipping objects"
        elif 'mirror' in evidence_lower:
            return "mirroring selected objects"
        elif 'select' in evidence_lower:
            return "selecting options"
        elif 'edit' in evidence_lower or 'modify' in evidence_lower:
            return "editing content"
        elif 'create' in evidence_lower:
            return "creating content"
        elif 'delete' in evidence_lower or 'remove' in evidence_lower:
            return "deleting content"
        else:
            # Generic fallback
            if 'tool' in feature_lower:
                # Try to extract what the tool does from evidence
                if 'rotate' in evidence_lower:
                    return "rotating selected objects"
                elif 'move' in evidence_lower:
                    return "moving selected objects"
                else:
                    return "manipulating selected objects"
            elif 'menu' in evidence_lower:
                return "accessing menu options"
            else:
                return "interacting with the feature"
    
    def _extract_entry_points_evidence(self, evidence_text: str, feature_name: str) -> List[str]:
        """Extract UI entry points from evidence only (no invention)."""
        entry_points = []
        
        # Check each valid UI surface - must be exact match in evidence
        for surface in self.VALID_UI_SURFACES:
            surface_lower = surface.lower()
            # Check exact match in evidence (word boundary)
            pattern = r'\b' + re.escape(surface_lower) + r'\b'
            if re.search(pattern, evidence_text):
                entry_points.append(surface)
        
        # Remove duplicates while preserving order
        seen = set()
        result = []
        for ep in entry_points:
            if ep not in seen:
                seen.add(ep)
                result.append(ep)
        
        return result
    
    def _build_bullets(self, story: UserStory, evidence_text: str, test_titles: List[str]) -> List[str]:
        """Build 7-10 professional ChatGPT-style bullet themes from AC.
        
        Creates polished, professional statements matching ChatGPT template style.
        """
        # Parse AC into raw bullets
        ac_bullets = self._parse_acceptance_criteria(story.acceptance_criteria)
        
        # Build professional bullets from AC patterns
        professional_bullets = []
        
        # Pattern 1: Menu/tool entry availability and activation (generic)
        if any('appears' in b.lower() and 'menu' in b.lower() for b in ac_bullets):
            menu_bullet = self._create_menu_availability_bullet(ac_bullets, evidence_text)
            if menu_bullet:
                professional_bullets.append(menu_bullet)
        elif any('activate' in b.lower() and ('menu' in b.lower() or 'tool' in b.lower()) for b in ac_bullets):
            professional_bullets.append("Availability of the tool from the expected menu location and correct activation behavior")
        
        # Pattern 2: Tool activation and behavior (for tool features)
        if any('activate' in b.lower() and ('tool' in b.lower() or 'rotate' in b.lower() or 'move' in b.lower()) for b in ac_bullets):
            if any('select' in b.lower() and ('shape' in b.lower() or 'object' in b.lower()) for b in ac_bullets):
                professional_bullets.append("Correct activation behavior when objects are selected, ensuring the tool becomes active and ready for interaction")
            else:
                professional_bullets.append("Correct activation behavior of the tool, ensuring it becomes active and ready for interaction")
        
        # Pattern 3: Core functionality - rotation
        if any('rotate' in b.lower() for b in ac_bullets):
            if any('marker' in b.lower() or 'handle' in b.lower() for b in ac_bullets):
                professional_bullets.append("Proper rotation behavior using the rotation marker, including smooth interaction and accurate angle changes")
            else:
                professional_bullets.append("Proper rotation functionality, enabling users to rotate selected objects to desired orientations")
        
        # Pattern 4: Core functionality - movement
        if any('move' in b.lower() and 'object' in b.lower() for b in ac_bullets):
            professional_bullets.append("Accurate movement behavior, allowing precise positioning of selected objects within the workspace")
        
        # Pattern 5: Interaction patterns - click and drag
        if any('click' in b.lower() and 'drag' in b.lower() for b in ac_bullets):
            professional_bullets.append("Correct click-and-drag interaction behavior, providing responsive and predictable manipulation")
        
        # Pattern 6: Keyboard accessibility
        if any('keyboard' in b.lower() or ('key' in b.lower() and ('shortcut' in b.lower() or 'navigation' in b.lower())) for b in ac_bullets):
            professional_bullets.append("Keyboard accessibility and navigation support, ensuring the tool can be activated and controlled via keyboard input")
        
        # Pattern 7: Constrained interaction (shift key, etc.)
        if any('shift' in b.lower() and ('constrain' in b.lower() or 'snap' in b.lower() or 'increment' in b.lower()) for b in ac_bullets):
            professional_bullets.append("Constrained interaction behavior when modifier keys are used, providing precise control and predictable increments")
        
        # Pattern 8: State management - undo/redo
        if any('undo' in b.lower() or 'redo' in b.lower() for b in ac_bullets):
            professional_bullets.append("Proper integration with undo/redo functionality, ensuring tool operations can be reversed and restored correctly")
        
        # Pattern 9: Selection behavior
        if any('select' in b.lower() and ('object' in b.lower() or 'shape' in b.lower()) for b in ac_bullets):
            if any('deselect' in b.lower() or 'deactivate' in b.lower() for b in ac_bullets):
                professional_bullets.append("Correct selection and deselection behavior, maintaining proper tool state when objects are selected or deselected")
        
        # Pattern 10: Edge cases - empty canvas/no selection
        if any('empty' in b.lower() and ('canvas' in b.lower() or 'selection' in b.lower()) for b in ac_bullets):
            professional_bullets.append("Appropriate behavior when no objects are selected or the canvas is empty, preventing unintended tool activation")
        
        # Pattern 11: Tool switching
        if any('switch' in b.lower() or ('change' in b.lower() and 'tool' in b.lower()) for b in ac_bullets):
            professional_bullets.append("Correct tool switching behavior, ensuring proper deactivation of the previous tool when switching to another tool")
        
        # Pattern 12: Window/dialog rendering (for dialog-based features)
        if any('opens' in b.lower() and ('window' in b.lower() or 'dialog' in b.lower()) for b in ac_bullets):
            professional_bullets.append("Proper rendering of the dialog window, including layout, visibility, and appropriate presentation")
        
        # Pattern 13: Application metadata display (for informational features)
        metadata_items = []
        if any('application name' in b.lower() or 'app name' in b.lower() for b in ac_bullets):
            metadata_items.append('application name')
        if any('version' in b.lower() and 'string' in b.lower() for b in ac_bullets):
            metadata_items.append('full installed version string')
        if any('copyright' in b.lower() for b in ac_bullets):
            metadata_items.append('dynamic copyright text')
        
        if metadata_items:
            if len(metadata_items) == 1:
                professional_bullets.append(f"Accurate display of {metadata_items[0]}")
            else:
                items_text = ', '.join(metadata_items[:-1]) + f', and {metadata_items[-1]}'
                professional_bullets.append(f"Accurate display of core application metadata, including {items_text}")
        
        # Pattern 14: Support link functionality (for informational features)
        if any('link' in b.lower() and ('clickable' in b.lower() or 'opens' in b.lower() or 'browser' in b.lower()) for b in ac_bullets):
            professional_bullets.append("Presence and functionality of the support link, ensuring it launches the correct destination in the default browser")
        
        # Pattern 15: Window dismissal (for dialog features)
        if any('close' in b.lower() or 'dismiss' in b.lower() for b in ac_bullets):
            professional_bullets.append("Correct dismissal behavior of the window using provided close controls, without impacting the active session")
        
        # Pattern 16: Absence of extra elements
        if any('no additional' in b.lower() or 'no extra' in b.lower() or ('only' in b.lower() and 'required' in b.lower()) for b in ac_bullets):
            professional_bullets.append("Absence of unintended inputs, settings, or actions beyond the defined feature scope")
        
        # Pattern 17: Additional AC items as professional statements
        for ac_bullet in ac_bullets:
            if len(professional_bullets) >= 10:
                break
            
            # Skip if already covered by patterns above
            ac_lower = ac_bullet.lower()
            covered_patterns = [
                'appears', 'menu', 'opens', 'window', 'displays', 'name', 'version', 'link', 'close',
                'no additional', 'activate', 'rotate', 'move', 'select', 'undo', 'redo', 'empty',
                'switch', 'keyboard', 'shift', 'click', 'drag'
            ]
            if any(pattern in ac_lower for pattern in covered_patterns):
                continue
            
            # Skip fragments (very short or incomplete thoughts)
            if len(ac_bullet.split()) < 4:
                continue
            
            # Skip if it's just a verb or action without context
            if ac_lower.startswith(('activate', 'proper', 'correct')) and len(ac_bullet.split()) < 6:
                continue
            
            # Skip specific fragment patterns
            if re.match(r'^(proper|correct)\s+(activate|"|about)', ac_lower):
                continue
            if re.match(r'^"about\s+app"\s+appears', ac_lower):
                continue
            
            # Create professional statement from remaining AC
            normalized = self._normalize_single_bullet(ac_bullet, evidence_text)
            if normalized and normalized not in professional_bullets and len(normalized.split()) >= 6:
                # Skip if it's still a fragment after normalization
                normalized_lower = normalized.lower()
                if normalized_lower.startswith('proper ') and len(normalized.split()) < 8:
                    continue
                # Skip specific fragment patterns after normalization
                if re.match(r'^proper\s+(activate|"|about)', normalized_lower):
                    continue
                if re.match(r'^"about\s+app"\s+appears', normalized_lower):
                    continue
                professional_bullets.append(normalized)
        
        # Ensure 7-10 bullets - add test-case derived bullets if needed
        if len(professional_bullets) < 7:
            test_bullets = self._derive_bullets_from_tests(test_titles, evidence_text)
            for tb in test_bullets:
                if len(professional_bullets) >= 10:
                    break
                if tb and tb not in professional_bullets and len(tb.split()) >= 6:
                    professional_bullets.append(tb)
        
        # Deduplicate
        deduplicated = self._deduplicate_bullets(professional_bullets)
        
        # Ensure minimum 7 bullets - extract from AC if still needed
        while len(deduplicated) < 7 and len(ac_bullets) > 0:
            for ac_bullet in ac_bullets:
                if len(deduplicated) >= 7:
                    break
                # Skip very short fragments
                if len(ac_bullet.split()) < 4:
                    continue
                # Skip fragment patterns before normalization
                ac_lower = ac_bullet.lower()
                if re.match(r'^(proper|correct)\s+(activate|"|about)', ac_lower):
                    continue
                if re.match(r'^"about\s+app"\s+appears', ac_lower):
                    continue
                normalized = self._normalize_single_bullet(ac_bullet, evidence_text)
                if normalized and normalized not in deduplicated and len(normalized.split()) >= 6:
                    # Skip if it's still a fragment after normalization
                    normalized_lower = normalized.lower()
                    if normalized_lower.startswith('proper ') and len(normalized.split()) < 8:
                        continue
                    if normalized_lower.startswith('correct behavior for') and len(normalized.split()) < 8:
                        continue
                    # Skip specific fragment patterns
                    if re.match(r'^proper\s+(activate|"|about)', normalized_lower):
                        continue
                    if re.match(r'^"about\s+app"\s+appears', normalized_lower):
                        continue
                    deduplicated.append(normalized)
            break  # Prevent infinite loop
        
        # If still not enough bullets, create generic ones from test titles
        if len(deduplicated) < 7:
            # Extract key behaviors from test titles
            behaviors = []
            for title in test_titles[:15]:  # Check first 15 test titles
                title_lower = title.lower()
                if 'activate' in title_lower and 'tool' in title_lower and 'activation' not in ' '.join(deduplicated).lower():
                    behaviors.append("tool activation")
                if 'rotate' in title_lower and 'rotation' not in ' '.join(deduplicated).lower():
                    behaviors.append("rotation functionality")
                if 'move' in title_lower and 'movement' not in ' '.join(deduplicated).lower():
                    behaviors.append("movement functionality")
                if 'keyboard' in title_lower and 'keyboard' not in ' '.join(deduplicated).lower():
                    behaviors.append("keyboard navigation")
                if ('undo' in title_lower or 'redo' in title_lower) and 'undo' not in ' '.join(deduplicated).lower():
                    behaviors.append("undo/redo integration")
            
            # Create bullets from behaviors
            for behavior in behaviors[:5]:  # Max 5 additional
                if len(deduplicated) >= 7:
                    break
                bullet = f"Proper {behavior} behavior, ensuring correct and predictable operation"
                if bullet not in deduplicated:
                    deduplicated.append(bullet)
        
        return deduplicated[:10]  # Max 10 bullets
    
    def _create_menu_availability_bullet(self, ac_bullets: List[str], evidence_text: str) -> Optional[str]:
        """Create professional menu availability bullet."""
        for bullet in ac_bullets:
            bullet_lower = bullet.lower()
            if 'appears' in bullet_lower and 'menu' in bullet_lower:
                # Extract feature name and menu name
                menu_match = re.search(r'\b(help|tools|file|edit)\s+menu\b', bullet_lower)
                feature_match = re.search(r'\b(about\s+app|[\w\s]+)\s+appears', bullet_lower)
                
                if feature_match:
                    feature = feature_match.group(1).strip()
                    if menu_match:
                        menu_name = menu_match.group(0)
                        return f"Availability of the {feature.title()} entry from the expected {menu_name} location and correct invocation behavior"
                    else:
                        return f"Availability of the {feature.title()} entry from the expected menu location and correct invocation behavior"
                else:
                    return "Availability of the feature entry from the expected menu location and correct invocation behavior"
        return None
    
    def _parse_acceptance_criteria(self, ac_text: str) -> List[str]:
        """Parse acceptance criteria into individual bullets."""
        if not ac_text:
            return []
        
        bullets = []
        
        # Split by common bullet markers
        lines = re.split(r'[\n\r]+', ac_text)
        for line in lines:
            line = line.strip()
            if not line:
                    continue
            
            # Remove bullet markers
            line = re.sub(r'^[-•*]\s*', '', line)
            line = re.sub(r'^\d+[.)]\s*', '', line)
            
            # Remove "Acceptance Criteria:" header
            if 'acceptance criteria' in line.lower() and ':' in line:
                continue
            
            # Skip if it's just "Acceptance Criteria" or similar header
            if line.lower().strip() in ['acceptance criteria', 'ac']:
                continue
            
            if line:
                bullets.append(line)
        
        return bullets
    
    def _group_related_bullets(self, bullets: List[str]) -> List[List[str]]:
        """Group fragment bullets (ending with ":") with their content bullets."""
        groups = []
        i = 0
        
        while i < len(bullets):
            bullet = bullets[i].strip()
            
            # Check if this is a fragment (ends with ":")
            if bullet.endswith(':'):
                # Start a new group
                group = [bullet]
                i += 1
                
                # Collect following bullets until we hit another fragment or end
                while i < len(bullets):
                    next_bullet = bullets[i].strip()
                    # Stop if we hit another fragment
                    if next_bullet.endswith(':'):
                        break
                    # Stop if bullet is too long (likely standalone)
                    if len(next_bullet.split()) > 15:
                        break
                    group.append(next_bullet)
                    i += 1
                
                groups.append(group)
            else:
                # Standalone bullet
                groups.append([bullet])
                i += 1
        
        return groups
    
    def _normalize_bullet_group(self, group: List[str], evidence_text: str) -> Optional[str]:
        """Normalize a group of related bullets into one complete, professional bullet (ChatGPT-style)."""
        if not group:
            return None
        
        # If single bullet, use single normalization
        if len(group) == 1:
            return self._normalize_single_bullet(group[0], evidence_text)
        
        # Merge fragment with content - create professional statement
        fragment = group[0].rstrip(':').strip()
        content_items = group[1:]
        
        # Remove quotes from all items
        fragment = re.sub(r'["\']', '', fragment)
        content_items = [re.sub(r'["\']', '', item).strip() for item in content_items]
        
        # Build professional statement matching ChatGPT style
        fragment_lower = fragment.lower()
        
        if 'displays' in fragment_lower or 'shows' in fragment_lower or 'includes' in fragment_lower:
            # "The window displays: X, Y, Z" -> "Accurate display of core application metadata, including X, Y, and Z"
            if 'window' in fragment_lower or 'dialog' in fragment_lower:
                if len(content_items) == 1:
                    return f"Accurate display of {content_items[0].lower()}"
                elif len(content_items) == 2:
                    return f"Accurate display of core application metadata, including {content_items[0].lower()} and {content_items[1].lower()}"
                else:
                    items_text = ', '.join([item.lower() for item in content_items[:-1]]) + f', and {content_items[-1].lower()}'
                    return f"Accurate display of core application metadata, including {items_text}"
            else:
                # Generic display statement
                if len(content_items) == 1:
                    return f"Accurate display of {content_items[0].lower()}"
                else:
                    items_text = ', '.join([item.lower() for item in content_items[:-1]]) + f', and {content_items[-1].lower()}'
                    return f"Accurate display of {items_text}"
        elif 'appears' in fragment_lower or 'available' in fragment_lower:
            # "About App appears under Help menu" -> "Availability of the About App entry from the expected menu location and correct invocation behavior"
            menu_match = re.search(r'\b(help|tools|file|edit)\s+menu\b', fragment_lower)
            if menu_match:
                menu_name = menu_match.group(0)
                feature_match = re.search(r'\b(about\s+app|[\w\s]+)\b', fragment_lower)
                feature = feature_match.group(1) if feature_match else "the feature"
                return f"Availability of the {feature.title()} entry from the expected {menu_name} location and correct invocation behavior"
            else:
                return f"Availability of the feature entry from the expected menu location and correct invocation behavior"
        elif 'opens' in fragment_lower or 'selecting' in fragment_lower:
            # "Selecting it opens an informational window" -> "Proper rendering of the informational window, including layout, visibility, and non-editable presentation"
            if 'window' in fragment_lower or 'dialog' in fragment_lower:
                return "Proper rendering of the informational window, including layout, visibility, and non-editable presentation"
            else:
                return "Proper rendering of the informational view, including layout and visibility"
        else:
            # Generic merge - create professional statement
            merged = ' '.join([fragment] + content_items)
            return self._normalize_single_bullet(merged, evidence_text)
    
    def _normalize_single_bullet(self, bullet: str, evidence_text: str) -> Optional[str]:
        """Normalize a single bullet into a professional, ChatGPT-style testable theme.
        
        Rules:
        - Remove quotes
        - Remove "Acceptance Criteria" words
        - Convert to professional, polished statement
        - Use ChatGPT-style language patterns
        """
        # Remove quotes
        bullet = re.sub(r'["\']', '', bullet)
        
        # Remove "Acceptance Criteria" references
        bullet = re.sub(r'\bacceptance criteria\b', '', bullet, flags=re.IGNORECASE)
        bullet = re.sub(r'\bAC\b', '', bullet, flags=re.IGNORECASE)
        
        # Remove trailing colons
        bullet = bullet.rstrip(':').strip()
        
        # Skip if too short
        if len(bullet) < 10:
            return None
        
        # Skip if it's just a header
        header_patterns = [
            r'^(the window|the dialog|the menu|it) (displays|shows|includes):?$',
            r'^acceptance criteria:?$'
        ]
        for pattern in header_patterns:
            if re.match(pattern, bullet, re.IGNORECASE):
                return None
        
        # Remove forbidden speculative words
        bullet_lower = bullet.lower()
        for forbidden in self.FORBIDDEN_SPECULATIVE:
            if forbidden in bullet_lower:
                bullet = re.sub(r'\b' + re.escape(forbidden) + r'\b', '', bullet, flags=re.IGNORECASE)
                bullet = bullet.strip()
        
        # Transform into ChatGPT-style professional statements
        bullet_lower = bullet.lower()
        
        # Pattern 1: "About App appears under Help menu" -> "Availability of the About App entry from the expected menu location and correct invocation behavior"
        if 'appears' in bullet_lower and ('menu' in bullet_lower or 'under' in bullet_lower):
            menu_match = re.search(r'\b(help|tools|file|edit)\s+menu\b', bullet_lower)
            feature_match = re.search(r'\b(about\s+app|[\w\s]+)\s+appears', bullet_lower)
            if feature_match:
                feature = feature_match.group(1).strip()
                if menu_match:
                    menu_name = menu_match.group(0)
                    return f"Availability of the {feature.title()} entry from the expected {menu_name} location and correct invocation behavior"
                else:
                    return f"Availability of the {feature.title()} entry from the expected menu location and correct invocation behavior"
        
        # Pattern 2: "Selecting it opens an informational window" -> "Proper rendering of the informational window, including layout, visibility, and non-editable presentation"
        if ('opens' in bullet_lower or 'selecting' in bullet_lower) and ('window' in bullet_lower or 'dialog' in bullet_lower):
            if 'informational' in bullet_lower:
                return "Proper rendering of the informational window, including layout, visibility, and non-editable presentation"
            else:
                return "Proper rendering of the window, including layout and visibility"
        
        # Pattern 3: "The window displays application name" -> "Accurate display of core application metadata, including application name"
        if 'displays' in bullet_lower or 'shows' in bullet_lower:
            if 'application name' in bullet_lower or 'version' in bullet_lower or 'copyright' in bullet_lower:
                return "Accurate display of core application metadata, including application name and full installed version string"
            elif 'name' in bullet_lower:
                return "Accurate display of application name"
            elif 'version' in bullet_lower:
                return "Accurate display of full installed version string"
            else:
                # Extract what's being displayed
                display_match = re.search(r'displays?\s+(.+)', bullet_lower)
                if display_match:
                    content = display_match.group(1).strip()
                    return f"Accurate display of {content}"
        
        # Pattern 4: "Support link (clickable; opens in default browser)" -> "Presence and functionality of the support link, ensuring it launches the correct destination in the default browser"
        if 'link' in bullet_lower and ('clickable' in bullet_lower or 'opens' in bullet_lower):
            if 'support' in bullet_lower:
                return "Presence and functionality of the support link, ensuring it launches the correct destination in the default browser"
            else:
                return "Presence and functionality of the link, ensuring it launches the correct destination"
        
        # Pattern 5: "The user can close the window easily" -> "Correct dismissal behavior of the window using provided close controls, without impacting the active drawing session"
        if 'close' in bullet_lower or 'dismiss' in bullet_lower:
            if 'window' in bullet_lower or 'dialog' in bullet_lower:
                return "Correct dismissal behavior of the window using provided close controls, without impacting the active drawing session"
            else:
                return "Correct dismissal behavior using provided close controls"
        
        # Pattern 6: "No additional fields, settings, or actions are required" -> "Absence of unintended inputs, settings, or actions beyond the defined informational scope"
        if 'no additional' in bullet_lower or 'no extra' in bullet_lower:
            return "Absence of unintended inputs, settings, or actions beyond the defined informational scope"
        
        # Pattern 7: Tool activation patterns
        if 'activate' in bullet_lower and ('tool' in bullet_lower or 'rotate' in bullet_lower or 'move' in bullet_lower):
            if 'select' in bullet_lower and ('shape' in bullet_lower or 'object' in bullet_lower):
                return "Correct activation behavior when objects are selected, ensuring the tool becomes active and ready for interaction"
            else:
                return "Correct activation behavior of the tool, ensuring it becomes active and ready for interaction"
        
        # Pattern 8: Rotation behavior
        if 'rotate' in bullet_lower:
            if 'marker' in bullet_lower or 'handle' in bullet_lower:
                return "Proper rotation behavior using the rotation marker, including smooth interaction and accurate angle changes"
            elif 'shift' in bullet_lower or 'constrain' in bullet_lower:
                return "Constrained rotation behavior when modifier keys are used, providing precise control and predictable increments"
            else:
                return "Proper rotation functionality, enabling users to rotate selected objects to desired orientations"
        
        # Pattern 9: Movement behavior
        if 'move' in bullet_lower and 'object' in bullet_lower:
            return "Accurate movement behavior, allowing precise positioning of selected objects within the workspace"
        
        # Pattern 10: Click and drag interaction
        if 'click' in bullet_lower and 'drag' in bullet_lower:
            return "Correct click-and-drag interaction behavior, providing responsive and predictable manipulation"
        
        # Pattern 11: Keyboard navigation
        if 'keyboard' in bullet_lower or ('key' in bullet_lower and ('shortcut' in bullet_lower or 'navigation' in bullet_lower)):
            return "Keyboard accessibility and navigation support, ensuring the tool can be activated and controlled via keyboard input"
        
        # Pattern 12: Undo/redo integration
        if 'undo' in bullet_lower or 'redo' in bullet_lower:
            return "Proper integration with undo/redo functionality, ensuring tool operations can be reversed and restored correctly"
        
        # Pattern 13: Selection behavior
        if 'select' in bullet_lower and ('object' in bullet_lower or 'shape' in bullet_lower):
            if 'deselect' in bullet_lower or 'deactivate' in bullet_lower:
                return "Correct selection and deselection behavior, maintaining proper tool state when objects are selected or deselected"
            else:
                return "Proper selection behavior, ensuring objects can be selected and the tool responds appropriately"
        
        # Pattern 14: Empty canvas/no selection edge case
        if 'empty' in bullet_lower and ('canvas' in bullet_lower or 'selection' in bullet_lower):
            return "Appropriate behavior when no objects are selected or the canvas is empty, preventing unintended tool activation"
        
        # Pattern 15: Tool switching
        if 'switch' in bullet_lower or ('change' in bullet_lower and 'tool' in bullet_lower):
            return "Correct tool switching behavior, ensuring proper deactivation of the previous tool when switching to another tool"
        
        # Pattern 16: Rotation angle display
        if 'rotation angle' in bullet_lower or ('angle' in bullet_lower and 'shown' in bullet_lower):
            return "Accurate display of the current rotation angle, providing clear visual feedback during rotation"
        
        # Pattern 17: Rotation range (0-360 degrees)
        if '0' in bullet_lower and ('360' in bullet_lower or 'degree' in bullet_lower):
            if 'turn' in bullet_lower or 'rotate' in bullet_lower:
                return "Full rotation capability, allowing objects to be rotated through the complete 0-360 degree range"
        
        # Pattern 18: Out of scope / phase notes
        if 'out of scope' in bullet_lower or 'phase' in bullet_lower and ('1' in bullet_lower or 'one' in bullet_lower):
            return None  # Skip out-of-scope items
        
        # Pattern 19: Compliance/standards notes (should be in accessibility clause, not bullets)
        if 'section 508' in bullet_lower or 'wcag' in bullet_lower or 'comply' in bullet_lower:
            return None  # Skip compliance notes (handled in accessibility clause)
        
        # Pattern 20: Generic "Correct behavior for X" -> transform to professional statement
        if bullet_lower.startswith('correct behavior for'):
            behavior = bullet_lower.replace('correct behavior for', '').strip()
            if behavior:
                return f"Correct behavior for {behavior}"
        
        # Skip fragments that start with lowercase verbs without proper context
        if bullet_lower.split()[0] in ['turn', 'show', 'must', 'out'] and len(bullet.split()) < 8:
            # Try to transform if it's a meaningful statement
            if 'turn' in bullet_lower and 'object' in bullet_lower:
                return "Proper rotation capability, enabling objects to be turned in any direction"
            elif 'show' in bullet_lower and 'angle' in bullet_lower:
                return "Accurate display of rotation angle information"
            else:
                return None  # Skip fragments
        
        # Default: Capitalize and ensure professional tone
        if bullet:
            bullet = bullet[0].upper() + bullet[1:] if len(bullet) > 1 else bullet.upper()
        
        # Ensure professional statement format
        if not bullet.lower().startswith(('availability', 'proper', 'accurate', 'presence', 'correct', 'absence')):
            # Add professional prefix based on content
            if 'behavior' in bullet_lower:
                bullet = f"Correct {bullet.lower()}"
            elif 'display' in bullet_lower or 'show' in bullet_lower:
                bullet = f"Accurate {bullet.lower()}"
            elif 'activate' in bullet_lower or 'interaction' in bullet_lower:
                bullet = f"Proper {bullet.lower()} behavior"
            else:
                bullet = f"Proper {bullet.lower()}"
        
        return bullet.strip()
    
    def _deduplicate_bullets(self, bullets: List[str]) -> List[str]:
        """Remove duplicate bullets."""
        seen = set()
        result = []
        for bullet in bullets:
            # Normalize for comparison
            bullet_normalized = re.sub(r'[^\w\s]', '', bullet.lower())
            bullet_normalized = ' '.join(bullet_normalized.split())
            
            if bullet_normalized not in seen:
                seen.add(bullet_normalized)
                result.append(bullet)
        return result
    
    def _derive_bullets_from_tests(self, test_titles: List[str], evidence_text: str) -> List[str]:
        """Derive additional bullets from test case titles if needed."""
        bullets = []
        
        for title in test_titles:
            # Extract meaningful parts
            if ' / ' in title:
                parts = title.split(' / ')
                if len(parts) >= 2:
                    scenario = parts[-1].strip()
                    if scenario and len(scenario) > 10:
                        # Skip fragment patterns before normalization
                        scenario_lower = scenario.lower()
                        if re.match(r'^(proper|correct)\s+(activate|"|about)', scenario_lower):
                            continue
                        if re.match(r'^"about\s+app"\s+appears', scenario_lower):
                            continue
                        # Normalize scenario into bullet
                        normalized = self._normalize_single_bullet(scenario, evidence_text)
                        if normalized:
                            # Double-check after normalization
                            normalized_lower = normalized.lower()
                            if re.match(r'^proper\s+(activate|"|about)', normalized_lower):
                                continue
                            if re.match(r'^"about\s+app"\s+appears', normalized_lower):
                                continue
                            if normalized_lower.startswith('proper ') and len(normalized.split()) < 8:
                                continue
                            bullets.append(normalized)
        
        return bullets[:3]  # Max 3 additional bullets
    
    def _extract_dependencies(self, evidence_text: str, test_titles: List[str]) -> List[str]:
        """Extract functional dependencies from evidence only (ChatGPT-style comprehensive).
        
        Only include if explicitly mentioned in evidence.
        """
        dependencies = []
        
        # Check for explicit mentions (word boundaries)
        if re.search(r'\bmenu\b', evidence_text):
            dependencies.append('application menu navigation')
        if re.search(r'\b(dialog|window|modal)\b', evidence_text):
            dependencies.append('modal dialog rendering')
        if re.search(r'\b(select|selected|selection)\b', evidence_text):
            dependencies.append('object selection')
        if re.search(r'\b(undo|redo)\b', evidence_text):
            dependencies.append('undo/redo system')
        if re.search(r'\blink\b', evidence_text) and re.search(r'\b(clickable|opens)\b', evidence_text):
            dependencies.append('external link handling')
        if re.search(r'\bfocus\b', evidence_text) or (re.search(r'\bmodal\b', evidence_text) and re.search(r'\bkeyboard\b', evidence_text)):
            dependencies.append('window focus management')
        
        return dependencies
    
    def _build_accessibility_clause(self, evidence_text: str, test_cases: List[TestCase]) -> str:
        """Build accessibility paragraph (ChatGPT-style comprehensive).
        
        Must not mention tools unless explicitly in story.
        """
        # Check if dialog/window is mentioned
        has_dialog = 'dialog' in evidence_text.lower() or 'window' in evidence_text.lower()
        
        if has_dialog:
            clause = (
                "Accessibility testing will validate compliance with Section 508 / WCAG 2.1 AA standards, "
                "including keyboard navigation, visible focus indicators, readable text, and meaningful labels "
                "and roles for all interactive elements within the dialog."
            )
        else:
            clause = (
                "Accessibility testing will validate compliance with Section 508 / WCAG 2.1 AA standards, "
                "including keyboard operability, visible focus indicators, and readable labels and control roles "
                "to ensure the feature is usable with assistive technologies."
            )
        
        return clause
    
    def _render_summary(self, plan: SummaryPlan) -> str:
        """Phase B: Render SummaryPlan into final text.
        
        Uses template matching required format exactly.
        """
        # Format bullets
        bullet_lines = '\n'.join(f"• {bullet}" for bullet in plan.bullet_themes)
        
        # Format dependencies (ChatGPT-style)
        if plan.dependencies:
            if len(plan.dependencies) == 1:
                deps_text = plan.dependencies[0]
            elif len(plan.dependencies) == 2:
                deps_text = f"{plan.dependencies[0]} and {plan.dependencies[1]}"
            else:
                deps_text = ', '.join(plan.dependencies[:-1]) + f', and {plan.dependencies[-1]}'
            dependencies_para = f"Functional dependencies include {deps_text}, all of which must operate correctly to ensure a stable and predictable user experience."
        else:
            dependencies_para = "Functional dependencies include core application components that must operate correctly to ensure a stable and predictable user experience."
        
        # Render full summary with header
        summary = (
            f"QA Planning Summary for this Work Item\n"
            f"{'=' * 80}\n\n"
            f"{plan.intro_facts}\n\n"
            f"Testing will focus on verifying:\n"
            f"{bullet_lines}\n\n"
            f"{dependencies_para}\n\n"
            f"{plan.accessibility_clause}\n\n"
            f"{plan.platform_clause}"
        )
        
        return summary
    
    def _lint_summary(self, summary: str, story: UserStory, test_cases: List[TestCase]) -> List[str]:
        """Lint summary against evidence and rules.
        
        Returns list of error messages (empty if valid).
        """
        errors = []
        summary_lower = summary.lower()
        evidence_text = f"{story.description} {story.acceptance_criteria}".lower()
        
        # Check for forbidden speculative language
        for term in self.FORBIDDEN_SPECULATIVE:
            if term in summary_lower:
                errors.append(f"Forbidden speculative term: '{term}'")
        
        # Check for "Acceptance Criteria" or "implements Description"
        if 'acceptance criteria' in summary_lower:
            errors.append("Contains 'Acceptance Criteria' phrase")
        if 'implements description' in summary_lower:
            errors.append("Contains 'implements Description' phrase")
        
        # Check for invented UI surfaces
        for surface in self.VALID_UI_SURFACES:
            surface_lower = surface.lower()
            if surface_lower in summary_lower:
                # Check if it's in evidence (word boundary match)
                pattern = r'\b' + re.escape(surface_lower) + r'\b'
                if not re.search(pattern, evidence_text):
                    # Check test titles
                    in_tests = any(re.search(pattern, tc.title.lower()) for tc in test_cases)
                    if not in_tests:
                        errors.append(f"Invented UI surface: '{surface}' not in evidence")
        
        # Check for bullet fragments (ending with ":")
        lines = summary.split('\n')
        for line in lines:
            line_stripped = line.strip()
            if line_stripped.startswith('•'):
                bullet_text = line_stripped[1:].strip()
                if bullet_text.endswith(':'):
                    errors.append(f"Bullet fragment ending with ':': {bullet_text[:50]}")
                if len(bullet_text.split()) < 4:
                    errors.append(f"Bullet too short (< 4 words): {bullet_text[:50]}")
        
        # Check for duplicate bullets
        bullet_lines = [line.strip() for line in lines if line.strip().startswith('•')]
        seen_bullets = set()
        for bullet_line in bullet_lines:
            bullet_normalized = re.sub(r'[^\w\s]', '', bullet_line.lower())
            bullet_normalized = ' '.join(bullet_normalized.split())
            if bullet_normalized in seen_bullets:
                errors.append(f"Duplicate bullet: {bullet_line[:50]}")
            seen_bullets.add(bullet_normalized)
        
        return errors
    
    def save_summary(self, summary: str, story_id: int, output_dir: str, feature_name_safe: Optional[str] = None) -> str:
        """Save QA Planning Summary to file.
        
        Args:
            summary: The generated summary text
            story_id: User story ID
            output_dir: Output directory path
            feature_name_safe: Optional sanitized feature name for filename
            
        Returns:
            Path to saved file
        """
        import os
        from pathlib import Path
        
        Path(output_dir).mkdir(exist_ok=True)
        if feature_name_safe:
            filename = f"{story_id}_{feature_name_safe}_qa_summary.txt"
        else:
            filename = f"{story_id}_qa_summary.txt"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            # Summary already includes header, so write as-is
            f.write(summary)
        
        return filepath

    def validate_summary(self, summary: str) -> Tuple[bool, List[str]]:
        """Validate summary structure and content.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check required sections
        if 'QA Planning Summary for this Work Item' not in summary:
            errors.append("Missing header")
        if 'Testing will focus on verifying:' not in summary:
            errors.append("Missing 'Testing will focus on verifying:' section")
        if 'Functional dependencies' not in summary:
            errors.append("Missing dependencies paragraph")
        if 'Accessibility testing' not in summary:
            errors.append("Missing accessibility paragraph")
        if 'Tests will be executed on Windows 11' not in summary:
            errors.append("Missing platform clause")
        
        # Check bullet count
        bullet_count = summary.count('•')
        if bullet_count < 7:
            errors.append(f"Too few bullets: {bullet_count} (minimum 7)")
        elif bullet_count > 10:
            errors.append(f"Too many bullets: {bullet_count} (maximum 10)")
        
        return len(errors) == 0, errors
