"""
Objective Service
Generates objectives with evidence gates and optional LLM rewriting.
"""
from typing import List, Optional
from core.domain.models import TestCase, Objective, EvidenceModel, LintResult
from core.services.linting import ObjectiveLinter
from core.services.llm.base import LLMProvider


class ObjectiveService:
    """Service for generating objectives."""
    
    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        debug: bool = False
    ):
        """Initialize objective service.
        
        Args:
            llm_provider: Optional LLM provider for rewriting
            debug: Enable debug output
        """
        self.llm_provider = llm_provider
        self.debug = debug
    
    def generate_objectives(
        self,
        test_cases: List[TestCase],
        evidence: EvidenceModel
    ) -> tuple[List[Objective], LintResult]:
        """Generate objectives for test cases.
        
        Returns:
            Tuple of (objectives, lint_result)
        """
        objectives = []
        
        for tc in test_cases:
            # Use deterministic objective from test case
            deterministic_obj = tc.objective if tc.objective else self._generate_default_objective(tc)
            
            # Create objective object
            obj = Objective(
                test_id=tc.test_id,
                title=tc.title,
                objective_text=deterministic_obj
            )
            
            # If LLM enabled, try rewriting
            if self.llm_provider and self.llm_provider.is_available():
                rewritten = self._rewrite_objective_with_llm(obj, tc, evidence)
                if rewritten:
                    # Lint rewritten version
                    temp_obj = Objective(
                        test_id=tc.test_id,
                        title=tc.title,
                        objective_text=rewritten
                    )
                    
                    linter = ObjectiveLinter(evidence)
                    lint_result = linter.lint_objective(temp_obj, tc)
                    
                    if lint_result.ok:
                        if self.debug:
                            print(f"[DEBUG] {tc.test_id}: Using LLM rewrite")
                        obj.objective_text = rewritten
                    else:
                        if self.debug:
                            print(f"[DEBUG] {tc.test_id}: LLM rewrite failed lint, using deterministic")
            
            objectives.append(obj)
        
        # Lint all objectives
        linter = ObjectiveLinter(evidence)
        lint_result = linter.lint_all(objectives, test_cases)
        
        return objectives, lint_result
    
    def _generate_default_objective(self, tc: TestCase) -> str:
        """Generate default objective from test case title."""
        # Extract scenario from title
        if ' / ' in tc.title:
            parts = tc.title.split(' / ')
            scenario = parts[-1] if len(parts) > 0 else "feature behavior"
            scenario = scenario.split('(')[0].strip().lower()
            return f"Verify that {scenario}."
        else:
            return "Verify that the feature functions correctly."
    
    def _rewrite_objective_with_llm(
        self,
        objective: Objective,
        test_case: TestCase,
        evidence: EvidenceModel
    ) -> Optional[str]:
        """Rewrite objective with LLM."""
        if not self.llm_provider:
            return None
        
        # Build prompt
        prompt = self._build_rewrite_prompt(objective, test_case, evidence)
        
        # Get LLM rewrite
        rewritten = self.llm_provider.rewrite_text(
            prompt=prompt,
            temperature=0.3,
            max_tokens=150
        )
        
        if not rewritten:
            return None
        
        # Clean up rewritten text
        rewritten = rewritten.strip()
        
        # Ensure it starts with "Verify that"
        if rewritten.lower().startswith('objective:'):
            rewritten = rewritten[10:].strip()
        if not rewritten.lower().startswith('verify that'):
            if rewritten.lower().startswith('verify '):
                rewritten = f"Verify that {rewritten[7:]}"
            else:
                rewritten = f"Verify that {rewritten}"
        
        return rewritten
    
    def _build_rewrite_prompt(
        self,
        objective: Objective,
        test_case: TestCase,
        evidence: EvidenceModel
    ) -> str:
        """Build prompt for LLM rewriting."""
        prompt = f"""You are rewriting a test objective to make it less dry and more natural.

STRICT RULES:
1. Rewrite WORDING ONLY - do not add scope beyond the test case title
2. Must start with "Verify that"
3. Must include device/tool only if in test case title
4. Do not invent new scenarios, UI surfaces, or behaviors
5. Keep it concise (1-2 sentences max)
6. Make it sound more natural and professional

TEST CASE TITLE:
{test_case.title}

DETERMINISTIC OBJECTIVE:
{objective.objective_text}

EVIDENCE SNIPPET:
{evidence.ac_text[:200]}...

Rewrite the objective following the rules above. Output ONLY the rewritten objective starting with "Verify that":
"""
        return prompt
