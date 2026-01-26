"""
QA Planning Summary Service
Generates QA Planning Summary with evidence gates and optional LLM rewriting.
"""
import re
from typing import List, Optional, Dict
from core.domain.models import UserStory, TestCase, SummaryPlan, EvidenceModel, LintResult
from core.services.linting import SummaryLinter
from core.services.llm.base import LLMProvider


class SummaryService:
    """Service for generating QA Planning Summary."""
    
    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        debug: bool = False
    ):
        """Initialize summary service.
        
        Args:
            llm_provider: Optional LLM provider for rewriting
            debug: Enable debug output
        """
        self.llm_provider = llm_provider
        self.debug = debug
        
        # Forbidden assumptive terms (always forbidden)
        self.forbidden_assumptive = [
            'activation', 'activated', 'real-time', 'real time', 
            'visual feedback', 'dynamic', 'instant', 'assumingly',
            'expected behavior', 'state persistence', 'invalid inputs',
            'boundary conditions', 'generally', 'presumably'
        ]
    
    def generate_summary(
        self,
        story: UserStory,
        test_cases: List[TestCase]
    ) -> tuple[str, SummaryPlan, LintResult]:
        """Generate QA Planning Summary.
        
        Returns:
            Tuple of (final_text, plan, lint_result)
        """
        # Build evidence model
        evidence = self._build_evidence(story, test_cases)
        
        # Phase A: Build deterministic plan
        plan = self._build_summary_plan(story, test_cases, evidence)
        
        # Validate plan
        plan_valid, plan_errors = plan.validate()
        if not plan_valid and self.debug:
            print(f"[DEBUG] Plan validation errors: {plan_errors}")
        
        # Phase B: Render deterministic summary
        deterministic_summary = self._render_summary(plan)
        
        # Lint deterministic summary
        linter = SummaryLinter(evidence)
        lint_result = linter.lint(deterministic_summary)
        
        if not lint_result.ok:
            if self.debug:
                print(f"[DEBUG] Deterministic summary failed lint:")
                for err in lint_result.errors:
                    print(f"  - {err}")
            return deterministic_summary, plan, lint_result
        
        # If LLM enabled, try rewriting
        if self.llm_provider and self.llm_provider.is_available():
            llm_summary = self._rewrite_with_llm(
                deterministic_summary, plan, evidence
            )
            
            if llm_summary:
                # Lint LLM output
                llm_lint = linter.lint(llm_summary)
                
                if llm_lint.ok:
                    if self.debug:
                        print("[DEBUG] LLM rewrite passed lint, using LLM version")
                    return llm_summary, plan, llm_lint
                else:
                    if self.debug:
                        print("[DEBUG] LLM rewrite failed lint, falling back to deterministic")
                        for err in llm_lint.errors:
                            print(f"  - {err}")
        
        # Return deterministic version
        return deterministic_summary, plan, lint_result
    
    def _build_evidence(
        self,
        story: UserStory,
        test_cases: List[TestCase]
    ) -> EvidenceModel:
        """Build evidence model from story and test cases."""
        # Extract UI entry points from test titles
        entry_points = set()
        test_titles = []
        
        for tc in test_cases:
            test_titles.append(tc.title)
            
            if ' / ' in tc.title:
                parts = tc.title.split(' / ')
                if len(parts) >= 2:
                    entry_points.add(parts[1].strip())
        
        # Extract behaviors from AC
        behaviors = self._extract_behaviors(story.acceptance_criteria)
        
        # Build evidence model
        evidence = EvidenceModel(
            allowed_entry_points=sorted(list(entry_points)),
            allowed_behaviors=behaviors,
            forbidden_words=self.forbidden_assumptive,
            description_text=story.description,
            ac_text=story.acceptance_criteria,
            test_titles=test_titles
        )
        
        return evidence
    
    def _extract_behaviors(self, ac_text: str) -> List[str]:
        """Extract behavior verbs from AC text."""
        text = ac_text.lower()
        
        # Common action verbs
        verbs = [
            'display', 'show', 'open', 'close', 'activate', 'select',
            'flip', 'mirror', 'rotate', 'transform', 'edit', 'modify',
            'undo', 'redo', 'navigate', 'click', 'drag'
        ]
        
        found_behaviors = []
        for verb in verbs:
            if verb in text:
                found_behaviors.append(verb)
        
        return found_behaviors
    
    def _build_summary_plan(
        self,
        story: UserStory,
        test_cases: List[TestCase],
        evidence: EvidenceModel
    ) -> SummaryPlan:
        """Build deterministic summary plan from evidence."""
        # Extract feature name
        feature_name = self._extract_feature_name(story.title)
        
        # Build intro facts
        intro = self._build_intro(feature_name, story, evidence)
        
        # Build focus bullets (6-9) from AC
        bullets = self._build_focus_bullets(story, test_cases, evidence)
        
        # Build dependencies
        dependencies = self._build_dependencies(story, test_cases, evidence)
        
        # Build accessibility clause
        accessibility = self._build_accessibility_clause(test_cases)
        
        # Build platform clause
        platform = self._build_platform_clause(test_cases)
        
        return SummaryPlan(
            intro_facts=intro,
            bullet_themes=bullets,
            dependencies=dependencies,
            accessibility_clause=accessibility,
            platform_clause=platform
        )
    
    def _extract_feature_name(self, title: str) -> str:
        """Extract feature name from story title."""
        title = title.strip()
        for prefix in ['As a', 'As an', 'I want', 'I need']:
            if title.lower().startswith(prefix.lower()):
                parts = title.split(',')
                if len(parts) > 1:
                    title = parts[1].strip()
                else:
                    title = title.replace(prefix, '').strip()
                break
        
        # Clean up
        title = title.replace('Help: ', '').replace('Tool: ', '').strip()
        return title
    
    def _build_intro(
        self,
        feature_name: str,
        story: UserStory,
        evidence: EvidenceModel
    ) -> str:
        """Build intro paragraph from evidence only."""
        # Extract primary action
        primary_action = self._extract_primary_action(evidence)
        
        # Format UI surface
        ui_surface = self._format_ui_surface(evidence.allowed_entry_points)
        
        # Build intro
        intro = f"This work item introduces {feature_name}, enabling {primary_action} through {ui_surface}."
        
        return intro
    
    def _extract_primary_action(self, evidence: EvidenceModel) -> str:
        """Extract primary action from evidence."""
        text = f"{evidence.description_text} {evidence.ac_text}".lower()
        
        # Check for specific verbs
        if 'flip' in text:
            if 'horizontal' in text or 'vertical' in text:
                return "flip objects horizontally or vertically"
            return "flip objects"
        elif 'mirror' in text:
            return "mirror selected objects"
        elif 'rotate' in text:
            return "rotate selected objects"
        elif 'view' in text or 'display' in text or 'about' in text.lower():
            return "view application information"
        elif 'select' in text:
            return "select options"
        else:
            return "interact with the feature"
    
    def _format_ui_surface(self, entry_points: List[str]) -> str:
        """Format UI entry points naturally."""
        if not entry_points:
            return "designated entry points"
        
        if len(entry_points) == 1:
            return f"the {entry_points[0]}"
        elif len(entry_points) == 2:
            return f"the {entry_points[0]} and {entry_points[1]}"
        else:
            return f"the {', '.join(entry_points[:-1])}, and {entry_points[-1]}"
    
    def _build_focus_bullets(
        self,
        story: UserStory,
        test_cases: List[TestCase],
        evidence: EvidenceModel
    ) -> List[str]:
        """Build 6-9 focus bullets from AC order."""
        bullets = []
        seen_themes = set()
        
        # Parse AC into bullets
        ac_bullets = self._parse_ac(story.acceptance_criteria)
        
        # Convert AC bullets to QA bullets (evidence-based)
        for ac_bullet in ac_bullets:
            if len(bullets) >= 9:
                break
            
            ac_lower = ac_bullet.lower()
            
            # Skip accessibility (handled separately)
            if 'accessibility' in ac_lower or 'wcag' in ac_lower:
                continue
            
            # Skip out of scope
            if 'out of scope' in ac_lower:
                continue
            
            # Convert to QA bullet
            qa_bullet = self._ac_to_qa_bullet(ac_bullet, evidence)
            if qa_bullet:
                theme = self._extract_theme(qa_bullet)
                if theme not in seen_themes:
                    bullets.append(qa_bullet)
                    seen_themes.add(theme)
        
        # Ensure minimum 6 bullets
        if len(bullets) < 6:
            # Add generic bullets from test scenarios
            for tc in test_cases:
                if len(bullets) >= 6:
                    break
                
                if tc.is_accessibility:
                    continue
                
                # Extract scenario from title
                if ' / ' in tc.title:
                    parts = tc.title.split(' / ')
                    if len(parts) >= 3:
                        scenario = parts[2].strip()
                        scenario = scenario.split('(')[0].strip()
                        
                        theme = self._extract_theme(scenario)
                        if theme not in seen_themes and len(scenario) > 10:
                            bullets.append(scenario)
                            seen_themes.add(theme)
        
        return bullets[:9]
    
    def _parse_ac(self, ac_text: str) -> List[str]:
        """Parse AC into ordered bullets."""
        if not ac_text:
            return []
        
        bullets = []
        lines = ac_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or len(line) < 5:
                continue
            
            # Skip headers
            if line.lower().startswith(('acceptance criteria:', 'when active:', 'out of scope')):
                if ':' in line and len(line.split(':', 1)[1].strip()) < 5:
                    continue
            
            # Remove bullet markers
            line = re.sub(r'^[-•*]\s*', '', line)
            line = re.sub(r'^\d+[.)]\s*', '', line)
            
            if len(line) > 10:
                bullets.append(line)
        
        return bullets
    
    def _ac_to_qa_bullet(self, ac_text: str, evidence: EvidenceModel) -> Optional[str]:
        """Convert AC to QA bullet using evidence only."""
        if not ac_text or len(ac_text) < 10:
            return None
        
        # Clean up
        text = ac_text.strip()
        text = re.sub(r'^(verify|ensure|check)\s+that\s+', '', text, flags=re.IGNORECASE)
        text = text[0].upper() + text[1:] if len(text) > 1 else text
        
        # Limit length
        if len(text) > 90:
            words = text[:90].split()
            text = ' '.join(words[:-1])
        
        # Check for forbidden assumptive language
        text_lower = text.lower()
        for forbidden in self.forbidden_assumptive:
            if forbidden in text_lower:
                return None
        
        return text
    
    def _extract_theme(self, bullet: str) -> str:
        """Extract theme key for deduplication."""
        words = re.findall(r'\b\w+\b', bullet.lower())
        key_words = [
            w for w in words
            if w not in ['the', 'a', 'an', 'and', 'or', 'from', 'in', 'on']
        ]
        return ' '.join(key_words[:4])
    
    def _build_dependencies(
        self,
        story: UserStory,
        test_cases: List[TestCase],
        evidence: EvidenceModel
    ) -> List[str]:
        """Build dependencies list from evidence."""
        deps = []
        text = f"{evidence.description_text} {evidence.ac_text}".lower()
        
        if 'undo' in text or 'redo' in text:
            deps.append("Undo/Redo")
        if 'select' in text and 'selected' in text:
            deps.append("object selection")
        if 'canvas' in text:
            deps.append("canvas rendering")
        if 'menu' in text:
            deps.append("menu navigation")
        if 'dialog' in text or 'window' in text:
            deps.append("dialog rendering")
        
        if not deps:
            deps.append("core application components")
        
        return deps
    
    def _build_accessibility_clause(self, test_cases: List[TestCase]) -> str:
        """Build accessibility clause (always included)."""
        return (
            "Accessibility testing will validate compliance with Section 508 / WCAG 2.1 AA standards, "
            "including keyboard operability, visible focus indicators, and readable labels and control roles "
            "to ensure the feature is usable with assistive technologies."
        )
    
    def _build_platform_clause(self, test_cases: List[TestCase]) -> str:
        """Build platform clause."""
        return (
            "Tests will be executed on Windows 11 and tablet devices (iOS iPad and Android Tablet) "
            "to validate consistent behavior across mouse-based and touch-based interaction models."
        )
    
    def _render_summary(self, plan: SummaryPlan) -> str:
        """Render summary from plan."""
        bullets_text = '\n'.join(f"• {b}" for b in plan.bullet_themes)
        
        # Format dependencies
        if len(plan.dependencies) == 1:
            deps_text = plan.dependencies[0]
        elif len(plan.dependencies) == 2:
            deps_text = f"{plan.dependencies[0]} and {plan.dependencies[1]}"
        else:
            deps_text = ', '.join(plan.dependencies[:-1]) + f", and {plan.dependencies[-1]}"
        
        summary = f"""{plan.intro_facts}

Testing will focus on verifying:
{bullets_text}

Functional dependencies include {deps_text}, all of which must operate correctly to ensure proper feature behavior.

{plan.accessibility_clause}

{plan.platform_clause}"""
        
        return summary
    
    def _rewrite_with_llm(
        self,
        deterministic_text: str,
        plan: SummaryPlan,
        evidence: EvidenceModel
    ) -> Optional[str]:
        """Rewrite summary with LLM."""
        if not self.llm_provider:
            return None
        
        # Build prompt
        prompt = self._build_rewrite_prompt(deterministic_text, plan, evidence)
        
        if self.debug:
            print("[DEBUG] Sending to LLM for rewriting...")
        
        # Get LLM rewrite
        rewritten = self.llm_provider.rewrite_text(
            prompt=prompt,
            temperature=0.3,
            max_tokens=500
        )
        
        if not rewritten:
            if self.debug:
                print("[DEBUG] LLM returned no output")
            return None
        
        if self.debug:
            print(f"[DEBUG] LLM returned {len(rewritten)} chars")
        
        return rewritten
    
    def _build_rewrite_prompt(
        self,
        deterministic_text: str,
        plan: SummaryPlan,
        evidence: EvidenceModel
    ) -> str:
        """Build prompt for LLM rewriting."""
        prompt = f"""You are rewriting a QA Planning Summary to make it less dry and more natural.

STRICT RULES:
1. Rewrite WORDING ONLY - do not add new claims, features, or behaviors
2. All facts must come from the evidence provided (Description, Acceptance Criteria)
3. Do not invent UI surfaces, entry points, or behaviors
4. Do not use speculative words: assumingly, generally, presumably, probably
5. Keep the exact same structure and bullet count
6. Make it sound more natural and professional, not robotic

EVIDENCE (Description + AC):
{evidence.description_text[:200]}...
{evidence.ac_text[:300]}...

DETERMINISTIC SUMMARY TO REWRITE:
{deterministic_text}

Rewrite the summary following the rules above. Output ONLY the rewritten summary, no explanations:
"""
        return prompt
