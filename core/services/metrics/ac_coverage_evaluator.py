"""
AC-coverage evaluation: precision / recall / F1 for AI-generated test cases
against a human-authored ground-truth labeling.

The baseline a human authors is light: the story's acceptance criteria (which
already exist) plus, for each ALREADY-GENERATED test case, the AC id(s) it
actually covers (`covers: []` marks a spurious / hallucinated test).

Metrics (per story, then aggregated):
- AC Recall (completeness)   = |in-scope ACs covered by >=1 valid test| / |in-scope ACs|
- Test Precision (signal)    = |tests mapping to >=1 in-scope AC| / |total generated tests|
- F1                         = harmonic mean of the two

This module is pure logic (no I/O) so it is fully unit-testable.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Set


@dataclass
class ACItem:
    id: str
    text: str = ""
    in_scope: bool = True


@dataclass
class TestLabel:
    test_id: str
    title: str = ""
    covers: List[str] = field(default_factory=list)   # AC ids this test actually covers


@dataclass
class StoryBaseline:
    story_id: str
    acceptance_criteria: List[ACItem] = field(default_factory=list)
    test_labels: List[TestLabel] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict) -> "StoryBaseline":
        acs = [
            ACItem(id=str(a["id"]), text=a.get("text", ""), in_scope=a.get("in_scope", True))
            for a in d.get("acceptance_criteria", [])
        ]
        labels = [
            TestLabel(
                test_id=str(t["test_id"]),
                title=t.get("title", ""),
                covers=[str(c) for c in (t.get("covers") or [])],
            )
            for t in d.get("test_labels", [])
        ]
        return cls(story_id=str(d.get("story_id", "")), acceptance_criteria=acs, test_labels=labels)


@dataclass
class StoryMetrics:
    story_id: str
    total_acs: int
    in_scope_acs: int
    covered_acs: int
    total_tests: int
    valid_tests: int
    recall: float
    precision: float
    f1: float
    uncovered_acs: List[str] = field(default_factory=list)
    spurious_tests: List[str] = field(default_factory=list)
    unknown_ac_refs: List[str] = field(default_factory=list)   # covers referencing a non-existent AC id

    @property
    def redundancy(self) -> float:
        """Avg valid tests per covered AC (>1 => multiple tests per AC)."""
        return (self.valid_tests / self.covered_acs) if self.covered_acs else 0.0


def _f1(precision: float, recall: float) -> float:
    return (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0


def evaluate_story(baseline: StoryBaseline) -> StoryMetrics:
    in_scope_ids: Set[str] = {ac.id for ac in baseline.acceptance_criteria if ac.in_scope}
    all_ids: Set[str] = {ac.id for ac in baseline.acceptance_criteria}

    covered: Set[str] = set()
    valid_tests = 0
    spurious: List[str] = []
    unknown_refs: Set[str] = set()

    for t in baseline.test_labels:
        covered_in_scope = [c for c in t.covers if c in in_scope_ids]
        for c in t.covers:
            if c not in all_ids:
                unknown_refs.add(c)
        if covered_in_scope:
            valid_tests += 1
            covered.update(covered_in_scope)
        else:
            spurious.append(t.test_id)

    total_tests = len(baseline.test_labels)
    recall = (len(covered) / len(in_scope_ids)) if in_scope_ids else 0.0
    precision = (valid_tests / total_tests) if total_tests else 0.0

    return StoryMetrics(
        story_id=baseline.story_id,
        total_acs=len(all_ids),
        in_scope_acs=len(in_scope_ids),
        covered_acs=len(covered),
        total_tests=total_tests,
        valid_tests=valid_tests,
        recall=recall,
        precision=precision,
        f1=_f1(precision, recall),
        uncovered_acs=sorted(in_scope_ids - covered),
        spurious_tests=spurious,
        unknown_ac_refs=sorted(unknown_refs),
    )


@dataclass
class AggregateMetrics:
    stories: int
    # Micro: pool all ACs / tests across stories (weights by size)
    micro_recall: float
    micro_precision: float
    micro_f1: float
    # Macro: unweighted average of per-story metrics
    macro_recall: float
    macro_precision: float
    macro_f1: float
    total_in_scope_acs: int
    total_covered_acs: int
    total_tests: int
    total_valid_tests: int


def aggregate(metrics: List[StoryMetrics]) -> AggregateMetrics:
    n = len(metrics)
    if n == 0:
        return AggregateMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

    tot_in_scope = sum(m.in_scope_acs for m in metrics)
    tot_covered = sum(m.covered_acs for m in metrics)
    tot_tests = sum(m.total_tests for m in metrics)
    tot_valid = sum(m.valid_tests for m in metrics)

    micro_recall = (tot_covered / tot_in_scope) if tot_in_scope else 0.0
    micro_precision = (tot_valid / tot_tests) if tot_tests else 0.0

    macro_recall = sum(m.recall for m in metrics) / n
    macro_precision = sum(m.precision for m in metrics) / n

    return AggregateMetrics(
        stories=n,
        micro_recall=micro_recall,
        micro_precision=micro_precision,
        micro_f1=_f1(micro_precision, micro_recall),
        macro_recall=macro_recall,
        macro_precision=macro_precision,
        macro_f1=_f1(macro_precision, macro_recall),
        total_in_scope_acs=tot_in_scope,
        total_covered_acs=tot_covered,
        total_tests=tot_tests,
        total_valid_tests=tot_valid,
    )
