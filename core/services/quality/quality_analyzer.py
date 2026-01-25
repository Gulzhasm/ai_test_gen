"""
Test Quality Analyzer - Evaluates test case quality against standards.

Domain-agnostic quality analysis using pattern matching and heuristics.
"""
import re
from typing import List, Dict, Optional

from core.interfaces.quality_standards import (
    IQualityAnalyzer,
    TestCaseQualityMetrics,
    StepQualityMetrics,
    QualityIssue,
    GENERIC_PHRASES,
    HIGH_QUALITY_PATTERNS,
    QUALITY_THRESHOLDS,
)


class TestQualityAnalyzer(IQualityAnalyzer):
    """Analyzes test case quality using pattern-based heuristics."""

    def __init__(self):
        """Initialize quality analyzer."""
        # Compile regex patterns for efficiency
        self._generic_patterns = [
            re.compile(re.escape(phrase), re.IGNORECASE)
            for phrase in GENERIC_PHRASES
        ]
        self._action_verb_pattern = re.compile(
            r'\b(' + '|'.join(HIGH_QUALITY_PATTERNS['action_verbs']) + r')\b',
            re.IGNORECASE
        )
        self._object_pattern = re.compile(
            r'\b(' + '|'.join(HIGH_QUALITY_PATTERNS['specific_objects']) + r')\b',
            re.IGNORECASE
        )
        self._outcome_pattern = re.compile(
            r'\b(' + '|'.join(HIGH_QUALITY_PATTERNS['observable_outcomes']) + r')\b',
            re.IGNORECASE
        )

    def analyze_test_case(self, test_case: Dict) -> TestCaseQualityMetrics:
        """Analyze quality of a complete test case."""
        # Analyze title first
        title = test_case.get('title', '')
        title_quality = self._analyze_title(title)

        metrics = TestCaseQualityMetrics(title_quality=title_quality)

        # Analyze steps
        steps = test_case.get('steps', [])
        for step in steps:
            action = step.get('action', '')
            expected = step.get('expected', '')
            step_metrics = self.analyze_step(action, expected)
            metrics.step_metrics.append(step_metrics)

            # Check for structural elements
            action_lower = action.lower()
            if 'pre-req' in action_lower or 'prerequisite' in action_lower:
                metrics.has_prereq = True
            if 'launch' in action_lower or 'open' in action_lower and 'application' in action_lower:
                metrics.has_launch = True
            if 'close' in action_lower and ('app' in action_lower or 'application' in action_lower):
                metrics.has_close = True
            if 'verify' in action_lower or 'confirm' in action_lower or 'check' in action_lower:
                metrics.has_verification_steps = True

        # Analyze objective
        objective = test_case.get('objective', '')
        metrics.objective_quality = self._analyze_objective(objective)

        # Collect issues
        metrics.issues = [issue.description for issue in self.find_issues(test_case)]

        return metrics

    def analyze_step(self, action: str, expected: str) -> StepQualityMetrics:
        """Analyze quality of a single test step."""
        metrics = StepQualityMetrics(
            action_specificity=0.0,
            expected_observability=0.0,
            has_generic_phrases=False,
            action_length=len(action),
            expected_length=len(expected),
        )

        # Check for generic phrases
        for pattern in self._generic_patterns:
            if pattern.search(action) or pattern.search(expected):
                metrics.has_generic_phrases = True
                metrics.issues.append(f"Contains generic phrase")
                break

        # Calculate action specificity
        metrics.action_specificity = self._calculate_action_specificity(action)

        # Calculate expected observability
        metrics.expected_observability = self._calculate_expected_observability(expected)

        # Additional issue checks
        if len(action) < QUALITY_THRESHOLDS['min_action_length']:
            metrics.issues.append("Action too short")
        if expected and len(expected) < QUALITY_THRESHOLDS['min_expected_length']:
            metrics.issues.append("Expected result too short")

        return metrics

    def find_issues(self, test_case: Dict) -> List[QualityIssue]:
        """Find quality issues in a test case."""
        issues = []

        # Check title
        title = test_case.get('title', '')
        if not title:
            issues.append(QualityIssue(
                severity="critical",
                location="title",
                description="Missing test case title",
                suggestion="Add a descriptive title following pattern: ID: Feature / Location / Description"
            ))
        elif '/' not in title:
            issues.append(QualityIssue(
                severity="major",
                location="title",
                description="Title does not follow standard format",
                suggestion="Use format: ID: Feature / Location / Description"
            ))

        # Check steps
        steps = test_case.get('steps', [])
        if len(steps) < QUALITY_THRESHOLDS['min_total_steps']:
            issues.append(QualityIssue(
                severity="major",
                location="steps",
                description=f"Too few steps ({len(steps)})",
                suggestion=f"Add at least {QUALITY_THRESHOLDS['min_total_steps']} steps"
            ))

        verification_count = 0
        for idx, step in enumerate(steps):
            action = step.get('action', '')
            expected = step.get('expected', '')

            # Check for generic actions
            for pattern in self._generic_patterns:
                if pattern.search(action):
                    issues.append(QualityIssue(
                        severity="major",
                        location=f"step_{idx+1}_action",
                        description=f"Generic action: '{action[:50]}...'",
                        suggestion="Replace with specific, actionable instruction"
                    ))
                    break

            # Check for generic expected results
            if expected:
                for pattern in self._generic_patterns:
                    if pattern.search(expected):
                        issues.append(QualityIssue(
                            severity="major",
                            location=f"step_{idx+1}_expected",
                            description=f"Generic expected result: '{expected[:50]}...'",
                            suggestion="Replace with specific, observable outcome"
                        ))
                        break

            # Count verification steps
            if 'verify' in action.lower() or 'confirm' in action.lower():
                verification_count += 1

        if verification_count < QUALITY_THRESHOLDS['min_verification_steps']:
            issues.append(QualityIssue(
                severity="major",
                location="steps",
                description="No verification steps found",
                suggestion="Add steps that verify expected behavior"
            ))

        # Check objective
        objective = test_case.get('objective', '')
        if not objective:
            issues.append(QualityIssue(
                severity="minor",
                location="objective",
                description="Missing test objective",
                suggestion="Add a clear objective describing what the test verifies"
            ))

        return issues

    def _analyze_title(self, title: str) -> float:
        """Analyze title quality (0-1)."""
        if not title:
            return 0.0

        score = 0.0

        # Check for ID pattern (e.g., "12345-AC1:" or "12345-005:")
        if re.search(r'^\d+-[A-Z0-9]+:', title):
            score += 0.3

        # Check for path separator pattern (Feature / Location / Description)
        path_parts = title.split('/')
        if len(path_parts) >= 3:
            score += 0.4
        elif len(path_parts) >= 2:
            score += 0.2

        # Check for meaningful content length
        if len(title) >= 30:
            score += 0.2
        elif len(title) >= 20:
            score += 0.1

        # Bonus for descriptive ending
        if path_parts:
            last_part = path_parts[-1].strip()
            if len(last_part) > 10 and not last_part.lower().startswith('test'):
                score += 0.1

        return min(1.0, score)

    def _analyze_objective(self, objective: str) -> float:
        """Analyze objective quality (0-1)."""
        if not objective:
            return 0.0

        score = 0.0

        # Check for "Verify that" pattern
        if objective.lower().startswith('verify') or '<b>' in objective:
            score += 0.3

        # Check for specific terms
        if self._action_verb_pattern.search(objective):
            score += 0.2
        if self._object_pattern.search(objective):
            score += 0.2

        # Length check
        if len(objective) >= 50:
            score += 0.2
        elif len(objective) >= 30:
            score += 0.1

        # Penalize generic objectives
        for pattern in self._generic_patterns:
            if pattern.search(objective):
                score -= 0.2
                break

        return max(0.0, min(1.0, score))

    def _calculate_action_specificity(self, action: str) -> float:
        """Calculate how specific an action is (0-1)."""
        if not action:
            return 0.0

        score = 0.0
        action_lower = action.lower()

        # Check for action verbs
        verb_matches = self._action_verb_pattern.findall(action)
        if verb_matches:
            score += 0.3 * min(1.0, len(verb_matches) / 2)

        # Check for specific objects
        object_matches = self._object_pattern.findall(action)
        if object_matches:
            score += 0.3 * min(1.0, len(object_matches) / 2)

        # Check for examples or specific values
        if '(e.g.' in action or 'such as' in action_lower:
            score += 0.1
        if re.search(r'\d+', action):  # Contains numbers
            score += 0.1
        if '"' in action or "'" in action:  # Contains quoted text
            score += 0.1

        # Length bonus (but not too short or too long)
        if QUALITY_THRESHOLDS['min_action_length'] <= len(action) <= QUALITY_THRESHOLDS['max_action_length']:
            score += 0.2

        # Penalty for generic phrases
        for pattern in self._generic_patterns:
            if pattern.search(action):
                score -= 0.3
                break

        return max(0.0, min(1.0, score))

    def _calculate_expected_observability(self, expected: str) -> float:
        """Calculate how observable an expected result is (0-1)."""
        if not expected:
            return 0.0  # Empty expected results for setup steps are OK

        score = 0.0

        # Check for observable outcome phrases
        outcome_matches = self._outcome_pattern.findall(expected)
        if outcome_matches:
            score += 0.4 * min(1.0, len(outcome_matches) / 2)

        # Check for specific objects
        object_matches = self._object_pattern.findall(expected)
        if object_matches:
            score += 0.3 * min(1.0, len(object_matches) / 2)

        # Check for specific values or examples
        if re.search(r'\d+', expected):  # Contains numbers
            score += 0.1
        if '"' in expected or "'" in expected:  # Contains quoted text
            score += 0.1

        # Length bonus
        if len(expected) >= QUALITY_THRESHOLDS['min_expected_length']:
            score += 0.1

        # Penalty for generic phrases
        for pattern in self._generic_patterns:
            if pattern.search(expected):
                score -= 0.4
                break

        return max(0.0, min(1.0, score))


def get_quality_analyzer() -> TestQualityAnalyzer:
    """Get singleton quality analyzer instance."""
    if not hasattr(get_quality_analyzer, '_instance'):
        get_quality_analyzer._instance = TestQualityAnalyzer()
    return get_quality_analyzer._instance
