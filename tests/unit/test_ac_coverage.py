"""
Unit tests for the AC-coverage evaluator (precision / recall / F1).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.services.metrics.ac_coverage_evaluator import (
    StoryBaseline, evaluate_story, aggregate,
)


def _baseline():
    # 3 in-scope ACs (AC3 uncovered); 5 tests, 1 spurious.
    return StoryBaseline.from_dict({
        "story_id": "S1",
        "acceptance_criteria": [
            {"id": "AC1", "text": "a", "in_scope": True},
            {"id": "AC2", "text": "b", "in_scope": True},
            {"id": "AC3", "text": "c", "in_scope": True},
        ],
        "test_labels": [
            {"test_id": "T1", "covers": ["AC1"]},
            {"test_id": "T2", "covers": ["AC1"]},   # redundant
            {"test_id": "T3", "covers": ["AC2"]},
            {"test_id": "T4", "covers": []},        # spurious
            {"test_id": "T5", "covers": ["AC1", "AC2"]},
        ],
    })


class TestStoryMetrics:
    def test_recall_precision_f1(self):
        m = evaluate_story(_baseline())
        assert m.in_scope_acs == 3
        assert m.covered_acs == 2                  # AC1, AC2
        assert abs(m.recall - 2 / 3) < 1e-6
        assert m.valid_tests == 4                  # T1,T2,T3,T5
        assert abs(m.precision - 0.8) < 1e-6
        assert abs(m.f1 - (2 * 0.8 * (2/3) / (0.8 + 2/3))) < 1e-6
        assert m.uncovered_acs == ["AC3"]
        assert m.spurious_tests == ["T4"]

    def test_out_of_scope_ac_excluded_from_recall(self):
        bl = StoryBaseline.from_dict({
            "story_id": "S2",
            "acceptance_criteria": [
                {"id": "AC1", "in_scope": True},
                {"id": "AC2", "in_scope": False},   # excluded from denominator
            ],
            "test_labels": [{"test_id": "T1", "covers": ["AC1"]}],
        })
        m = evaluate_story(bl)
        assert m.in_scope_acs == 1
        assert m.recall == 1.0
        assert m.precision == 1.0

    def test_unknown_ac_reference_flagged_and_not_counted(self):
        bl = StoryBaseline.from_dict({
            "story_id": "S3",
            "acceptance_criteria": [{"id": "AC1", "in_scope": True}],
            "test_labels": [{"test_id": "T1", "covers": ["AC9"]}],  # AC9 doesn't exist
        })
        m = evaluate_story(bl)
        assert m.unknown_ac_refs == ["AC9"]
        assert m.valid_tests == 0          # AC9 not a real in-scope AC
        assert m.spurious_tests == ["T1"]
        assert m.recall == 0.0

    def test_redundancy(self):
        m = evaluate_story(_baseline())
        assert abs(m.redundancy - 4 / 2) < 1e-6   # 4 valid tests / 2 covered ACs


class TestAggregate:
    def test_micro_and_macro(self):
        a = evaluate_story(_baseline())
        b = evaluate_story(StoryBaseline.from_dict({
            "story_id": "S2",
            "acceptance_criteria": [{"id": "AC1", "in_scope": True}],
            "test_labels": [{"test_id": "T1", "covers": ["AC1"]}],
        }))
        agg = aggregate([a, b])
        assert agg.stories == 2
        # micro recall = (2+1) covered / (3+1) in-scope = 3/4
        assert abs(agg.micro_recall - 0.75) < 1e-6
        # macro recall = (2/3 + 1) / 2
        assert abs(agg.macro_recall - ((2/3 + 1) / 2)) < 1e-6

    def test_empty(self):
        agg = aggregate([])
        assert agg.stories == 0 and agg.micro_f1 == 0
