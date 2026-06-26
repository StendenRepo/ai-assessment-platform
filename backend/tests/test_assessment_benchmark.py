from __future__ import annotations

import pytest

from app.eval import benchmark
from app.services.assessment_draft_core import _score_to_grade


@pytest.fixture(scope="module")
def dataset():
    return benchmark.load_dataset()


def test_dataset_is_non_trivial(dataset):
    cases = dataset["cases"]
    assert len(cases) >= 15
    tiers = {c.get("tier") for c in cases}
    assert {"strong", "partial", "weak"} <= tiers


def test_case_ids_are_unique(dataset):
    ids = [c["id"] for c in dataset["cases"]]
    assert len(ids) == len(set(ids))


def test_gold_grades_match_band_function(dataset):
    for c in dataset["cases"]:
        max_score = float(c["criterion"].get("max_score", 10))
        assert c["gold_grade"] == _score_to_grade(float(c["gold_score"]), max_score), c["id"]


def test_perfect_scorer_is_flawless(dataset):
    report = benchmark.evaluate(lambda c: {"score": c["gold_score"]}, dataset=dataset)
    s = report["summary"]
    assert s["score_mae"] == 0.0
    assert s["grade_exact_pct"] == 100.0
    assert s["within_tolerance_pct"] == 100.0


def test_constant_offset_scorer_reports_that_offset(dataset):
    report = benchmark.evaluate(
        lambda c: {"score": min(10, c["gold_score"] + 2)}, dataset=dataset
    )
    assert report["summary"]["score_mae"] > 0.0
    assert report["summary"]["score_mae"] <= 2.0


def test_consistency_metric_detects_variance(dataset):
    state = {"n": 0}

    def jittery(case):
        state["n"] += 1
        bump = 1.0 if state["n"] % 2 else -1.0
        return {"score": max(0, min(10, case["gold_score"] + bump))}

    report = benchmark.evaluate(jittery, dataset=dataset, runs=4)
    assert report["summary"]["mean_run_stdev"] > 0.0


def test_grade_distance_ordering():
    assert benchmark._grade_distance("A", "A") == 0
    assert benchmark._grade_distance("A", "A-") == 1
    assert benchmark._grade_distance("F", "A") == len(benchmark.GRADE_ORDER) - 1


def test_live_adapter_builds_matches_with_missing_note(dataset):
    no_evidence = next(c for c in dataset["cases"] if not c["evidence"][0]["quote"])
    matches = benchmark._matches_from_case(no_evidence)
    assert matches
    assert matches[0].missing_note
    assert matches[0].quote == ""
