"""
Generic Test Generator - Project-agnostic test case generation.
Uses ProjectConfig to generate test cases for any application.
Integrates quality enhancement for high-quality, deterministic output.
Uses StoryTypeClassifier to avoid irrelevant edge cases.
Uses story description to generate context-rich, meaningful test scenarios.
"""
from typing import List, Dict, Optional, Any, Tuple
import re
from dataclasses import dataclass, field

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projects.project_config import ProjectConfig
from projects.test_suite_creator import QAPrepGenerator
from core.services.story_type_classifier import StoryType, StoryTypeClassifier


# =============================================================================
# DESCRIPTION PARSER - Extract structured info from story descriptions
# =============================================================================

@dataclass
class DescriptionContext:
    """Parsed context from story description."""
    menu_path: str = ""  # e.g., "Help → User Manual"
    user_flow: List[str] = field(default_factory=list)  # e.g., ["User selects Help → User Manual", "QuickDraw opens the built-in manual viewer"]
    key_features: List[str] = field(default_factory=list)  # e.g., ["offline access", "in-app viewer", "PDF manuals"]
    main_purpose: str = ""  # e.g., "provides users with direct access to official QuickDraw documentation"
    raw_description: str = ""


class DescriptionParser:
    """
    Parses story descriptions to extract structured context for test generation.

    Extracts:
    - Menu Path: Navigation path to the feature
    - User Flow: Step-by-step user actions
    - Key Features: Main capabilities/characteristics
    - Main Purpose: What the feature does
    """

    @classmethod
    def parse(cls, description: str) -> DescriptionContext:
        """Parse description and extract structured context."""
        if not description:
            return DescriptionContext()

        ctx = DescriptionContext(raw_description=description)
        desc_lower = description.lower()

        # Extract Menu Path
        ctx.menu_path = cls._extract_menu_path(description)

        # Extract User Flow
        ctx.user_flow = cls._extract_user_flow(description)

        # Extract Key Features
        ctx.key_features = cls._extract_key_features(description)

        # Extract Main Purpose
        ctx.main_purpose = cls._extract_main_purpose(description)

        return ctx

    @classmethod
    def _extract_menu_path(cls, description: str) -> str:
        """Extract menu navigation path from description."""
        # Pattern: "Menu Path:" or "Navigation:" followed by path
        patterns = [
            r'Menu\s*Path\s*:?\s*\n?\s*([^\n]+)',
            r'Navigation\s*:?\s*\n?\s*([^\n]+)',
            r'Access\s+(?:via|through)\s*:?\s*\n?\s*([^\n]+)',
            r'(?:Go\s+to|Navigate\s+to)\s+([A-Z][a-z]+(?:\s*[→>-]\s*[A-Z][a-z]+)+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                path = match.group(1).strip()
                # Clean up the path
                path = re.sub(r'\s*[→>-]+\s*', ' → ', path)
                return path

        return ""

    @classmethod
    def _extract_user_flow(cls, description: str) -> List[str]:
        """Extract user flow steps from description."""
        flow_steps = []

        # Look for "User Flow" section
        flow_match = re.search(r'User\s*Flow\s*:?\s*\n((?:[•\-\*]\s*[^\n]+\n?)+)', description, re.IGNORECASE)
        if flow_match:
            flow_text = flow_match.group(1)
            # Extract bullet points
            bullets = re.findall(r'[•\-\*]\s*([^\n]+)', flow_text)
            flow_steps.extend([b.strip() for b in bullets if b.strip()])

        # Also look for numbered steps
        numbered_match = re.search(r'(?:Steps?|Flow)\s*:?\s*\n((?:\d+\.\s*[^\n]+\n?)+)', description, re.IGNORECASE)
        if numbered_match:
            numbered_text = numbered_match.group(1)
            steps = re.findall(r'\d+\.\s*([^\n]+)', numbered_text)
            flow_steps.extend([s.strip() for s in steps if s.strip()])

        return flow_steps

    @classmethod
    def _extract_key_features(cls, description: str) -> List[str]:
        """Extract key features/characteristics from description."""
        features = []
        desc_lower = description.lower()

        # Common feature indicators
        feature_patterns = [
            r'(?:provides?|offers?|supports?|enables?|allows?)\s+([^\.]+)',
            r'(?:full|complete)\s+(\w+\s+access)',
            r'(?:in-app|built-in|native)\s+(\w+)',
            r'(\w+)\s+(?:is\s+)?(?:displayed|shown)\s+(?:in|within)\s+(?:the\s+)?app',
            r'(?:offline|online)\s+(\w+)',
            r'(?:PDF|document|manual)\s+(\w+)',
        ]

        for pattern in feature_patterns:
            matches = re.findall(pattern, desc_lower)
            features.extend([m.strip() for m in matches if m.strip() and len(m.strip()) > 3])

        # Look for explicit feature lists
        feature_list_match = re.search(r'(?:Features?|Capabilities?)\s*:?\s*\n((?:[•\-\*]\s*[^\n]+\n?)+)', description, re.IGNORECASE)
        if feature_list_match:
            feature_text = feature_list_match.group(1)
            bullets = re.findall(r'[•\-\*]\s*([^\n]+)', feature_text)
            features.extend([b.strip() for b in bullets if b.strip()])

        # Deduplicate and limit
        seen = set()
        unique_features = []
        for f in features:
            f_lower = f.lower()
            if f_lower not in seen and len(f) > 3:
                seen.add(f_lower)
                unique_features.append(f)

        return unique_features[:10]  # Limit to 10 features

    @classmethod
    def _extract_main_purpose(cls, description: str) -> str:
        """Extract the main purpose/what the feature does."""
        # First sentence often describes the purpose
        # Look for "Description" section or first paragraph

        # Remove headers
        text = re.sub(r'^Description\s*:?\s*\n?', '', description, flags=re.IGNORECASE)

        # Get first meaningful sentence
        sentences = re.split(r'(?<=[.!?])\s+', text)
        for sentence in sentences:
            sentence = sentence.strip()
            # Skip very short or header-like sentences
            if len(sentence) > 20 and not re.match(r'^[A-Z][a-z]+\s*:', sentence):
                # Clean up
                sentence = re.sub(r'\s+', ' ', sentence)
                return sentence

        return ""


def detect_redundant_acs(criteria: List[str]) -> List[Tuple[int, int, str]]:
    """
    Detect redundant/similar acceptance criteria.

    Returns list of tuples: (ac_index1, ac_index2, reason)
    """
    redundant = []

    # Normalize ACs for comparison
    normalized = []
    for ac in criteria:
        norm = ac.lower().strip()
        # Remove common variations
        norm = re.sub(r'[\"\']', '', norm)
        norm = re.sub(r'\s+', ' ', norm)
        normalized.append(norm)

    # Check for similar ACs
    for i, ac1 in enumerate(normalized):
        for j, ac2 in enumerate(normalized):
            if i >= j:
                continue

            # Check for high similarity
            if cls_similar(ac1, ac2):
                reason = "Similar content"
                redundant.append((i, j, reason))

    return redundant


def cls_similar(text1: str, text2: str, threshold: float = 0.8) -> bool:
    """Check if two texts are similar using word overlap."""
    words1 = set(text1.split())
    words2 = set(text2.split())

    if not words1 or not words2:
        return False

    intersection = words1 & words2
    union = words1 | words2

    similarity = len(intersection) / len(union)
    return similarity >= threshold

# Import quality enhancement services
try:
    from core.services.quality import (
        get_quality_analyzer,
        get_semantic_step_builder,
        LLMTestCorrector,
        BatchTestCorrector,
    )
    QUALITY_SERVICES_AVAILABLE = True
except ImportError:
    QUALITY_SERVICES_AVAILABLE = False
    get_quality_analyzer = None
    get_semantic_step_builder = None


class GenericTestGenerator:
    """
    Generates test cases using project configuration.
    Replaces hardcoded ENV QuickDraw references with configurable templates.
    Integrates quality enhancement for high-quality output.
    """

    def __init__(
        self,
        config: ProjectConfig,
        llm_provider: Optional[Any] = None,
        enable_quality_enhancement: bool = True,
        quality_threshold: float = 0.6
    ):
        """
        Initialize generator with project configuration.

        Args:
            config: ProjectConfig for the target application.
            llm_provider: Optional LLM provider for quality correction.
            enable_quality_enhancement: Enable NLP-based step enhancement.
            quality_threshold: Minimum quality score (0-1) to skip LLM correction.
        """
        self.config = config
        self.app = config.application
        self.rules = config.rules
        self.test_id_counter = config.rules.test_id_increment

        # Quality enhancement
        self.enable_quality_enhancement = enable_quality_enhancement and QUALITY_SERVICES_AVAILABLE
        self.quality_threshold = quality_threshold
        self.llm_provider = llm_provider

        # Initialize quality services
        self._quality_analyzer = None
        self._step_builder = None
        self._test_corrector = None

        # Description context (set during test generation)
        self.description_context: Optional[DescriptionContext] = None
        self.story_type: StoryType = StoryType.UNKNOWN

        if self.enable_quality_enhancement:
            self._quality_analyzer = get_quality_analyzer()
            self._step_builder = get_semantic_step_builder()

    def generate_test_cases(
        self,
        story_data: Dict,
        criteria: List[str],
        qa_prep_content: Optional[str] = None
    ) -> List[Dict]:
        """
        Generate comprehensive test cases for a story.

        Uses BOTH story description AND acceptance criteria to generate
        context-rich, meaningful test scenarios.

        Args:
            story_data: Story information (story_id, title, description).
            criteria: List of acceptance criteria bullets.
            qa_prep_content: Optional QA Prep task content.

        Returns:
            List of test case dictionaries.
        """
        test_cases = []
        story_id = story_data['story_id']
        feature_name = self._extract_feature_name(story_data['title'])

        # Parse story DESCRIPTION to extract context
        description = story_data.get('description', '')
        self.description_context = DescriptionParser.parse(description)
        if self.description_context.menu_path:
            print(f"  Menu path from description: {self.description_context.menu_path}")
        if self.description_context.key_features:
            print(f"  Key features: {', '.join(self.description_context.key_features[:3])}")

        # Classify story type to avoid irrelevant edge cases
        self.story_type = StoryTypeClassifier.classify(
            story_data.get('title', ''),
            criteria,
            qa_prep_content or ""
        )
        print(f"  Story type classified as: {self.story_type.value}")

        # Parse QA Prep or generate equivalent
        qa_details = self._parse_qa_prep(qa_prep_content) if qa_prep_content else {}

        # If no QA Prep and no details, generate them
        if not qa_details:
            qa_generator = QAPrepGenerator(self.config)
            qa_details = qa_generator.generate_qa_prep_content(story_data, criteria)

        # Override entry point for Help/Documentation stories
        if self.story_type == StoryType.HELP_DOCUMENTATION:
            qa_details['entry_points'] = ['Help Menu']

        # Detect Properties Panel entry point from description/ACs
        # This is important for stories where features are accessed via Properties Panel
        combined_text = (description + ' ' + ' '.join(criteria)).lower()
        properties_panel_detected = False
        if 'properties panel' in combined_text or 'properties' in combined_text and 'panel' in combined_text:
            # Check if description/ACs explicitly mention Properties panel as control point
            properties_patterns = [
                r'(?:controlled?|access(?:ed|ible)?|available|configur(?:ed?|able)|manag(?:ed?|able)|set|adjust(?:ed|able)?)\s+(?:via|through|from|in|using)\s+(?:the\s+)?properties\s*panel',
                r'properties\s*panel\s+(?:controls?|provides?|allows?|contains?|displays?|shows?)',
            ]
            for pattern in properties_patterns:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    qa_details['entry_points'] = ['Properties Panel']
                    properties_panel_detected = True
                    print(f"  Entry point set to Properties Panel (detected from description/AC)")
                    break
            else:
                # Fallback: If story type is PROPERTIES, use Properties Panel
                if self.story_type == StoryType.PROPERTIES:
                    qa_details['entry_points'] = ['Properties Panel']
                    properties_panel_detected = True
                    print(f"  Entry point set to Properties Panel (PROPERTIES story type)")

        # Use menu path from description if available (but NOT if Properties Panel was explicitly detected)
        if self.description_context.menu_path and not properties_panel_detected:
            # Extract the menu name from path (e.g., "Help → User Manual" -> "Help Menu")
            menu_parts = self.description_context.menu_path.split('→')
            if menu_parts:
                menu_name = menu_parts[0].strip() + " Menu"
                if menu_name not in qa_details.get('entry_points', []):
                    qa_details['entry_points'] = [menu_name] + qa_details.get('entry_points', [])

        # Detect edge cases and negative scenarios from description/ACs
        # This ensures edge cases are generated even without QA prep
        if 'negative_scenarios' not in qa_details:
            qa_details['negative_scenarios'] = []
        if 'edge_cases' not in qa_details:
            qa_details['edge_cases'] = []

        # Detect no_selection edge case from ACs
        no_selection_patterns = [
            r'enabled\s+only\s+when.*(?:object|item|element).*selected',
            r'disabled\s+when\s+no.*selected',
            r'requires?\s+(?:a|an|at least one)\s+(?:object|selection)',
            r'only\s+(?:available|enabled|active)\s+(?:when|if).*selected',
            r'at\s+least\s+one\s+object\s+(?:is\s+)?selected',
        ]
        for pattern in no_selection_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                if 'no_selection' not in qa_details['negative_scenarios']:
                    qa_details['negative_scenarios'].append('no_selection')
                break

        # Detect undo/redo edge case from ACs
        if re.search(r'\bundo\b.*\bredo\b|\bredo\b.*\bundo\b|\bundo/redo\b', combined_text, re.IGNORECASE):
            if 'undo_redo' not in qa_details.get('edge_cases', []):
                qa_details.setdefault('undo_redo_actions', []).append('transformation')

        # Detect and track redundant ACs to avoid duplicate tests
        self._redundant_acs = self._detect_redundant_criteria(criteria)
        if self._redundant_acs:
            print(f"  Detected {len(self._redundant_acs)} similar AC pairs (will consolidate)")

        # Generate test cases from AC
        skipped_redundant = set()
        for idx, ac_bullet in enumerate(criteria):
            # Skip cancelled AC
            if self._is_cancelled(ac_bullet):
                print(f"  Skipping cancelled AC{idx + 1}: {ac_bullet[:50]}...")
                continue

            # Skip if this AC was marked as redundant with an earlier one
            if idx in skipped_redundant:
                print(f"  Skipping AC{idx + 1}: Merged with earlier similar AC")
                continue

            # Check if this AC has redundant siblings - mark them for skipping
            for (ac1_idx, ac2_idx, reason) in self._redundant_acs:
                if ac1_idx == idx:
                    skipped_redundant.add(ac2_idx)
                    print(f"  AC{ac2_idx + 1} will be consolidated with AC{idx + 1}")

            # Check feature feasibility (skip if feature doesn't exist in app)
            feasibility = self.app.check_ac_feasibility(ac_bullet)
            if not feasibility['feasible']:
                for reason in feasibility['blocked_reasons']:
                    print(f"  SKIPPING AC{idx + 1}: {reason}")
                continue
            if feasibility['warnings']:
                for warning in feasibility['warnings']:
                    print(f"  NOTE AC{idx + 1}: {warning}")

            # Generate test ID
            if idx == 0:
                test_id = f"{story_id}-{self.rules.first_test_id}"
            else:
                test_id = f"{story_id}-{self.test_id_counter:03d}"
                self.test_id_counter += self.rules.test_id_increment

            # Generate test case
            test_case = self._generate_test_for_ac(
                test_id, ac_bullet, idx + 1, feature_name, story_data, qa_details
            )
            if test_case:
                test_cases.append(test_case)

        # Generate edge case tests
        edge_cases = self._extract_edge_cases(qa_details, feature_name)
        for edge_case in edge_cases:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += self.rules.test_id_increment

            test_case = self._generate_edge_case_test(test_id, edge_case, feature_name, story_data)
            if test_case:
                test_cases.append(test_case)

        # Generate platform-specific tests
        if qa_details.get('platforms'):
            platform_tests = self._generate_platform_tests(
                story_id, feature_name, story_data, qa_details
            )
            test_cases.extend(platform_tests)

        # Generate accessibility tests
        accessibility_tests = self._generate_accessibility_tests(
            story_id, feature_name, story_data, qa_details
        )
        test_cases.extend(accessibility_tests)

        print(f"  Generated {len(test_cases)} test cases from {len(criteria)} AC bullets")

        # Apply quality enhancement if enabled
        if self.enable_quality_enhancement and self._quality_analyzer:
            test_cases = self._enhance_test_quality(test_cases, feature_name)

        return test_cases

    def _enhance_test_quality(
        self,
        test_cases: List[Dict],
        feature_context: str
    ) -> List[Dict]:
        """
        Enhance test case quality using analyzer and optional LLM correction.

        Args:
            test_cases: Generated test cases
            feature_context: Feature name for context

        Returns:
            Quality-enhanced test cases
        """
        if not self._quality_analyzer:
            return test_cases

        enhanced_cases = []
        low_quality_count = 0

        for test_case in test_cases:
            # Analyze quality
            metrics = self._quality_analyzer.analyze_test_case(test_case)

            if metrics.overall_score >= self.quality_threshold:
                # Quality is acceptable
                enhanced_cases.append(test_case)
            else:
                low_quality_count += 1

                # Try LLM correction if provider available
                if self.llm_provider and self._test_corrector is None:
                    from core.services.cache import get_cache_manager
                    try:
                        cache = get_cache_manager()
                    except Exception:
                        cache = None
                    self._test_corrector = LLMTestCorrector(
                        self.llm_provider,
                        cache_manager=cache,
                        quality_threshold=self.quality_threshold
                    )

                if self._test_corrector:
                    result = self._test_corrector.correct_test_case(
                        test_case, metrics, feature_context
                    )
                    enhanced_cases.append(result.corrected_test)
                else:
                    # Apply rule-based enhancement
                    enhanced = self._apply_rule_based_enhancement(test_case, metrics)
                    enhanced_cases.append(enhanced)

        if low_quality_count > 0:
            print(f"  Enhanced {low_quality_count} low-quality test cases")

        return enhanced_cases

    def _apply_rule_based_enhancement(
        self,
        test_case: Dict,
        metrics: Any
    ) -> Dict:
        """
        Apply rule-based enhancement for low-quality tests without LLM.

        Args:
            test_case: Test case to enhance
            metrics: Quality metrics

        Returns:
            Enhanced test case
        """
        enhanced = test_case.copy()
        enhanced['steps'] = []

        for idx, (step, step_metric) in enumerate(
            zip(test_case.get('steps', []), metrics.step_metrics)
        ):
            action = step.get('action', '')
            expected = step.get('expected', '')

            # Use semantic step builder to enhance generic steps
            if step_metric.has_generic_phrases and self._step_builder:
                feature_name = self._extract_feature_from_title(test_case.get('title', ''))
                enhanced_step = self._step_builder.enhance_generic_step(
                    action=action,
                    expected=expected,
                    feature_name=feature_name,
                    ac_text=action
                )
                enhanced['steps'].append(enhanced_step)
            else:
                enhanced['steps'].append({'action': action, 'expected': expected})

        return enhanced

    def _extract_feature_from_title(self, title: str) -> str:
        """Extract feature name from test case title."""
        # Title format: "ID: Feature / Location / Description"
        parts = title.split('/')
        if len(parts) >= 2:
            # Get the first part after ID
            feature_part = parts[0].split(':')
            if len(feature_part) >= 2:
                return feature_part[1].strip()
        return "Feature"

    # Step Template Methods

    def _get_prereq_step(self) -> Dict[str, str]:
        """Get the prerequisite step using project config."""
        return {"action": self.app.get_prereq_step(), "expected": ""}

    def _get_launch_step(self) -> Dict[str, str]:
        """Get the application launch step using project config."""
        return {"action": self.app.get_launch_step(), "expected": self.app.launch_expected}

    def _get_close_step(self) -> Dict[str, str]:
        """Get the application close step using project config."""
        return {"action": self.app.get_close_step(), "expected": ""}

    def _get_create_file_step(self) -> Dict[str, str]:
        """Get the create file/drawing step using project config.

        IMPORTANT: Most menus require a file/drawing to be open first.
        """
        return {
            "action": self.app.get_create_file_step(),
            "expected": self.app.get_create_file_expected()
        }

    def _get_standard_setup_steps(self, include_create_file: bool = True) -> List[Dict[str, str]]:
        """Get standard setup steps (prereq + launch + optional create file).

        Args:
            include_create_file: If True, includes create file step (required for most menu access).
        """
        steps = [self._get_prereq_step(), self._get_launch_step()]
        if include_create_file:
            steps.append(self._get_create_file_step())
        return steps

    def _get_object_setup_steps(self) -> List[Dict[str, str]]:
        """Get object interaction setup steps (after file is created).

        These steps should be added AFTER the standard setup steps which
        already include file creation.
        """
        return [
            {"action": "Draw an object/shape on the canvas (e.g., circle, rectangle, or any measurable shape).",
             "expected": "Object is created and displayed on the canvas."},
            {"action": "Select the created object.",
             "expected": "Object is selected and selection handles are visible."}
        ]

    # Test Generation Methods

    def _generate_test_for_ac(
        self,
        test_id: str,
        ac_bullet: str,
        ac_index: int,
        feature_name: str,
        story_data: Dict,
        qa_details: Dict
    ) -> Optional[Dict]:
        """Generate test case for an acceptance criterion."""
        ac_lower = ac_bullet.lower()

        # AC1 is always availability test
        if test_id.endswith(self.rules.first_test_id):
            return self._generate_availability_test(
                test_id, ac_bullet, feature_name, story_data, qa_details
            )

        # Undo/Redo test
        if 'undo' in ac_lower or 'redo' in ac_lower:
            return self._generate_undo_redo_test(
                test_id, ac_bullet, feature_name, story_data, qa_details
            )

        # Accessibility test - will be generated separately
        if 'accessibility' in ac_lower or 'wcag' in ac_lower or '508' in ac_lower:
            return None

        # Generic test for other AC
        return self._generate_generic_test(
            test_id, ac_bullet, feature_name, story_data, qa_details
        )

    def _generate_availability_test(
        self,
        test_id: str,
        ac_bullet: str,
        feature_name: str,
        story_data: Dict,
        qa_details: Dict
    ) -> Dict:
        """Generate availability/access test for AC1."""
        entry_points = qa_details.get('entry_points', [])

        # For Help/Documentation stories, always use Help Menu
        story_type = getattr(self, 'story_type', StoryType.UNKNOWN)
        if story_type == StoryType.HELP_DOCUMENTATION:
            entry_point = "Help Menu"
        elif story_type == StoryType.PROPERTIES or 'Properties Panel' in entry_points:
            entry_point = "Properties Panel"
        else:
            entry_point = self.app.determine_entry_point(feature_name, entry_points)

        # Generate humanistic title based on feature
        scenario = self._generate_ac1_title(feature_name, entry_point, ac_bullet)
        title = f"{test_id}: {feature_name} / {entry_point} / {scenario}"

        # Help/Documentation features don't need create file step
        if story_type == StoryType.HELP_DOCUMENTATION:
            steps = self._get_standard_setup_steps(include_create_file=False)
        else:
            steps = self._get_standard_setup_steps()

            # Properties Panel features require object selection first
            if entry_point == "Properties Panel" or story_type == StoryType.PROPERTIES:
                steps.extend(self._get_object_setup_steps())

        # Generate steps based on entry point type
        if entry_point == "Properties Panel":
            steps.extend([
                {"action": f"Navigate to the {entry_point} on the right side of the screen.",
                 "expected": f"{entry_point} is displayed showing label options for the selected object."},
                {"action": f"Verify that label controls are visible and accessible in the {entry_point}.",
                 "expected": "Label visibility and repositioning controls are available."},
            ])
            objective = f"Verify that <b>{feature_name}</b> controls are accessible from <b>{entry_point}</b> after selecting an object"
        else:
            steps.extend([
                {"action": f"Open the {entry_point}.", "expected": f"{entry_point} opens displaying available commands."},
                {"action": f"Locate the {feature_name} command in the menu.",
                 "expected": f"{feature_name} command is visible and enabled."},
            ])
            objective = f"Verify that <b>{feature_name}</b> command is accessible from <b>{entry_point}</b>"

        steps.append(self._get_close_step())

        return {'id': test_id, 'title': title, 'steps': steps, 'objective': objective}

    def _generate_ac1_title(self, feature_name: str, entry_point: str, ac_bullet: str) -> str:
        """Generate a humanistic title for AC1 availability test.

        Uses description context for Help/Documentation features.
        Uses LLM if available, otherwise falls back to intelligent rule-based generation.
        """
        story_type = getattr(self, 'story_type', StoryType.UNKNOWN)
        desc_ctx = getattr(self, 'description_context', None)

        # For Help/Documentation features, use description-aware titles
        if story_type == StoryType.HELP_DOCUMENTATION:
            if desc_ctx and desc_ctx.menu_path:
                # Use the menu path to create a meaningful title
                # e.g., "Help → User Manual" -> "Help: User Manual menu access"
                return f"{feature_name} menu access"
            return f"{feature_name} menu access"

        # Try LLM-based title generation if corrector is available
        if self._test_corrector:
            try:
                llm_title = self._test_corrector.generate_title(
                    feature_name=feature_name,
                    ac_text=ac_bullet,
                    test_focus="menu availability and access"
                )
                if llm_title:
                    return llm_title
            except Exception:
                pass  # Fall back to rule-based

        # Intelligent rule-based title generation
        feature_lower = feature_name.lower()

        # Extract key action words from feature name
        if 'rotate' in feature_lower and 'mirror' in feature_lower:
            return "Rotate and Mirror commands in menu"
        elif 'rotate' in feature_lower:
            return "Rotate command menu access"
        elif 'mirror' in feature_lower:
            return "Mirror command menu access"
        elif 'transform' in feature_lower:
            return "Transformation tools menu access"
        elif 'dimension' in feature_lower:
            return "Dimension tools menu access"
        elif 'import' in feature_lower or 'export' in feature_lower:
            return "File import/export menu access"
        elif 'property' in feature_lower or 'properties' in feature_lower:
            return "Properties panel access"

        # Generic but still better than "Feature availability"
        short_name = feature_name.split('(')[0].strip()  # Remove parenthetical
        if len(short_name) > 30:
            short_name = short_name[:27] + "..."
        return f"{short_name} menu access"

    def _generate_undo_redo_test(
        self,
        test_id: str,
        ac_bullet: str,
        feature_name: str,
        story_data: Dict,
        qa_details: Dict
    ) -> Dict:
        """Generate undo/redo test."""
        entry_point = self.app.determine_entry_point(feature_name, qa_details.get('entry_points', []))
        title = f"{test_id}: {feature_name} / {entry_point} / Undo and redo actions"

        steps = self._get_standard_setup_steps()
        steps.append({"action": "Create a new document/drawing.", "expected": ""})

        # Add object setup if needed
        if self.app.requires_object_interaction(ac_bullet) or self.app.requires_object_interaction(feature_name):
            steps.extend([
                {"action": "Create an object in the workspace.", "expected": ""},
                {"action": "Select the created object.", "expected": ""},
            ])

        steps.extend([
            {"action": f"Perform the {feature_name} action.", "expected": ""},
            {"action": f"Verify the {feature_name} action is applied.",
             "expected": f"{feature_name} action is completed successfully."},
            {"action": "Trigger Undo (Ctrl+Z or Cmd+Z).", "expected": ""},
            {"action": f"Verify the {feature_name} action is reversed.",
             "expected": f"{feature_name} action is undone."},
            {"action": "Trigger Redo (Ctrl+Y or Cmd+Shift+Z).", "expected": ""},
            {"action": f"Verify the {feature_name} action is restored.",
             "expected": f"{feature_name} action is restored after Redo."},
        ])
        steps.append(self._get_close_step())

        objective = f"Verify that <b>Undo</b> and <b>Redo</b> correctly reverse and restore <b>{feature_name}</b> actions"

        return {'id': test_id, 'title': title, 'steps': steps, 'objective': objective}

    def _generate_generic_test(
        self,
        test_id: str,
        ac_bullet: str,
        feature_name: str,
        story_data: Dict,
        qa_details: Dict
    ) -> Dict:
        """Generate a SPECIFIC test based on AC content - never generic."""
        story_type = getattr(self, 'story_type', StoryType.UNKNOWN)
        entry_points = qa_details.get('entry_points', [])

        # Determine entry point based on story type
        if story_type == StoryType.HELP_DOCUMENTATION:
            entry_point = "Help Menu"
        elif story_type == StoryType.PROPERTIES or 'Properties Panel' in entry_points:
            entry_point = "Properties Panel"
        else:
            entry_point = self.app.determine_entry_point(feature_name, entry_points)

        scenario = self._extract_scenario_from_ac(ac_bullet, feature_name)
        title = f"{test_id}: {feature_name} / {entry_point} / {scenario}"

        # Help/Documentation features don't need create file step
        if story_type == StoryType.HELP_DOCUMENTATION:
            steps = self._get_standard_setup_steps(include_create_file=False)
        else:
            steps = self._get_standard_setup_steps()

            # Add object setup if:
            # 1. AC requires object interaction, OR
            # 2. Story type is PROPERTIES (properties are applied to selected objects), OR
            # 3. Entry point is Properties Panel (requires object to be selected)
            needs_object_setup = (
                self.app.requires_object_interaction(ac_bullet) or
                story_type == StoryType.PROPERTIES or
                entry_point == "Properties Panel"
            )
            if needs_object_setup:
                steps.extend(self._get_object_setup_steps())

        # Generate SPECIFIC steps based on AC analysis
        ac_lower = ac_bullet.lower()
        ac_steps = self._derive_specific_steps_from_ac(ac_bullet, feature_name, entry_point)

        steps.extend(ac_steps)
        steps.append(self._get_close_step())

        # Generate specific objective from AC - context-aware
        if story_type == StoryType.HELP_DOCUMENTATION:
            # Use AC-specific objective for Help features
            objective = self._generate_help_objective(ac_bullet, feature_name)
        else:
            objective = f"Verify that {self._humanize_objective(ac_bullet, feature_name)}"

        return {'id': test_id, 'title': title, 'steps': steps, 'objective': objective}

    def _derive_specific_steps_from_ac(
        self,
        ac_bullet: str,
        feature_name: str,
        entry_point: str
    ) -> List[Dict[str, str]]:
        """Derive SPECIFIC test steps from AC text - never generic.

        Context-aware based on story type to generate appropriate steps
        for different feature types (Help/Documentation, Tool, Dialog, etc.)
        """
        steps = []
        ac_lower = ac_bullet.lower()
        story_type = getattr(self, 'story_type', StoryType.UNKNOWN)

        # Handle Help/Documentation features with context-appropriate steps
        if story_type == StoryType.HELP_DOCUMENTATION:
            return self._derive_help_documentation_steps(ac_bullet, feature_name, entry_point)

        # Handle Properties Panel features - these require object selection first
        if entry_point == "Properties Panel" or story_type == StoryType.PROPERTIES:
            return self._derive_properties_panel_steps(ac_bullet, feature_name, entry_point)

        # Pattern-based step generation for specific AC types

        # 1. Dialog/menu opening ACs
        if 'opens' in ac_lower or 'open' in ac_lower:
            menu_match = re.search(r'(file|edit|view|tools?|insert|help)\s*(?:→|->|menu)?', ac_lower)
            if menu_match:
                menu = menu_match.group(1).capitalize()
                steps.append({"action": f"Open the {menu} Menu.", "expected": f"{menu} Menu opens displaying available commands."})

            action_match = re.search(r'(?:select|click|choose)\s+["\']?(\w+)["\']?', ac_lower)
            if action_match:
                action = action_match.group(1).capitalize()
                steps.append({"action": f"Select '{action}'.", "expected": f"The {feature_name} dialog opens."})
            else:
                steps.append({"action": f"Select the {feature_name} command.", "expected": f"The {feature_name} dialog opens."})

        # 2. Default value ACs
        elif 'default' in ac_lower:
            steps.append({"action": f"Open the {entry_point}.", "expected": f"{entry_point} opens."})
            default_match = re.search(r'default(?:\s+preset)?\s*=\s*["\']?([^"\'\.]+)', ac_bullet, re.IGNORECASE)
            if default_match:
                default_val = default_match.group(1).strip()
                steps.append({"action": f"Verify the default preset value.", "expected": f"Preset shows '{default_val}'."})
            else:
                steps.append({"action": "Verify the default preset values are displayed.", "expected": "Default values are shown correctly."})

        # 3. Field/control availability ACs
        elif 'field' in ac_lower or 'available' in ac_lower or 'include' in ac_lower:
            steps.append({"action": f"Open the {entry_point}.", "expected": f"{entry_point} opens."})
            # Extract field names if listed
            field_match = re.search(r'fields?\s*(?:available|include)?:?\s*([^\.]+)', ac_bullet, re.IGNORECASE)
            if field_match:
                fields_str = field_match.group(1)
                fields = [f.strip() for f in re.split(r'[,;]', fields_str) if f.strip() and len(f.strip()) > 1]
                for field in fields[:5]:  # Limit to 5 fields
                    clean_field = re.sub(r'\([^)]+\)', '', field).strip()
                    if clean_field:
                        steps.append({"action": f"Verify {clean_field} is displayed.", "expected": f"{clean_field} field/control is visible."})
            else:
                steps.append({"action": f"Verify all required controls are displayed.", "expected": "All controls are visible and functional."})

        # 4. Setting dependency ACs
        elif 'follow' in ac_lower and 'setting' in ac_lower:
            # Extract what setting
            setting_match = re.search(r'follow(?:s)?\s+(?:the\s+)?(?:current\s+)?(\w+(?:\s+\w+)?)\s+setting', ac_lower)
            setting_name = setting_match.group(1) if setting_match else "Unit of Measure"
            steps.append({"action": f"Open Settings.", "expected": "Settings panel/dialog opens."})
            steps.append({"action": f"Note the current {setting_name} setting.", "expected": ""})
            steps.append({"action": f"Open the {entry_point}.", "expected": f"{entry_point} opens."})
            steps.append({"action": f"Verify the dropdown reflects the current {setting_name} setting.", "expected": f"Dropdown value matches the {setting_name} setting."})

        # 5. Recent items ACs
        elif 'recent' in ac_lower:
            steps.append({"action": f"Open the {entry_point}.", "expected": f"{entry_point} opens."})
            steps.append({"action": "Locate the Recent Items section.", "expected": "Recent Items section is displayed."})
            steps.append({"action": "Verify Recent Items shows previously used presets.", "expected": "Most recently used canvas presets are listed."})

        # 6. Create/action button ACs
        elif 'create' in ac_lower or 'initialize' in ac_lower:
            steps.append({"action": f"Open the {entry_point}.", "expected": f"{entry_point} opens."})
            steps.append({"action": "Set desired size and unit values.", "expected": ""})
            steps.append({"action": "Click 'Create' button.", "expected": "A new blank canvas is created with the selected settings."})
            steps.append({"action": "Verify the canvas reflects the chosen dimensions.", "expected": "Canvas matches the specified size and units."})

        # 7. Close/cancel button ACs
        elif 'close' in ac_lower or 'cancel' in ac_lower or 'exit' in ac_lower:
            steps.append({"action": "Open an existing document.", "expected": "Document is displayed."})
            steps.append({"action": f"Open the {entry_point}.", "expected": f"{entry_point} opens."})
            steps.append({"action": "Modify some values in the dialog.", "expected": ""})
            steps.append({"action": "Click 'Close' button.", "expected": "Dialog closes without creating a new document."})
            steps.append({"action": "Verify the previous document is still displayed.", "expected": "User returns to the previously open document."})

        # 8. Accessibility/WCAG ACs (handled separately, skip here)
        elif 'accessibility' in ac_lower or 'wcag' in ac_lower or '508' in ac_lower:
            pass  # Will be generated by accessibility test generator

        # 9. Fallback: Extract specific action from AC text
        else:
            steps.append({"action": f"Navigate to {entry_point}.", "expected": f"{entry_point} is accessible."})

            # Extract the main action verb and object
            action = self._extract_main_action(ac_bullet, feature_name)
            expected = self._extract_verification(ac_bullet, feature_name)
            expected_formatted = self._format_expected_result(expected)

            steps.append({"action": action, "expected": ""})
            steps.append({"action": f"Verify: {expected}", "expected": expected_formatted})

        return steps

    def _derive_help_documentation_steps(
        self,
        ac_bullet: str,
        feature_name: str,
        entry_point: str
    ) -> List[Dict[str, str]]:
        """Derive steps for Help/Documentation features.

        These features don't involve object manipulation, so we focus on:
        - Menu navigation to Help
        - Opening the viewer/manual
        - Content display verification
        - Offline access verification
        - No external browser verification
        """
        steps = []
        ac_lower = ac_bullet.lower()

        # Step 1: Open Help Menu
        steps.append({
            "action": f"Open the {entry_point}.",
            "expected": f"{entry_point} opens displaying available commands."
        })

        # Step 2: Select User Manual
        steps.append({
            "action": f"Select the {feature_name} command.",
            "expected": "The in-app viewer opens displaying the manual content."
        })

        # Step 3: Context-specific verification based on AC content
        if 'appear' in ac_lower and 'menu' in ac_lower:
            # AC: "User Manual" appears under the Help menu
            steps.clear()  # Reset steps
            steps.append({
                "action": f"Open the {entry_point}.",
                "expected": f"{entry_point} opens."
            })
            steps.append({
                "action": f"Verify \"{feature_name}\" appears in the menu.",
                "expected": f"\"{feature_name}\" is visible in the {entry_point}."
            })

        elif 'viewer' in ac_lower and 'open' in ac_lower:
            # AC: Selecting it opens an in-app viewer
            steps.append({
                "action": "Verify the manual content is displayed in the in-app viewer.",
                "expected": "PDF manual content is displayed correctly."
            })

        elif 'offline' in ac_lower or 'internet' in ac_lower:
            # AC: Viewer displays content without requiring internet
            steps.append({
                "action": "Disconnect from the internet (disable WiFi/network).",
                "expected": ""
            })
            steps.append({
                "action": "Verify the manual content is still displayed without errors.",
                "expected": "Content remains accessible without internet connection."
            })

        elif 'remain' in ac_lower and ('open' in ac_lower or 'behind' in ac_lower):
            # AC: QuickDraw remains open behind the viewer
            steps.append({
                "action": "Verify the QuickDraw workspace is visible behind the viewer.",
                "expected": "QuickDraw application remains accessible behind the viewer."
            })

        elif 'browser' in ac_lower or 'external' in ac_lower:
            # AC: No external browser or online hosting is used
            steps.append({
                "action": "Verify no external browser window is launched.",
                "expected": "No external browser is opened. Content is displayed in-app."
            })

        else:
            # Generic Help verification
            steps.append({
                "action": f"Verify the {feature_name} content is displayed correctly.",
                "expected": "Manual content is displayed in the in-app viewer."
            })

        # Step 4: Close the viewer (if applicable)
        if 'viewer' in ac_lower or 'open' in ac_lower:
            steps.append({
                "action": "Close the viewer.",
                "expected": ""
            })

        return steps

    def _derive_properties_panel_steps(
        self,
        ac_bullet: str,
        feature_name: str,
        entry_point: str
    ) -> List[Dict[str, str]]:
        """Derive steps for Properties Panel features.

        Properties Panel features require object selection first, then
        manipulating properties through the panel.
        """
        steps = []
        ac_lower = ac_bullet.lower()

        # Step 1: Navigate to Properties Panel (object should already be selected from setup steps)
        steps.append({
            "action": f"Navigate to the {entry_point} on the right side of the screen.",
            "expected": f"{entry_point} is displayed showing options for the selected object."
        })

        # Step 2: Context-specific verification based on AC content
        if 'label' in ac_lower and ('reposition' in ac_lower or 'position' in ac_lower):
            # AC: Labels can be repositioned
            steps.append({
                "action": "Locate the label position controls in the Properties Panel.",
                "expected": "Label position controls are visible and enabled."
            })
            steps.append({
                "action": "Change the label position using the available controls.",
                "expected": "Label is repositioned on the canvas."
            })
            steps.append({
                "action": "Verify the label is displayed at the new position.",
                "expected": "Label appears at the repositioned location without overlapping other labels."
            })

        elif 'label' in ac_lower and 'visibility' in ac_lower:
            # AC: Label visibility control
            steps.append({
                "action": "Locate the label visibility controls in the Properties Panel.",
                "expected": "Label visibility toggle/controls are visible."
            })
            steps.append({
                "action": "Toggle the label visibility.",
                "expected": "Label visibility changes accordingly on the canvas."
            })

        elif 'label' in ac_lower and ('display' in ac_lower or 'show' in ac_lower or 'multiple' in ac_lower):
            # AC: Multiple labels display
            steps.append({
                "action": "Verify all available labels for the object are shown in the Properties Panel.",
                "expected": "All applicable labels (e.g., Radius, Diameter, Length, Dimensions, GPS coordinates) are listed."
            })
            steps.append({
                "action": "Enable multiple labels for the object.",
                "expected": "Multiple labels are displayed on the canvas."
            })

        elif 'overlap' in ac_lower or 'readability' in ac_lower or 'clutter' in ac_lower:
            # AC: Avoid label overlapping
            steps.append({
                "action": "Enable multiple labels that would normally overlap.",
                "expected": "Labels are displayed on the canvas."
            })
            steps.append({
                "action": "Verify that label repositioning helps avoid overlapping.",
                "expected": "Labels can be repositioned to improve readability and avoid visual clutter."
            })

        elif 'geometric' in ac_lower or 'preserve' in ac_lower:
            # AC: Preserve geometric meaning
            steps.append({
                "action": "Reposition a measurement label (e.g., radius or diameter).",
                "expected": "Label is repositioned within acceptable bounds."
            })
            steps.append({
                "action": "Verify the geometric meaning is preserved.",
                "expected": "Label remains close to the related geometry (e.g., radius label stays near the radius line)."
            })

        elif 'control' in ac_lower and 'panel' in ac_lower:
            # AC: Features controlled via Properties Panel
            steps.append({
                "action": f"Locate the {feature_name} controls in the Properties Panel.",
                "expected": f"{feature_name} controls are visible and accessible."
            })
            steps.append({
                "action": f"Use the controls to adjust {feature_name}.",
                "expected": "Changes are reflected on the canvas immediately."
            })

        elif 'supported' in ac_lower or 'applies' in ac_lower:
            # AC: Feature applies only to supported items
            steps.append({
                "action": f"Verify {feature_name} is available for the selected object type.",
                "expected": f"{feature_name} controls are enabled for supported object types."
            })
            steps.append({
                "action": f"Apply {feature_name} to the object.",
                "expected": f"{feature_name} is applied successfully to the supported object."
            })

        else:
            # Generic Properties Panel verification
            steps.append({
                "action": f"Locate the {feature_name} options in the Properties Panel.",
                "expected": f"{feature_name} options are visible and accessible."
            })
            steps.append({
                "action": f"Verify {feature_name} can be controlled via the Properties Panel.",
                "expected": f"{feature_name} settings can be adjusted from the Properties Panel."
            })

        return steps

    def _humanize_objective(self, ac_bullet: str, feature_name: str) -> str:
        """Create a human-readable objective from AC text."""
        text = ac_bullet.strip()

        # Remove common prefixes
        text = re.sub(r'^(?:the\s+)?(?:user\s+)?(?:can|should|must|shall)\s+', '', text, flags=re.IGNORECASE)

        # Lowercase first char if not acronym
        if text and text[0].isupper() and (len(text) < 2 or not text[1].isupper()):
            text = text[0].lower() + text[1:]

        # Truncate if too long
        if len(text) > 100:
            text = text[:97].rsplit(' ', 1)[0] + '...'

        return text

    def _format_expected_result(self, verification: str) -> str:
        """Format verification text as a proper expected result."""
        result = verification.strip()

        # Capitalize first letter
        if result:
            result = result[0].upper() + result[1:]

        # Add period if missing
        if result and not result.endswith('.'):
            result += '.'

        return result

    def _generate_edge_case_test(
        self,
        test_id: str,
        edge_case: Dict,
        feature_name: str,
        story_data: Dict
    ) -> Optional[Dict]:
        """Generate test for edge case scenario."""
        edge_type = edge_case['type']
        story_type = getattr(self, 'story_type', StoryType.UNKNOWN)

        # For Help/Documentation stories, always use Help Menu
        if story_type == StoryType.HELP_DOCUMENTATION:
            entry_point = "Help Menu"
        else:
            entry_point = edge_case.get('entry_point', 'Application Menu')

        title = f"{test_id}: {feature_name} / {entry_point} / {edge_case['title']}"

        # Help/Documentation features don't need create file step
        if story_type == StoryType.HELP_DOCUMENTATION:
            steps = self._get_standard_setup_steps(include_create_file=False)
        else:
            steps = self._get_standard_setup_steps()

        if edge_type == 'no_selection':
            # Note: Standard setup already includes file creation, so don't add another
            steps.extend([
                {"action": f"Navigate to {entry_point}.", "expected": f"{entry_point} is displayed."},
                {"action": f"Attempt to use the {feature_name} feature without selecting any object.",
                 "expected": ""},
                {"action": "Verify appropriate feedback is provided when no object is selected.",
                 "expected": "Feature is disabled or provides feedback that no object is selected."},
            ])
            objective = f"Verify that <b>{feature_name}</b> provides appropriate feedback when <b>no object is selected</b>"

        elif edge_type == 'invalid_type':
            # Note: Standard setup already includes file creation
            steps.extend([
                {"action": "Create an object of incompatible type (e.g., text annotation).",
                 "expected": "Object is created on the canvas."},
                {"action": "Select the object.",
                 "expected": "Object is selected with selection handles visible."},
                {"action": f"Navigate to {entry_point}.", "expected": f"{entry_point} is displayed."},
                {"action": f"Attempt to use the {feature_name} feature.", "expected": ""},
                {"action": "Verify appropriate feedback is provided for incompatible object type.",
                 "expected": "Feature is disabled or provides feedback about incompatible object type."},
            ])
            objective = f"Verify that <b>{feature_name}</b> handles <b>incompatible object types</b> appropriately"

        elif edge_type == 'duplicate_prevention':
            # Note: Standard setup already includes file creation
            steps.extend([
                {"action": "Draw an object/shape on the canvas.",
                 "expected": "Object is created and displayed on the canvas."},
                {"action": "Select the created object.",
                 "expected": "Object is selected with selection handles visible."},
                {"action": f"Navigate to {entry_point}.", "expected": f"{entry_point} is displayed."},
                {"action": f"Apply the {feature_name} feature.", "expected": "Feature is applied successfully."},
                {"action": f"Navigate to {entry_point} again.", "expected": ""},
                {"action": f"Attempt to apply the {feature_name} feature again.", "expected": ""},
                {"action": "Verify no duplicate is created.",
                 "expected": "Feature prevents duplicate application."},
            ])
            objective = f"Verify that <b>reapplying {feature_name}</b> does not create <b>duplicates</b>"

        elif edge_type == 'empty_state':
            steps.extend([
                {"action": "Create a new empty document/drawing.", "expected": ""},
                {"action": f"Navigate to {entry_point}.", "expected": ""},
                {"action": f"Verify the {feature_name} feature behavior with empty state.",
                 "expected": "Feature handles empty state appropriately."},
            ])
            objective = f"Verify that <b>{feature_name}</b> handles <b>empty state</b> appropriately"

        else:
            return None

        steps.append(self._get_close_step())
        return {'id': test_id, 'title': title, 'steps': steps, 'objective': objective}

    def _generate_platform_tests(
        self,
        story_id: str,
        feature_name: str,
        story_data: Dict,
        qa_details: Dict
    ) -> List[Dict]:
        """Generate platform-specific tests."""
        platform_tests = []
        platforms = qa_details.get('platforms', [])
        story_type = getattr(self, 'story_type', StoryType.UNKNOWN)
        entry_points = qa_details.get('entry_points', [])

        # Determine entry point based on story type
        if story_type == StoryType.HELP_DOCUMENTATION:
            entry_point = "Help Menu"
        elif story_type == StoryType.PROPERTIES or 'Properties Panel' in entry_points:
            entry_point = "Properties Panel"
        else:
            entry_point = self.app.determine_entry_point(feature_name, entry_points)

        # Check for touch platforms - separate tablets and phones
        tablet_platforms = [p for p in platforms if p in ['iPad', 'Android Tablet']]
        phone_platforms = [p for p in platforms if p in ['iPhone', 'Android Phone']]

        # Combine tablet touch tests into a single "(Tablets)" test if both iPad and Android Tablet present
        if len(tablet_platforms) >= 2:
            # Combined tablets test
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += self.rules.test_id_increment

            title = f"{test_id}: {feature_name} / {entry_point} / Touch interaction (Tablets)"

            # Help/Documentation features don't need create file step
            if story_type == StoryType.HELP_DOCUMENTATION:
                steps = self._get_standard_setup_steps(include_create_file=False)
            else:
                steps = self._get_standard_setup_steps()

                # Add object setup for Properties Panel or object interaction features
                needs_object = (
                    self.app.requires_object_interaction(feature_name) or
                    entry_point == "Properties Panel" or
                    story_type == StoryType.PROPERTIES
                )
                if needs_object:
                    steps.extend([
                        {"action": "Draw an object/shape on the canvas using touch gestures.",
                         "expected": "Object is created and displayed on the canvas."},
                        {"action": "Select the object using touch.",
                         "expected": "Object is selected and selection handles are visible."},
                    ])

            steps.extend([
                {"action": f"Navigate to {entry_point} using touch.", "expected": f"{entry_point} opens."},
                {"action": f"Access the {feature_name} using touch gestures.", "expected": f"The {feature_name} feature is activated."},
                {"action": f"Verify the {feature_name} is accessible via touch input.",
                 "expected": f"{feature_name} works correctly with touch interaction on iPad and Android Tablet."},
            ])
            steps.append(self._get_close_step())

            objective = f"Verify that <b>{feature_name}</b> works correctly on <b>iPad and Android Tablet</b> using <b>touch or stylus</b>"
            platform_tests.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})
        elif len(tablet_platforms) == 1:
            # Single tablet platform - use specific name
            platform = tablet_platforms[0]
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += self.rules.test_id_increment

            title = f"{test_id}: {feature_name} / {entry_point} / Touch interaction ({platform})"

            # Help/Documentation features don't need create file step
            if story_type == StoryType.HELP_DOCUMENTATION:
                steps = self._get_standard_setup_steps(include_create_file=False)
            else:
                steps = self._get_standard_setup_steps()

                # Add object setup for Properties Panel or object interaction features
                needs_object = (
                    self.app.requires_object_interaction(feature_name) or
                    entry_point == "Properties Panel" or
                    story_type == StoryType.PROPERTIES
                )
                if needs_object:
                    steps.extend([
                        {"action": "Draw an object/shape on the canvas using touch gestures.",
                         "expected": "Object is created and displayed on the canvas."},
                        {"action": "Select the object using touch.",
                         "expected": "Object is selected and selection handles are visible."},
                    ])

            steps.extend([
                {"action": f"Navigate to {entry_point} using touch.", "expected": f"{entry_point} opens."},
                {"action": f"Access the {feature_name} using touch gestures.", "expected": f"The {feature_name} feature is activated."},
                {"action": f"Verify the {feature_name} is accessible via touch input.",
                 "expected": f"{feature_name} works correctly with touch interaction on {platform}."},
            ])
            steps.append(self._get_close_step())

            objective = f"Verify that <b>{feature_name}</b> works correctly on <b>{platform}</b> using <b>touch or stylus</b>"
            platform_tests.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        # Generate separate tests for phone platforms (if any)
        for platform in phone_platforms:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += self.rules.test_id_increment

            title = f"{test_id}: {feature_name} / {entry_point} / Touch interaction ({platform})"

            # Help/Documentation features don't need create file step
            if story_type == StoryType.HELP_DOCUMENTATION:
                steps = self._get_standard_setup_steps(include_create_file=False)
            else:
                steps = self._get_standard_setup_steps()

                # Add object setup for Properties Panel or object interaction features
                needs_object = (
                    self.app.requires_object_interaction(feature_name) or
                    entry_point == "Properties Panel" or
                    story_type == StoryType.PROPERTIES
                )
                if needs_object:
                    steps.extend([
                        {"action": "Draw an object/shape on the canvas using touch gestures.",
                         "expected": "Object is created and displayed on the canvas."},
                        {"action": "Select the object using touch.",
                         "expected": "Object is selected and selection handles are visible."},
                    ])

            steps.extend([
                {"action": f"Navigate to {entry_point} using touch.", "expected": f"{entry_point} opens."},
                {"action": f"Access the {feature_name} using touch gestures.", "expected": f"The {feature_name} feature is activated."},
                {"action": f"Verify the {feature_name} is accessible via touch input.",
                 "expected": f"{feature_name} works correctly with touch interaction on {platform}."},
            ])
            steps.append(self._get_close_step())

            objective = f"Verify that <b>{feature_name}</b> works correctly on <b>{platform}</b> using <b>touch or stylus</b>"
            platform_tests.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        return platform_tests

    def _generate_accessibility_tests(
        self,
        story_id: str,
        feature_name: str,
        story_data: Dict,
        qa_details: Dict
    ) -> List[Dict]:
        """Generate accessibility tests for each platform."""
        accessibility_tests = []
        platforms = qa_details.get('platforms', self.app.supported_platforms)
        story_type = getattr(self, 'story_type', StoryType.UNKNOWN)
        entry_points = qa_details.get('entry_points', [])

        # Determine entry point based on story type
        if story_type == StoryType.HELP_DOCUMENTATION:
            entry_point = "Help Menu"
        elif story_type == StoryType.PROPERTIES or 'Properties Panel' in entry_points:
            entry_point = "Properties Panel"
        else:
            entry_point = self.app.determine_entry_point(feature_name, entry_points)

        # Helper: should we include create file step?
        include_create_file = story_type != StoryType.HELP_DOCUMENTATION

        # Helper: should we include object setup?
        needs_object_setup = (
            entry_point == "Properties Panel" or
            story_type == StoryType.PROPERTIES
        )

        # Windows accessibility test - use exact platform name in title
        windows_platform = 'Windows 11' if 'Windows 11' in platforms else ('Windows 10' if 'Windows 10' in platforms else 'Windows')
        if 'Windows 11' in platforms or 'Windows 10' in platforms or 'Windows' in platforms:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += self.rules.test_id_increment

            title = f"{test_id}: {feature_name} / Accessibility / Keyboard navigation ({windows_platform})"

            steps = [
                self._get_prereq_step(),
                {"action": "Pre-req: Accessibility Insights for Windows is installed", "expected": ""},
                self._get_launch_step(),
            ]
            if include_create_file:
                steps.append(self._get_create_file_step())

            # Add object setup for Properties Panel features
            if needs_object_setup:
                steps.extend(self._get_object_setup_steps())
                steps.extend([
                    {"action": f"Navigate to the {entry_point} on the right side of the screen.",
                     "expected": f"{entry_point} is displayed showing options for the selected object."},
                    {"action": f"Use the Tab key to navigate through label controls in the {entry_point}.",
                     "expected": "Focus cycles through all label visibility and positioning controls."},
                ])
            else:
                steps.extend([
                    {"action": f"Open the {entry_point}.", "expected": f"{entry_point} opens displaying available commands."},
                    {"action": f"Select the {feature_name} command.", "expected": "The in-app viewer opens displaying the manual content." if story_type == StoryType.HELP_DOCUMENTATION else f"The {feature_name} dialog opens."},
                    {"action": f"Use the Tab key to navigate through controls in the viewer.",
                     "expected": "Focus cycles through all interactive elements within the viewer."},
                ])
            steps.append(self._get_close_step())

            objective = f"Verify that <b>{feature_name}</b> controls meet <b>WCAG 2.1 AA</b> standards on <b>{windows_platform}</b>"
            accessibility_tests.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        # macOS accessibility test
        if 'macOS' in platforms or 'Mac' in platforms:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += self.rules.test_id_increment

            title = f"{test_id}: {feature_name} / Accessibility / VoiceOver navigation (macOS)"

            steps = [
                self._get_prereq_step(),
                {"action": "Pre-req: VoiceOver is enabled (Cmd+F5)", "expected": ""},
                self._get_launch_step(),
            ]
            if include_create_file:
                steps.append(self._get_create_file_step())

            steps.extend([
                {"action": f"Navigate to {entry_point} using keyboard (Tab/Arrow keys).", "expected": ""},
                {"action": f"Verify the {feature_name} controls are announced with meaningful labels.",
                 "expected": f"VoiceOver announces {feature_name} controls with meaningful labels and roles."},
                {"action": "Verify keyboard focus indicators are visible.",
                 "expected": "Focus indicators are clearly visible on all interactive elements."},
            ])
            steps.append(self._get_close_step())

            objective = f"Verify that <b>{feature_name}</b> controls are accessible via <b>VoiceOver</b> on <b>macOS</b>"
            accessibility_tests.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        # iPad/iOS accessibility test - use exact platform name in title
        ios_platform = 'iPad' if 'iPad' in platforms else 'iPhone'
        if 'iPad' in platforms or 'iPhone' in platforms:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += self.rules.test_id_increment

            title = f"{test_id}: {feature_name} / Accessibility / VoiceOver functionality ({ios_platform})"

            steps = [
                self._get_prereq_step(),
                {"action": f"Pre-req: VoiceOver is enabled on the {ios_platform}", "expected": ""},
                self._get_launch_step(),
            ]
            if include_create_file:
                steps.append(self._get_create_file_step())

            # Add object setup for Properties Panel features
            if needs_object_setup:
                steps.extend([
                    {"action": "Draw an object/shape on the canvas using touch gestures.",
                     "expected": "Object is created and displayed on the canvas."},
                    {"action": "Select the object using touch.",
                     "expected": "Object is selected and selection handles are visible."},
                    {"action": f"Navigate to the {entry_point} on the right side of the screen.",
                     "expected": f"{entry_point} is displayed showing options for the selected object."},
                    {"action": "Activate VoiceOver and navigate through the label controls.",
                     "expected": "VoiceOver reads out the label visibility and positioning controls correctly."},
                ])
            else:
                steps.extend([
                    {"action": f"Open the {entry_point}.", "expected": f"{entry_point} opens displaying available commands."},
                    {"action": f"Select the {feature_name} command.", "expected": "The in-app viewer opens displaying the manual content." if story_type == StoryType.HELP_DOCUMENTATION else f"The {feature_name} dialog opens."},
                    {"action": "Activate VoiceOver and navigate through the viewer.",
                     "expected": "VoiceOver reads out the content and controls correctly."},
                ])
            steps.append(self._get_close_step())

            objective = f"Verify that <b>{feature_name}</b> controls are accessible via <b>VoiceOver</b> on <b>{ios_platform}</b>"
            accessibility_tests.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        # Android accessibility test - use exact platform name in title
        android_platform = 'Android Tablet' if 'Android Tablet' in platforms else ('Android Phone' if 'Android Phone' in platforms else 'Android')
        if 'Android Tablet' in platforms or 'Android Phone' in platforms or 'Android' in platforms:
            test_id = f"{story_id}-{self.test_id_counter:03d}"
            self.test_id_counter += self.rules.test_id_increment

            title = f"{test_id}: {feature_name} / Accessibility / Accessibility Scanner ({android_platform})"

            steps = [
                self._get_prereq_step(),
                {"action": "Pre-req: Accessibility Scanner is installed", "expected": ""},
                self._get_launch_step(),
            ]
            if include_create_file:
                steps.append(self._get_create_file_step())

            # Add object setup for Properties Panel features
            if needs_object_setup:
                steps.extend([
                    {"action": "Draw an object/shape on the canvas using touch gestures.",
                     "expected": "Object is created and displayed on the canvas."},
                    {"action": "Select the object using touch.",
                     "expected": "Object is selected and selection handles are visible."},
                    {"action": f"Navigate to the {entry_point} on the right side of the screen.",
                     "expected": f"{entry_point} is displayed showing options for the selected object."},
                    {"action": "Run Accessibility Scanner on the Properties Panel.",
                     "expected": "Accessibility Scanner identifies all label controls and provides feedback."},
                ])
            else:
                steps.extend([
                    {"action": f"Open the {entry_point}.", "expected": f"{entry_point} opens displaying available commands."},
                    {"action": f"Select the {feature_name} command.", "expected": "The in-app viewer opens displaying the manual content." if story_type == StoryType.HELP_DOCUMENTATION else f"The {feature_name} dialog opens."},
                    {"action": "Run Accessibility Scanner on the viewer.", "expected": "Accessibility Scanner identifies all interactive elements and provides feedback."},
                ])
            steps.append(self._get_close_step())

            objective = f"Verify that <b>{feature_name}</b> controls meet accessibility standards on <b>{android_platform}</b>"
            accessibility_tests.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        # Web browser accessibility (for web apps)
        if self.app.app_type == 'web':
            web_platforms = [p for p in platforms if p in ['Chrome', 'Firefox', 'Safari', 'Edge']]
            if web_platforms:
                test_id = f"{story_id}-{self.test_id_counter:03d}"
                self.test_id_counter += self.rules.test_id_increment

                title = f"{test_id}: {feature_name} / Accessibility / Screen reader and keyboard (Web)"

                steps = [
                    self._get_prereq_step(),
                    {"action": "Pre-req: Screen reader (NVDA/JAWS/VoiceOver) is enabled", "expected": ""},
                    self._get_launch_step(),
                    self._get_create_file_step(),
                    {"action": f"Navigate to {entry_point} using keyboard (Tab/Arrow keys).", "expected": ""},
                    {"action": f"Verify the {feature_name} controls have correct ARIA roles and labels.",
                     "expected": "Screen reader announces controls with meaningful labels."},
                    {"action": "Verify focus indicators are visible.",
                     "expected": "Focus is clearly visible on all interactive elements."},
                ]
                steps.append(self._get_close_step())

                objective = f"Verify that <b>{feature_name}</b> is accessible via <b>keyboard and screen reader</b>"
                accessibility_tests.append({'id': test_id, 'title': title, 'steps': steps, 'objective': objective})

        return accessibility_tests

    # Helper Methods

    def _parse_qa_prep(self, qa_prep: str) -> Dict:
        """Parse QA Prep content to extract testing details."""
        if not qa_prep:
            return {}

        qa_lower = qa_prep.lower()
        details = {
            'entry_points': [],
            'platforms': [],
            'edge_cases': [],
            'units': False,
            'undo_redo_actions': [],
            'visibility': False,
            'negative_scenarios': []
        }

        # Extract entry points using project config with word boundary matching
        # Avoids false matches like 'cut' in 'executed'
        for keyword, entry_point in self.app.entry_point_mappings.items():
            pattern = rf'\b{re.escape(keyword)}\b'
            if re.search(pattern, qa_lower):
                if entry_point not in details['entry_points']:
                    details['entry_points'].append(entry_point)

        # ALWAYS use ALL supported platforms for touch/accessibility tests
        # Platform mentions in QA prep are informational only - we test all platforms
        # to ensure comprehensive coverage across all supported devices
        details['platforms'] = list(self.app.supported_platforms)

        # Detect unit system tests
        if 'imperial' in qa_lower and 'metric' in qa_lower:
            details['units'] = True

        # Detect visibility toggle
        if 'visibility' in qa_lower or 'show or hide' in qa_lower:
            details['visibility'] = True

        # Extract undo/redo actions
        if 'undo' in qa_lower or 'redo' in qa_lower:
            if 'add' in qa_lower or 'remove' in qa_lower:
                details['undo_redo_actions'].append('add/remove')
            if 'visibility' in qa_lower:
                details['undo_redo_actions'].append('visibility')

        # Detect negative scenarios
        if 'no object' in qa_lower or 'no selection' in qa_lower:
            details['negative_scenarios'].append('no_selection')
        if 'wrong' in qa_lower or 'invalid' in qa_lower:
            details['negative_scenarios'].append('invalid_type')
        if 'duplicate' in qa_lower or 'reappl' in qa_lower:
            details['edge_cases'].append('duplicate_prevention')

        return details

    def _extract_edge_cases(self, qa_details: Dict, feature_name: str) -> List[Dict]:
        """Extract edge case scenarios from QA details.

        Filters out irrelevant edge cases based on story type.
        For example, Help/Documentation stories don't need object selection tests.
        """
        edge_cases = []
        story_type = getattr(self, 'story_type', StoryType.UNKNOWN)
        entry_points = qa_details.get('entry_points', [])

        # Determine entry point based on story type
        if story_type == StoryType.HELP_DOCUMENTATION:
            entry_point = "Help Menu"
        elif story_type == StoryType.PROPERTIES or 'Properties Panel' in entry_points:
            entry_point = "Properties Panel"
        else:
            entry_point = self.app.determine_entry_point(feature_name, entry_points)

        # Help/Documentation stories should NEVER have object-related edge cases
        if story_type == StoryType.HELP_DOCUMENTATION:
            # Only include Help-specific edge cases if any
            # For now, Help features don't need typical edge cases
            return edge_cases

        # Skip object-related edge cases for non-object-manipulation story types
        object_manipulation_types = {
            StoryType.TOOL,
            StoryType.MEASUREMENT,
            StoryType.PROPERTIES
        }
        is_object_story = story_type in object_manipulation_types

        if is_object_story and 'no_selection' in qa_details.get('negative_scenarios', []):
            edge_cases.append({
                'type': 'no_selection',
                'title': 'No selection behavior (disabled state)',
                'entry_point': entry_point
            })

        if is_object_story and 'invalid_type' in qa_details.get('negative_scenarios', []):
            edge_cases.append({
                'type': 'invalid_type',
                'title': 'Incompatible object type handling',
                'entry_point': entry_point
            })

        if 'duplicate_prevention' in qa_details.get('edge_cases', []):
            edge_cases.append({
                'type': 'duplicate_prevention',
                'title': 'Duplicate application prevention',
                'entry_point': entry_point
            })

        if 'empty_state' in qa_details.get('edge_cases', []):
            edge_cases.append({
                'type': 'empty_state',
                'title': 'Empty state handling',
                'entry_point': entry_point
            })

        return edge_cases

    def _extract_feature_name(self, story_title: str) -> str:
        """Extract the core feature name from story title."""
        title = story_title.strip()

        # Remove user story prefixes
        prefixes = ['As a', 'As an', 'I want', 'I need', 'User can', 'Users can']
        for prefix in prefixes:
            if title.lower().startswith(prefix.lower()):
                parts = title.split(',')
                if len(parts) > 1:
                    title = parts[1].strip() if 'so that' not in parts[1].lower() else parts[0].replace(prefix, '').strip()
                else:
                    title = title.replace(prefix, '').strip()
                break

        return title

    def _validate_and_fix_title(self, title: str, feature_name: str) -> str:
        """
        Validate and fix scenario titles to ensure they are complete and meaningful.

        Rules:
        1. No truncated/incomplete phrases (e.g., "Display content without requiring")
        2. No overly vague titles (e.g., "Selection behavior", "Functionality")
        3. Titles should be grammatically complete
        4. No trailing periods (they're redundant in titles)
        """
        if not title:
            return f"{feature_name} functionality"

        # Remove trailing periods (redundant in titles)
        title = title.rstrip('.')

        # List of incomplete/vague titles that need fixing
        vague_titles = {
            'Selection behavior': 'Selection and interaction behavior',
            'Display content without requiring': 'Content accessible without internet connection',
            'Functionality': f'{feature_name} core functionality',
            'Feature availability': f'{feature_name} availability in menu',
            'Behavior': f'{feature_name} expected behavior',
            'Canvas update behavior': 'Canvas updates immediately on action',
            'Command availability': f'{feature_name} command available in menu',
            'Transformation behavior': 'Transformation applied to selected objects',
        }

        # Check for exact matches first
        if title in vague_titles:
            return vague_titles[title]

        # Check for incomplete patterns (ending with prepositions or articles)
        incomplete_endings = [
            ' without', ' with', ' for', ' to', ' from', ' in', ' on', ' at',
            ' the', ' a', ' an', ' and', ' or', ' but', ' if', ' when'
        ]
        for ending in incomplete_endings:
            if title.lower().endswith(ending):
                # Try to fix by adding context
                if 'without' in ending:
                    title = f"{title} additional requirements"
                elif 'with' in ending:
                    title = f"{title} specific configuration"
                elif 'for' in ending:
                    title = f"{title} {feature_name}"
                else:
                    title = f"{title} (complete scenario)"
                break

        # Ensure title doesn't start with "Verify" (redundant in scenario part of title)
        if title.lower().startswith('verify '):
            title = title[7:]
            if title:
                title = title[0].upper() + title[1:]

        # Ensure minimum meaningful length
        if len(title) < 10:
            title = f"{feature_name} - {title}"

        return title

    def _extract_scenario_from_ac(self, ac_bullet: str, feature_name: str) -> str:
        """Extract a clean, balanced scenario description from AC text.

        Uses description context to generate meaningful, context-aware scenario titles.
        Creates action-oriented titles that follow the pattern:
        "Verify [action] [target/result]"
        """
        text = ac_bullet.strip()
        text_lower = text.lower()
        story_type = getattr(self, 'story_type', StoryType.UNKNOWN)
        desc_ctx = getattr(self, 'description_context', None)

        # Remove common prefixes
        prefixes = ['the user can', 'user can', 'users can', 'the system shall',
                    'shall be able to', 'able to', 'should be able to', 'must be able to',
                    'the application', 'application shall', 'the feature']
        for prefix in prefixes:
            if text_lower.startswith(prefix):
                text = text[len(prefix):].strip()
                text_lower = text.lower()
                break

        # =====================================================================
        # HELP/DOCUMENTATION SPECIFIC SCENARIO TITLES
        # Use description context to generate meaningful titles
        # =====================================================================
        if story_type == StoryType.HELP_DOCUMENTATION:
            title = self._generate_help_scenario_title(text_lower, feature_name, desc_ctx)
            return self._validate_and_fix_title(title, feature_name)

        # Extract key action and create balanced title - order matters (more specific first)
        action_patterns = [
            # Specific patterns first
            ('horizontally flip', 'Horizontal flip (mirror) transformation'),
            ('vertically flip', 'Vertical flip (mirror) transformation'),
            ('horizontal', 'Horizontal mirror transformation'),
            ('vertical', 'Vertical mirror transformation'),
            ('mirror.*horizontal', 'Horizontal mirror transformation'),
            ('mirror.*vertical', 'Vertical mirror transformation'),
            ('rotate.*object', 'Rotate selected objects'),
            ('multi.*select', 'Multi-selection transformation'),
            ('undo.*redo', 'Undo and redo support'),
            ('undo', 'Undo action support'),
            ('redo', 'Redo action support'),
            ('enabled.*when.*select', 'Commands enabled on selection'),
            ('enabled', 'Command enabled state'),
            ('disabled', 'Command disabled state'),
            ('properties panel.*available', 'Properties Panel commands'),
            ('properties panel.*synchron', 'Menu and Properties Panel sync'),
            ('properties panel', 'Properties Panel availability'),
            ('synchron', 'Menu and Properties Panel sync'),
            ('preserve.*position', 'Position preservation on transform'),
            ('preserve', 'Property preservation on transform'),
            ('update.*canvas', 'Immediate canvas update'),
            ('canvas.*immediate', 'Immediate canvas update'),
            ('canvas', 'Canvas update behavior'),
            ('color.*border.*stroke', 'Visual property preservation'),
            ('not.*modify.*color', 'Visual property preservation'),
            ('color', 'Color preservation on transform'),
            ('border', 'Border preservation on transform'),
            ('available.*tools', 'Tools menu commands available'),
            ('available.*menu', 'Menu commands available'),
            ('available', 'Command availability'),
            ('transform.*together', 'Group transformation behavior'),
            ('transform', 'Transformation behavior'),
            ('rotate', 'Rotate transformation'),
            ('mirror', 'Mirror transformation'),
            ('flip', 'Flip transformation'),
            ('select', 'Selection behavior'),
        ]

        # Try to match action patterns (uses regex)
        for pattern, title in action_patterns:
            if re.search(pattern, text_lower):
                return self._validate_and_fix_title(title, feature_name)

        # If no pattern matched, create a summarized title
        # Extract the main verb and object
        # Look for verb phrases
        verb_match = re.search(
            r'\b(rotate|mirror|flip|transform|update|preserve|synchronize|enable|disable|select|display|show|hide|apply)\w*\b',
            text_lower
        )

        if verb_match:
            verb = verb_match.group(1).capitalize()
            # Find object after verb
            after_verb = text_lower[verb_match.end():].strip()
            words = after_verb.split()[:3]  # Take up to 3 words after verb
            if words:
                obj = ' '.join(words).rstrip('.,;:')
                title = f"{verb} {obj}"
                if len(title) > 50:
                    title = title[:47] + "..."
                return self._validate_and_fix_title(title, feature_name)
            return self._validate_and_fix_title(f"{verb} action applied", feature_name)

        # Fallback: Clean and truncate
        # Remove leading articles and conjunctions
        text = re.sub(r'^(the|a|an|and|or|but|if|when|then)\s+', '', text, flags=re.IGNORECASE)

        if text:
            text = text[0].upper() + text[1:]

        # Create a balanced truncation
        if len(text) > 50:
            # Try to break at a word boundary
            truncated = text[:47]
            last_space = truncated.rfind(' ')
            if last_space > 30:
                truncated = truncated[:last_space]
            text = truncated + "..."

        # Validate and fix the final title
        final_title = text if text else f"{feature_name} functionality"
        return self._validate_and_fix_title(final_title, feature_name)

    def _extract_main_action(self, ac_bullet: str, feature_name: str = "") -> str:
        """Extract the main action from AC text using semantic parsing."""
        text = ac_bullet.strip()

        # Use semantic step builder if available
        if self._step_builder:
            enhanced = self._step_builder.enhance_generic_step(
                action=text,
                expected="",
                feature_name=feature_name,
                ac_text=ac_bullet
            )
            if enhanced['action'] and 'perform the action' not in enhanced['action'].lower():
                return enhanced['action']

        # Fallback: Extract action verb and context
        action_verbs = [
            'import', 'export', 'save', 'open', 'create', 'delete', 'edit',
            'select', 'click', 'drag', 'enable', 'disable', 'toggle', 'set',
            'rotate', 'mirror', 'flip', 'transform', 'apply', 'enter', 'type',
            'navigate', 'access', 'verify', 'check', 'confirm'
        ]

        text_lower = text.lower()
        for verb in action_verbs:
            if verb in text_lower:
                idx = text_lower.find(verb)
                action = text[idx:].split('.')[0].strip()
                if action and len(action) > 5:
                    # Clean up and format
                    action = action[0].upper() + action[1:]
                    if not action.endswith('.'):
                        action += "."
                    return action

        # Enhanced fallback: Build action from feature name
        if feature_name:
            return f"Apply the {feature_name} action to the selected object."

        return f"Perform the {text[:60].strip()} action."

    def _extract_verification(self, ac_bullet: str, feature_name: str) -> str:
        """Extract verification criteria from AC text with specific, observable outcomes.

        Context-aware based on story type to avoid object-manipulation language
        for non-object features like Help/Documentation.
        """
        text_lower = ac_bullet.lower()
        story_type = getattr(self, 'story_type', StoryType.UNKNOWN)

        # Use semantic step builder for specific expected result
        if self._step_builder:
            expected = self._step_builder.extract_specific_expected_result(
                ac_text=ac_bullet,
                feature_name=feature_name
            )
            if expected and 'as expected' not in expected.lower():
                return expected.rstrip('.')

        # Extract from "should/will" clauses
        if 'should' in text_lower:
            idx = text_lower.find('should')
            result = ac_bullet[idx:].split('.')[0].strip()
            if result and len(result) > 10:
                return result

        if 'will' in text_lower:
            idx = text_lower.find('will')
            result = ac_bullet[idx:].split('.')[0].strip()
            if result and len(result) > 10:
                return result

        # Context-specific outcomes based on story type
        if story_type == StoryType.HELP_DOCUMENTATION:
            # Help/Documentation specific outcomes
            help_outcomes = {
                'open': f"{feature_name} viewer opens",
                'display': f"{feature_name} content is displayed",
                'appear': f"{feature_name} is visible in the menu",
                'viewer': "In-app viewer displays content correctly",
                'offline': "Content is accessible without internet connection",
                'browser': "No external browser is launched",
                'remain': "QuickDraw application remains open behind the viewer",
                'close': f"{feature_name} viewer closes",
            }
            for keyword, outcome in help_outcomes.items():
                if keyword in text_lower:
                    return outcome
            # Default for Help features
            return f"{feature_name} content is displayed correctly"

        # Action-specific observable outcomes (for object manipulation features)
        action_outcomes = {
            'display': f"{feature_name} is displayed",
            'show': f"{feature_name} is visible",
            'hide': f"{feature_name} is hidden",
            'enable': f"{feature_name} is enabled",
            'disable': f"{feature_name} is disabled",
            'rotate': f"Selected object is rotated",
            'mirror': f"Selected object is mirrored",
            'flip': f"Selected object is flipped",
            'transform': f"Object transformation is applied",
            'open': f"{feature_name} dialog opens",
            'close': f"{feature_name} closes",
            'save': f"Changes are saved",
            'update': f"{feature_name} is updated",
            'select': f"Object is selected",
            'apply': f"{feature_name} is applied to the selection",
        }

        for action_word, outcome in action_outcomes.items():
            if action_word in text_lower:
                return outcome

        # Check for visibility indicators
        if any(word in text_lower for word in ['displayed', 'shown', 'visible', 'appears']):
            return f"{feature_name} is displayed"

        # Check for state change indicators
        if any(word in text_lower for word in ['enabled', 'disabled', 'active', 'inactive']):
            if 'disabled' in text_lower or 'inactive' in text_lower:
                return f"{feature_name} is disabled"
            return f"{feature_name} is enabled"

        # Default: Context-specific outcome
        if story_type == StoryType.HELP_DOCUMENTATION:
            return f"{feature_name} content is displayed correctly"
        elif story_type in {StoryType.TOOL, StoryType.MEASUREMENT}:
            return f"{feature_name} is applied to selected object(s)"
        elif story_type == StoryType.DIALOG:
            return f"{feature_name} dialog operates correctly"
        else:
            return f"{feature_name} functionality works as expected"

    def _is_cancelled(self, text: str) -> bool:
        """Check if text indicates cancelled/out-of-scope."""
        text_lower = text.lower()
        return any(ind in text_lower for ind in self.rules.cancelled_indicators)

    def _detect_redundant_criteria(self, criteria: List[str]) -> List[Tuple[int, int, str]]:
        """
        Detect redundant/similar acceptance criteria to avoid duplicate tests.

        Returns list of tuples: (ac_index1, ac_index2, reason)
        where ac_index2 should be skipped in favor of ac_index1.
        """
        redundant = []

        # Normalize ACs for comparison
        normalized = []
        for ac in criteria:
            norm = ac.lower().strip()
            # Remove quotes and extra whitespace
            norm = re.sub(r'[\"\']', '', norm)
            norm = re.sub(r'\s+', ' ', norm)
            normalized.append(norm)

        # Check for similar ACs
        for i, ac1 in enumerate(normalized):
            for j, ac2 in enumerate(normalized):
                if i >= j:
                    continue

                # Check for high similarity using word overlap
                if self._are_acs_similar(ac1, ac2):
                    reason = "Similar content - consolidating tests"
                    redundant.append((i, j, reason))

        return redundant

    def _are_acs_similar(self, text1: str, text2: str, threshold: float = 0.7) -> bool:
        """Check if two AC texts are similar using word overlap."""
        # Extract significant words (remove common words)
        stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                     'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                     'shall', 'should', 'can', 'could', 'may', 'might', 'must',
                     'that', 'this', 'these', 'those', 'and', 'or', 'but', 'if',
                     'when', 'where', 'which', 'who', 'whom', 'why', 'how',
                     'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
                     'up', 'about', 'into', 'over', 'after', 'user', 'users'}

        words1 = set(w for w in text1.split() if w not in stopwords and len(w) > 2)
        words2 = set(w for w in text2.split() if w not in stopwords and len(w) > 2)

        if not words1 or not words2:
            return False

        intersection = words1 & words2
        union = words1 | words2

        similarity = len(intersection) / len(union) if union else 0

        # Also check for key phrase similarity
        # e.g., both ACs about "menu" and "appear/visible"
        key_phrases_1 = self._extract_key_phrases(text1)
        key_phrases_2 = self._extract_key_phrases(text2)

        if key_phrases_1 and key_phrases_2:
            phrase_overlap = len(key_phrases_1 & key_phrases_2) / len(key_phrases_1 | key_phrases_2)
            # Boost similarity if key phrases match
            similarity = max(similarity, phrase_overlap * 0.9)

        return similarity >= threshold

    def _extract_key_phrases(self, text: str) -> set:
        """Extract key phrases from AC text for similarity comparison."""
        phrases = set()

        # Menu visibility phrases
        if 'menu' in text and any(w in text for w in ['appear', 'visible', 'display', 'show', 'access']):
            phrases.add('menu_visibility')

        # Viewer/open phrases
        if any(w in text for w in ['viewer', 'open', 'launch', 'display']):
            phrases.add('viewer_open')

        # Offline/internet phrases
        if any(w in text for w in ['offline', 'internet', 'connection']):
            phrases.add('offline_access')

        # Browser phrases
        if any(w in text for w in ['browser', 'external']):
            phrases.add('no_browser')

        return phrases

    def _generate_help_scenario_title(
        self,
        ac_lower: str,
        feature_name: str,
        desc_ctx: Optional[DescriptionContext]
    ) -> str:
        """
        Generate meaningful scenario titles for Help/Documentation features.

        Uses description context (menu path, user flow, key features) to create
        titles that accurately describe what the test verifies.
        """
        # Pattern-based title generation for Help/Documentation ACs
        # IMPORTANT: Titles must be COMPLETE and MEANINGFUL - no truncated phrases
        help_patterns = [
            # Menu visibility patterns
            (r'appear.*menu|menu.*appear|visible.*menu|menu.*visible',
             '"User Manual" appears under the Help menu'),

            # Viewer opening patterns
            (r'select.*open.*viewer|open.*in-app.*viewer|viewer.*open|selecting.*opens',
             'Selecting command opens in-app viewer'),

            # Offline access patterns
            (r'offline|without.*internet|no.*internet|without.*connection',
             'Content accessible without internet connection'),

            # No external browser patterns
            (r'external.*browser|browser.*external|no.*browser|not.*browser',
             'No external browser launched when viewing'),

            # Application remains open patterns
            (r'remain.*open|open.*behind|quickdraw.*remain|behind.*viewer',
             'Application remains open behind viewer'),

            # Unsupported features patterns
            (r'unsupported|not.*available|absence.*feature|multi-object|batch|cloud',
             'Unsupported features not available in UI'),

            # Content display patterns
            (r'display.*content|content.*display|pdf.*display|manual.*display',
             'Manual content displayed correctly in viewer'),

            # Close/exit patterns
            (r'close.*viewer|viewer.*close|exit.*viewer',
             'Viewer closes and returns to main application'),

            # State persistence patterns
            (r'persist|remember|save.*state|restore',
             'State persists after closing and reopening'),

            # Workflow/reopen patterns
            (r'reopen|open.*again|second.*time',
             'Reopening displays content correctly'),
        ]

        for pattern, title in help_patterns:
            if re.search(pattern, ac_lower):
                return title

        # Use description context if available
        if desc_ctx:
            # Check if AC relates to user flow steps
            for flow_step in desc_ctx.user_flow:
                flow_lower = flow_step.lower()
                # Check for keyword overlap
                ac_words = set(ac_lower.split())
                flow_words = set(flow_lower.split())
                overlap = ac_words & flow_words
                if len(overlap) >= 3:  # Significant overlap
                    # Use the flow step as inspiration for the title
                    return self._clean_flow_step_for_title(flow_step)

            # Check if AC relates to key features
            for feature in desc_ctx.key_features:
                if feature.lower() in ac_lower:
                    return f"{feature.capitalize()} verification"

        # Fallback: Extract meaningful title from AC text
        # Remove generic phrases
        clean_text = re.sub(
            r'\b(the|a|an|user|users|shall|should|must|can|will)\b',
            '',
            ac_lower
        )
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        # Capitalize and truncate
        if clean_text:
            clean_text = clean_text[0].upper() + clean_text[1:]
            if len(clean_text) > 50:
                clean_text = clean_text[:47] + "..."
            return clean_text

        return f"{feature_name} functionality"

    def _clean_flow_step_for_title(self, flow_step: str) -> str:
        """Clean a user flow step to use as a scenario title."""
        # Remove leading action verbs for title format
        title = re.sub(
            r'^(user\s+)?(selects?|opens?|clicks?|views?|navigates?)\s+',
            '',
            flow_step,
            flags=re.IGNORECASE
        )
        title = title.strip()

        # Capitalize first letter
        if title:
            title = title[0].upper() + title[1:]

        # Truncate if too long
        if len(title) > 50:
            title = title[:47] + "..."

        return title

    def _generate_help_objective(self, ac_bullet: str, feature_name: str) -> str:
        """Generate context-appropriate objective for Help/Documentation features.

        Avoids "applied to selected object(s)" language for Help features.
        """
        ac_lower = ac_bullet.lower()

        # Pattern-based objectives for Help features
        if 'appear' in ac_lower and 'menu' in ac_lower:
            return f"Verify that <b>{feature_name}</b> appears under the <b>Help menu</b>"

        elif 'viewer' in ac_lower and 'open' in ac_lower:
            return f"Verify that selecting <b>{feature_name}</b> opens an <b>in-app viewer</b> containing the PDF manual"

        elif 'select' in ac_lower and ('open' in ac_lower or 'viewer' in ac_lower):
            return f"Verify that selecting <b>{feature_name}</b> opens the <b>in-app viewer</b>"

        elif 'offline' in ac_lower or 'internet' in ac_lower:
            return f"Verify that the <b>{feature_name}</b> viewer displays content <b>without requiring an internet connection</b>"

        elif 'remain' in ac_lower and ('open' in ac_lower or 'behind' in ac_lower):
            return f"Verify that <b>QuickDraw remains open</b> behind the <b>{feature_name}</b> viewer"

        elif 'browser' in ac_lower or 'external' in ac_lower:
            return f"Verify that <b>no external browser</b> or online hosting is used for <b>{feature_name}</b>"

        elif 'unsupported' in ac_lower or 'absence' in ac_lower:
            return f"Verify that <b>unsupported features</b> are not available in the <b>{feature_name}</b>"

        else:
            # Default objective for Help features
            return f"Verify that <b>{feature_name}</b> displays correctly in the in-app viewer"
