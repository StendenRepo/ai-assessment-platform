import itertools
import json
import re
import uuid as uuid_mod
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.services import ollama_client
from app.models.evidence import Evidence
from app.models.enums import OverlapType
from app.models.overlap_signal import OverlapSignal
from app.models.project import Project
from app.models.student import Student, student_projects
from app.services.evidence_service import EVIDENCE_UPLOAD_DIR
from app.services.overlap_text_detector import (
    EvidenceChunk,
    detect_cross_group,
    detect_within_group,
)
from app.services.text_chunker import chunk_text

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_MAX_SIGNALS_PER_RUN = 100
_SNIPPET_JSON_PREFIX = "{"


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


def parse_signal_detail(snippet: Optional[str]) -> dict:
    if not snippet or not snippet.strip().startswith(_SNIPPET_JSON_PREFIX):
        return {}
    try:
        return json.loads(snippet)
    except json.JSONDecodeError:
        return {}


def encode_text_snippet(hit: dict) -> str:
    return json.dumps(
        {
            "scope": hit.get("scope"),
            "status": hit.get("status"),
            "passage_a": hit.get("passage_a"),
            "passage_b": hit.get("passage_b"),
            "file_a": hit.get("file_a"),
            "file_b": hit.get("file_b"),
            "group_a_id": hit.get("group_a_id"),
            "group_b_id": hit.get("group_b_id"),
            "group_a_name": hit.get("group_a_name"),
            "group_b_name": hit.get("group_b_name"),
        }
    )


class OverlapService:
    @staticmethod
    def _read_evidence_text(evidence: Evidence) -> str:
        full_path = EVIDENCE_UPLOAD_DIR / evidence.file_path
        if not full_path.exists():
            return ""
        try:
            return full_path.read_text(encoding="utf-8")
        except OSError:
            return ""

    @staticmethod
    def _build_chunks_for_module(db: Session, module_id: str) -> tuple[list[EvidenceChunk], dict]:
        projects = db.query(Project).filter(Project.module_id == module_id).all()
        if not projects:
            return [], {}

        project_ids = [p.id for p in projects]
        project_by_id = {str(p.id): p for p in projects}

        rows = db.execute(
            student_projects.select().where(student_projects.c.project_id.in_(project_ids))
        ).all()
        student_to_group = {row.student_id: str(row.project_id) for row in rows}

        students = (
            db.query(Student)
            .filter(Student.student_number.in_(list(student_to_group.keys())))
            .all()
        )
        student_names = {s.student_number: s.name for s in students}

        evidence_items = (
            db.query(Evidence)
            .filter(Evidence.student_id.in_(list(student_to_group.keys())))
            .all()
        )

        chunks: list[EvidenceChunk] = []
        for evidence in evidence_items:
            text = OverlapService._read_evidence_text(evidence)
            if not text.strip():
                continue
            group_id = student_to_group.get(evidence.student_id, "")
            group = project_by_id.get(group_id)
            for idx, part in enumerate(chunk_text(text)):
                chunks.append(
                    EvidenceChunk(
                        student_id=evidence.student_id,
                        student_name=student_names.get(evidence.student_id, evidence.student_id),
                        evidence_id=str(evidence.id),
                        file_name=evidence.file_name,
                        chunk_index=idx,
                        text=part,
                        group_id=group_id,
                        group_name=group.name if group else "",
                    )
                )
        return chunks, student_to_group

    @staticmethod
    def _text_hits_for_module(db: Session, module_id: str) -> list[dict]:
        chunks, _ = OverlapService._build_chunks_for_module(db, module_id)
        if len(chunks) < 2:
            return []

        by_group: dict[str, list[EvidenceChunk]] = defaultdict(list)
        for chunk in chunks:
            if chunk.group_id:
                by_group[chunk.group_id].append(chunk)

        hits: list[dict] = []
        for group_chunks in by_group.values():
            if len(group_chunks) >= 2:
                hits.extend(detect_within_group(group_chunks))

        group_ids = list(by_group.keys())
        for i in range(len(group_ids)):
            for j in range(i + 1, len(group_ids)):
                hits.extend(
                    detect_cross_group(by_group[group_ids[i]], by_group[group_ids[j]])
                )

        hits.sort(key=lambda h: h["similarity"], reverse=True)
        return hits[:_MAX_SIGNALS_PER_RUN]

    @staticmethod
    def _filename_hits(
        evidence_items: list[Evidence],
    ) -> list[OverlapSignal]:
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
                signal = OverlapService._filename_pair_signal(
                    ev_a, ev_b, seen_pairs, confidence=0.95,
                    snippet=f"Shared or very similar file name: '{normalized_name}'",
                    overlap_type=OverlapType.textual,
                )
                if signal:
                    created.append(signal)
                if len(created) >= _MAX_SIGNALS_PER_RUN:
                    return created

        if len(created) < _MAX_SIGNALS_PER_RUN:
            for ev_a, ev_b in itertools.combinations(evidence_items, 2):
                if ev_a.student_id == ev_b.student_id:
                    continue
                if _normalize_filename(ev_a.file_name) == _normalize_filename(ev_b.file_name):
                    continue
                similarity = _token_similarity(ev_a.file_name, ev_b.file_name)
                if similarity < 0.6:
                    continue
                signal = OverlapService._filename_pair_signal(
                    ev_a,
                    ev_b,
                    seen_pairs,
                    confidence=round(max(0.6, min(0.9, similarity)), 2),
                    snippet=(
                        "Similar file names suggest overlap: "
                        f"'{ev_a.file_name}' and '{ev_b.file_name}'"
                    ),
                    overlap_type=OverlapType.semantic,
                )
                if signal:
                    created.append(signal)
                if len(created) >= _MAX_SIGNALS_PER_RUN:
                    break
        return created

    @staticmethod
    def _filename_pair_signal(
        ev_a: Evidence,
        ev_b: Evidence,
        seen_pairs: set,
        *,
        confidence: float,
        snippet: str,
        overlap_type: OverlapType,
    ) -> Optional[OverlapSignal]:
        student_a_id, student_b_id = _ordered_pair(ev_a.student_id, ev_b.student_id)
        evidence_a_id, evidence_b_id = _ordered_pair(ev_a.id, ev_b.id)
        dedupe_key = (
            str(student_a_id),
            str(student_b_id),
            str(evidence_a_id),
            str(evidence_b_id),
        )
        if dedupe_key in seen_pairs:
            return None
        seen_pairs.add(dedupe_key)
        return OverlapSignal(
            student_a_id=student_a_id,
            student_b_id=student_b_id,
            evidence_a_id=evidence_a_id,
            evidence_b_id=evidence_b_id,
            overlap_type=overlap_type,
            confidence=confidence,
            snippet=snippet,
        )

    @staticmethod
    def _text_hit_to_signal(hit: dict, seen_pairs: set) -> Optional[OverlapSignal]:
        student_a_id, student_b_id = _ordered_pair(
            hit["student_a_id"], hit["student_b_id"]
        )
        evidence_a_id, evidence_b_id = _ordered_pair(
            uuid_mod.UUID(str(hit["evidence_a_id"])),
            uuid_mod.UUID(str(hit["evidence_b_id"])),
        )
        dedupe_key = (
            str(student_a_id),
            str(student_b_id),
            str(evidence_a_id),
            str(evidence_b_id),
        )
        if dedupe_key in seen_pairs:
            return None
        seen_pairs.add(dedupe_key)
        overlap_type = (
            OverlapType.textual if hit.get("status") == "confirmed" else OverlapType.semantic
        )
        return OverlapSignal(
            student_a_id=student_a_id,
            student_b_id=student_b_id,
            evidence_a_id=evidence_a_id,
            evidence_b_id=evidence_b_id,
            overlap_type=overlap_type,
            confidence=float(hit["similarity"]),
            snippet=encode_text_snippet(hit),
        )

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

        seen_pairs: set[Tuple[str, str, str, str]] = set()
        created: List[OverlapSignal] = []

        for hit in OverlapService._text_hits_for_module(db, module_id):
            signal = OverlapService._text_hit_to_signal(hit, seen_pairs)
            if signal:
                created.append(signal)
            if len(created) >= _MAX_SIGNALS_PER_RUN:
                break

        if len(created) < _MAX_SIGNALS_PER_RUN:
            for signal in OverlapService._filename_hits(evidence_items):
                key = (
                    str(signal.student_a_id),
                    str(signal.student_b_id),
                    str(signal.evidence_a_id),
                    str(signal.evidence_b_id),
                )
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                created.append(signal)
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
    def get_module_signals(
        db: Session,
        module_id: str,
        *,
        status: Optional[str] = None,
        scope: Optional[str] = None,
        group_id: Optional[str] = None,
    ) -> List[OverlapSignal]:
        signals = (
            db.query(OverlapSignal)
            .join(Student, OverlapSignal.student_a_id == Student.student_number)
            .join(student_projects, Student.student_number == student_projects.c.student_id)
            .join(Project, student_projects.c.project_id == Project.id)
            .filter(Project.module_id == module_id)
            .order_by(OverlapSignal.confidence.desc(), OverlapSignal.detected_at.desc())
            .all()
        )
        return OverlapService._filter_signals(signals, status=status, scope=scope, group_id=group_id)

    @staticmethod
    def get_signal(db: Session, module_id: str, signal_id: str) -> Optional[OverlapSignal]:
        students = (
            db.query(Student)
            .join(student_projects, Student.student_number == student_projects.c.student_id)
            .join(Project, student_projects.c.project_id == Project.id)
            .filter(Project.module_id == module_id)
            .all()
        )
        if not students:
            return None
        student_ids = [s.student_number for s in students]
        return (
            db.query(OverlapSignal)
            .filter(
                OverlapSignal.id == signal_id,
                OverlapSignal.student_a_id.in_(student_ids),
                OverlapSignal.student_b_id.in_(student_ids),
            )
            .first()
        )

    @staticmethod
    def get_signals_for_student(
        db: Session, module_id: str, student_id: str
    ) -> List[OverlapSignal]:
        """Return overlap signals involving a specific student, highest confidence first."""
        signals = OverlapService.get_module_signals(db, module_id)
        return [
            s
            for s in signals
            if s.student_a_id == student_id or s.student_b_id == student_id
        ]

    @staticmethod
    def _filter_signals(
        signals: Iterable[OverlapSignal],
        *,
        status: Optional[str],
        scope: Optional[str],
        group_id: Optional[str],
    ) -> List[OverlapSignal]:
        rows = list(signals)
        if not status and not scope and not group_id:
            return rows

        filtered: List[OverlapSignal] = []
        for signal in rows:
            detail = parse_signal_detail(signal.snippet)
            row_status = detail.get("status")
            if not row_status:
                row_status = "confirmed" if (signal.confidence or 0) >= 0.55 else "possible"
            row_scope = detail.get("scope") or "within_group"

            if status and row_status != status:
                continue
            if scope and row_scope != scope:
                continue
            if group_id:
                gid = str(group_id)
                if gid not in {detail.get("group_a_id"), detail.get("group_b_id")}:
                    continue
            filtered.append(signal)
        return filtered

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
        return ollama_client.generate(prompt, temperature=0.3)
