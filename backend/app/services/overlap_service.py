import itertools
import re
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models.evidence import Evidence
from app.models.enums import OverlapType
from app.models.overlap_signal import OverlapSignal
from app.models.project import Project
from app.models.student import Student, student_projects

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_MAX_SIGNALS_PER_RUN = 100


def _normalize_filename(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _filename_tokens(value: str) -> set[str]:
    return set(_TOKEN_RE.findall(_normalize_filename(value)))


def _token_similarity(name_a: str, name_b: str) -> float:
    tokens_a = _filename_tokens(name_a)
    tokens_b = _filename_tokens(name_b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union else 0.0


def _ordered_pair(a, b):
    return (a, b) if str(a) < str(b) else (b, a)


def _render_signal_line(signal: OverlapSignal) -> str:
    return (
        f"- confidence={signal.confidence:.2f}; type={signal.overlap_type.value}; "
        f"reason={signal.snippet or 'Possible overlap detected'}"
    )


class OverlapService:
    @staticmethod
    def analyze_module_overlap(db: Session, module_id: str) -> List[OverlapSignal]:
        students = (
            db.query(Student)
            .join(student_projects, Student.student_number == student_projects.c.student_id)
            .join(Project, student_projects.c.project_id == Project.id)
            .filter(Project.module_id == module_id)
            .all()
        )
        if not students:
            return []

        student_ids = [s.student_number for s in students]
        evidence_items = db.query(Evidence).filter(Evidence.student_id.in_(student_ids)).all()
        if not evidence_items:
            OverlapService._clear_module_signals(db, student_ids)
            db.commit()
            return []

        by_name: Dict[str, List[Evidence]] = defaultdict(list)
        for evidence in evidence_items:
            normalized = _normalize_filename(evidence.file_name)
            if normalized:
                by_name[normalized].append(evidence)

        created: List[OverlapSignal] = []
        seen_pairs: set[Tuple[str, str, str, str]] = set()

        for normalized_name, entries in by_name.items():
            if len(entries) < 2:
                continue
            for ev_a, ev_b in itertools.combinations(entries, 2):
                if ev_a.student_id == ev_b.student_id:
                    continue

                student_a_id, student_b_id = _ordered_pair(ev_a.student_id, ev_b.student_id)
                evidence_a_id, evidence_b_id = _ordered_pair(ev_a.id, ev_b.id)
                dedupe_key = (
                    str(student_a_id),
                    str(student_b_id),
                    str(evidence_a_id),
                    str(evidence_b_id),
                )
                if dedupe_key in seen_pairs:
                    continue
                seen_pairs.add(dedupe_key)

                confidence = 0.95
                overlap_type = OverlapType.textual

                snippet = f"Shared or very similar file name: '{normalized_name}'"
                created.append(
                    OverlapSignal(
                        student_a_id=student_a_id,
                        student_b_id=student_b_id,
                        evidence_a_id=evidence_a_id,
                        evidence_b_id=evidence_b_id,
                        overlap_type=overlap_type,
                        confidence=confidence,
                        snippet=snippet,
                    )
                )
                if len(created) >= _MAX_SIGNALS_PER_RUN:
                    break
            if len(created) >= _MAX_SIGNALS_PER_RUN:
                break

        # Secondary semantic pass for near matches that do not have exact names.
        if len(created) < _MAX_SIGNALS_PER_RUN:
            for ev_a, ev_b in itertools.combinations(evidence_items, 2):
                if ev_a.student_id == ev_b.student_id:
                    continue
                if _normalize_filename(ev_a.file_name) == _normalize_filename(ev_b.file_name):
                    continue

                similarity = _token_similarity(ev_a.file_name, ev_b.file_name)
                if similarity < 0.6:
                    continue

                student_a_id, student_b_id = _ordered_pair(ev_a.student_id, ev_b.student_id)
                evidence_a_id, evidence_b_id = _ordered_pair(ev_a.id, ev_b.id)
                dedupe_key = (
                    str(student_a_id),
                    str(student_b_id),
                    str(evidence_a_id),
                    str(evidence_b_id),
                )
                if dedupe_key in seen_pairs:
                    continue
                seen_pairs.add(dedupe_key)

                created.append(
                    OverlapSignal(
                        student_a_id=student_a_id,
                        student_b_id=student_b_id,
                        evidence_a_id=evidence_a_id,
                        evidence_b_id=evidence_b_id,
                        overlap_type=OverlapType.semantic,
                        confidence=round(max(0.6, min(0.9, similarity)), 2),
                        snippet=(
                            "Similar file names suggest overlap: "
                            f"'{ev_a.file_name}' and '{ev_b.file_name}'"
                        ),
                    )
                )
                if len(created) >= _MAX_SIGNALS_PER_RUN:
                    break

        OverlapService._clear_module_signals(db, student_ids)
        for signal in created:
            db.add(signal)
        db.commit()
        for signal in created:
            db.refresh(signal)
        return created

    @staticmethod
    def get_module_signals(db: Session, module_id: str) -> List[OverlapSignal]:
        return (
            db.query(OverlapSignal)
            .join(Student, OverlapSignal.student_a_id == Student.student_number)
            .join(student_projects, Student.student_number == student_projects.c.student_id)
            .join(Project, student_projects.c.project_id == Project.id)
            .filter(Project.module_id == module_id)
            .order_by(OverlapSignal.confidence.desc(), OverlapSignal.detected_at.desc())
            .all()
        )

    @staticmethod
    def build_warning(signals: Iterable[OverlapSignal]) -> Dict[str, object]:
        items = list(signals)
        high_risk_count = sum(1 for s in items if (s.confidence or 0) >= 0.8)
        has_overlap = len(items) > 0

        if not has_overlap:
            return {
                "has_overlap": False,
                "high_risk_count": 0,
                "signal_count": 0,
                "warning": "No overlap has been detected for this module.",
            }

        prompt_lines = [
            "You are an assessment assistant.",
            "Write a short warning for a teacher if overlap was detected between student submissions.",
            "Keep it under 80 words and mention reviewing evidence manually.",
            "Detected overlap signals:",
        ]
        for signal in items[:8]:
            prompt_lines.append(_render_signal_line(signal))

        model_warning = OverlapService._generate_ollama_warning("\n".join(prompt_lines))
        warning = model_warning or (
            "Potential overlap was detected between student submissions. "
            "Please review the matching evidence before finalizing assessment decisions."
        )

        return {
            "has_overlap": True,
            "high_risk_count": high_risk_count,
            "signal_count": len(items),
            "warning": warning,
        }

    @staticmethod
    def _clear_module_signals(db: Session, student_ids: List[object]) -> None:
        if not student_ids:
            return
        (
            db.query(OverlapSignal)
            .filter(
                OverlapSignal.student_a_id.in_(student_ids),
                OverlapSignal.student_b_id.in_(student_ids),
            )
            .delete(synchronize_session=False)
        )

    @staticmethod
    def _generate_ollama_warning(prompt: str) -> Optional[str]:
        for model in [settings.OLLAMA_MODEL, settings.OLLAMA_MODEL_BACKUP]:
            if not model:
                continue
            try:
                with httpx.Client(timeout=settings.OLLAMA_TIMEOUT_SECONDS) as client:
                    response = client.post(
                        f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate",
                        json={"model": model, "prompt": prompt, "stream": False},
                    )
                    response.raise_for_status()
                    payload = response.json()
                    text = (payload.get("response") or "").strip()
                    if text:
                        return text
            except Exception:
                continue
        return None
