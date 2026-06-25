from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

GRADE_ORDER = ["F", "D", "C-", "C", "C+", "B-", "B", "B+", "A-", "A"]

DEFAULT_DATASET = (
    Path(__file__).resolve().parents[2] / "tests" / "benchmarks" / "assessment_cases.json"
)

Scorer = Callable[[dict[str, Any]], dict[str, Any]]


def load_dataset(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path else DEFAULT_DATASET
    return json.loads(p.read_text(encoding="utf-8"))


def _matches_from_case(case: dict[str, Any]) -> list:
    from app.services.evidence_matcher import MatchedChunk

    out: list = []
    for i, ev in enumerate(case.get("evidence") or []):
        out.append(
            MatchedChunk(
                evidence_id=None,
                file_name=ev.get("file_name", ""),
                chunk_index=i,
                quote=ev.get("quote", ""),
                confidence=float(ev.get("confidence", 0.0)),
                missing_note=ev.get("missing_note"),
            )
        )
    if not out:
        out.append(
            MatchedChunk(
                evidence_id=None,
                file_name="",
                chunk_index=0,
                quote="",
                confidence=0.0,
                missing_note="No evidence uploaded.",
            )
        )
    return out


def live_scorer(case: dict[str, Any]) -> dict[str, Any]:
    from app.services.assessment_draft_core import _llm_assess_criterion

    matches = _matches_from_case(case)
    return _llm_assess_criterion(
        case["criterion"],
        matches,
        case.get("rubric_excerpt", ""),
        case.get("recording_text", ""),
    )


def _grade_for(score: float, max_score: float = 10) -> str:
    from app.services.assessment_draft_core import _score_to_grade

    return _score_to_grade(score, max_score)


def _grade_distance(predicted: str, gold: str) -> Optional[int]:
    if predicted not in GRADE_ORDER or gold not in GRADE_ORDER:
        return None
    return abs(GRADE_ORDER.index(predicted) - GRADE_ORDER.index(gold))


@dataclass
class CaseResult:
    case_id: str
    tier: str
    gold_score: float
    gold_grade: str
    pred_scores: list[float]
    pred_grade: str
    mean_pred: float
    abs_error: float
    grade_distance: Optional[int]
    run_stdev: float
    comment: str = ""


def evaluate(
    scorer: Scorer,
    dataset: dict[str, Any] | str | Path | None = None,
    runs: int = 1,
    grade_fn: Callable[[float, float], str] | None = None,
) -> dict[str, Any]:
    data = dataset if isinstance(dataset, dict) else load_dataset(dataset)
    tol = float(data.get("score_tolerance", 1.5))
    grader = grade_fn or _grade_for
    results: list[CaseResult] = []

    for case in data["cases"]:
        max_score = float(case["criterion"].get("max_score", 10))
        preds: list[float] = []
        last_comment = ""
        for _ in range(max(1, runs)):
            out = scorer(case)
            preds.append(float(out["score"]))
            last_comment = str(out.get("comment") or "")
        mean_pred = statistics.fmean(preds)
        pred_grade = grader(mean_pred, max_score)
        gold = float(case["gold_score"])
        results.append(
            CaseResult(
                case_id=case["id"],
                tier=case.get("tier", ""),
                gold_score=gold,
                gold_grade=case["gold_grade"],
                pred_scores=[round(p, 2) for p in preds],
                pred_grade=pred_grade,
                mean_pred=round(mean_pred, 2),
                abs_error=round(abs(mean_pred - gold), 2),
                grade_distance=_grade_distance(pred_grade, case["gold_grade"]),
                run_stdev=round(statistics.pstdev(preds), 3) if len(preds) > 1 else 0.0,
                comment=last_comment[:200],
            )
        )

    return {"summary": _summarise(results, tol), "cases": [r.__dict__ for r in results]}


def _summarise(results: list[CaseResult], tol: float) -> dict[str, Any]:
    n = len(results)
    if not n:
        return {"n": 0}
    errs = [r.abs_error for r in results]
    exact = sum(1 for r in results if r.grade_distance == 0)
    within_band = sum(
        1 for r in results if r.grade_distance is not None and r.grade_distance <= 1
    )
    within_tol = sum(1 for r in results if r.abs_error <= tol)
    stdevs = [r.run_stdev for r in results]
    by_tier: dict[str, list[float]] = {}
    for r in results:
        by_tier.setdefault(r.tier, []).append(r.abs_error)
    return {
        "n": n,
        "score_mae": round(statistics.fmean(errs), 3),
        "score_rmse": round(statistics.fmean([e * e for e in errs]) ** 0.5, 3),
        "grade_exact_pct": round(100 * exact / n, 1),
        "grade_within_one_band_pct": round(100 * within_band / n, 1),
        "within_tolerance_pct": round(100 * within_tol / n, 1),
        "mean_run_stdev": round(statistics.fmean(stdevs), 3),
        "max_run_stdev": round(max(stdevs), 3),
        "tolerance": tol,
        "mae_by_tier": {k: round(statistics.fmean(v), 3) for k, v in sorted(by_tier.items())},
    }


def format_report(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "Assessment scoring benchmark",
        "=" * 32,
        f"cases:                 {s.get('n')}",
        f"score MAE:             {s.get('score_mae')}",
        f"score RMSE:            {s.get('score_rmse')}",
        f"within tolerance:      {s.get('within_tolerance_pct')}%",
        f"grade exact match:     {s.get('grade_exact_pct')}%",
        f"grade within 1 band:   {s.get('grade_within_one_band_pct')}%",
        f"mean run stdev:        {s.get('mean_run_stdev')}",
        f"max run stdev:         {s.get('max_run_stdev')}",
        f"MAE by tier:           {s.get('mae_by_tier')}",
        "",
        f"{'case':<32}{'gold':>6}{'pred':>7}{'err':>6}{'stdev':>7}  grade",
        "-" * 72,
    ]
    for c in report["cases"]:
        lines.append(
            f"{c['case_id']:<32}{c['gold_score']:>6}{c['mean_pred']:>7}"
            f"{c['abs_error']:>6}{c['run_stdev']:>7}  "
            f"{c['gold_grade']}->{c['pred_grade']}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the assessment scoring benchmark.")
    parser.add_argument("--live", action="store_true", help="Score via the real Ollama pipeline.")
    parser.add_argument("--runs", type=int, default=1, help="Runs per case (for consistency).")
    parser.add_argument("--dataset", default=None, help="Path to a benchmark JSON file.")
    parser.add_argument("--json-out", default=None, help="Write the full report JSON here.")
    args = parser.parse_args(argv)

    if not args.live:
        print("Refusing to run without --live (mock runs belong in the test suite).")
        return 2

    report = evaluate(live_scorer, dataset=args.dataset, runs=args.runs)
    print(format_report(report))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nWrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
