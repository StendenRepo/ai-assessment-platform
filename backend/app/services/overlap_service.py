import itertools
import json
import re
import uuid as uuid_mod
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from app.services import ollama_client
from app.services.overlap_highlight import (
    apply_paired_student_highlights,
    highlight_phrases_paired,
)
from app.services.overlap_integrity_detector import (
    IntegrityFlag,
    IntegrityResult,
    apply_flags_to_document,
    attach_integrity_metrics,
    build_ai_only_hit,
    combine_ai_results,
    dedupe_student_flag_dicts,
    detect_ai_segments,
    enrich_hit_with_ai,
    merge_integrity_results,
)
from app.models.evidence import Evidence
from app.models.enums import OverlapType
from app.models.overlap_signal import OverlapSignal
from app.models.project import Project
from app.models.student import Student, student_projects
from app.services.evidence_service import EVIDENCE_UPLOAD_DIR
from app.services.text_extraction import read_stored_evidence_text
from app.services.overlap_text_detector import (
    EvidenceChunk,
    POSSIBLE_MIN,
    detect_cross_group,
    detect_within_group,
    highlight_shared,
)
from app.services.text_chunker import chunk_text

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_MAX_SIGNALS_PER_RUN = 100
_MAX_AI_VERIFY_PER_RUN = 20
_MAX_AI_DOC_SCANS_PER_RUN = 20
_MAX_PAIR_VERIFY_CHUNK_PAIRS = 3
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
            "ai_verified": hit.get("ai_verified"),
            "ai_explanation": hit.get("ai_explanation"),
            "ai_shared_excerpt": hit.get("ai_shared_excerpt"),
            "detection_method": hit.get("detection_method"),
            "integrity_type": hit.get("integrity_type"),
            "flags": dedupe_student_flag_dicts(hit.get("flags") or []),
            "ai_content_percent": hit.get("ai_content_percent"),
            "peak_ai_section_percent": hit.get("peak_ai_section_percent"),
            "student_match_count": hit.get("student_match_count"),
            "overlap_confidence_percent": hit.get("overlap_confidence_percent"),
            "detection_confidence_percent": hit.get("detection_confidence_percent"),
            "metrics_summary": hit.get("metrics_summary"),
        }
    )


_HIGHLIGHT_MARKER_RE = re.compile(r"\[\[(.*?)\]\]", re.DOTALL)


def extract_highlight_phrase(passage: Optional[str]) -> Optional[str]:
    if not passage:
        return None
    match = _HIGHLIGHT_MARKER_RE.search(passage)
    if match:
        return match.group(1).strip()
    # Fallback for passages without explicit [[...]] markers.
    return passage.strip()


def _dedupe_phrases(phrases: Iterable[str]) -> list[str]:
    ordered = sorted({p.strip() for p in phrases if p and p.strip()}, key=len, reverse=True)
    kept: list[str] = []
    for phrase in ordered:
        lower = phrase.lower()
        if any(lower in existing.lower() or existing.lower() in lower for existing in kept):
            continue
        kept.append(phrase)
    return kept


def shared_phrases_between_documents(
    full_a: str,
    full_b: str,
    *,
    min_similarity: float = POSSIBLE_MIN,
) -> list[str]:
    """Collect shared phrases from chunk and paragraph pairs between two documents."""
    phrases: list[str] = []

    def _collect_from_pairs(left_chunks: list[str], right_chunks: list[str]) -> None:
        if not left_chunks or not right_chunks:
            return
        combined = left_chunks + right_chunks
        matrix = TfidfVectorizer(stop_words="english").fit_transform(combined)
        sim = cosine_similarity(matrix)
        offset = len(left_chunks)
        for i, chunk_a in enumerate(left_chunks):
            for j, chunk_b in enumerate(right_chunks):
                if float(sim[i, offset + j]) < min_similarity:
                    continue
                marked_a, marked_b = highlight_shared(chunk_a, chunk_b)
                for marked in (marked_a, marked_b):
                    for match in _HIGHLIGHT_MARKER_RE.finditer(marked):
                        phrase = match.group(1).strip()
                        if len(phrase.split()) >= 8:
                            phrases.append(phrase)

    _collect_from_pairs(chunk_text(full_a), chunk_text(full_b))

    paragraphs_a = [p.strip() for p in re.split(r"\n\s*\n", full_a) if p.strip()]
    paragraphs_b = [p.strip() for p in re.split(r"\n\s*\n", full_b) if p.strip()]
    _collect_from_pairs(paragraphs_a, paragraphs_b)

    return _dedupe_phrases(phrases)


def build_highlighted_documents(
    db: Session,
    signal: OverlapSignal,
    *,
    detail: Optional[dict] = None,
) -> Tuple[Optional[str], Optional[str], list[dict]]:
    detail = detail if detail is not None else parse_signal_detail(signal.snippet)
    integrity_type = detail.get("integrity_type") or "student_plagiarism"
    flags = dedupe_student_flag_dicts(detail.get("flags") or [])
    effective_flags = flags

    evidence_a = db.query(Evidence).filter(Evidence.id == signal.evidence_a_id).first()
    if not evidence_a:
        return None, None

    full_a = OverlapService._read_evidence_text(evidence_a)
    if not full_a:
        return None, None

    ai_flags = [f for f in flags if f.get("type") == "ai"]
    student_flags = [f for f in flags if f.get("type") == "student"]

    if integrity_type == "ai":
        document_a = apply_flags_to_document(full_a, flags, side="a")
        return document_a, None, effective_flags

    evidence_b = db.query(Evidence).filter(Evidence.id == signal.evidence_b_id).first()
    if not evidence_b:
        document_a = apply_flags_to_document(full_a, flags, side="a")
        return document_a, None, effective_flags

    full_b = OverlapService._read_evidence_text(evidence_b)
    if not full_b:
        return apply_flags_to_document(full_a, flags, side="a"), None, effective_flags

    if student_flags:
        document_a, document_b, effective_flags = apply_paired_student_highlights(
            full_a,
            full_b,
            flags,
        )
    else:
        document_a, document_b = full_a, full_b

    if ai_flags:
        document_a = apply_flags_to_document(document_a, ai_flags, side="a")
        document_b = apply_flags_to_document(document_b, ai_flags, side="b")

    if student_flags:
        return document_a, document_b, effective_flags

    phrases = shared_phrases_between_documents(full_a, full_b)
    if not phrases:
        fallback = extract_highlight_phrase(detail.get("passage_a")) or extract_highlight_phrase(
            detail.get("passage_b")
        )
        if fallback:
            phrases = [fallback]
    ai_excerpt = (detail.get("ai_shared_excerpt") or "").strip()
    if ai_excerpt:
        phrases = _dedupe_phrases([*phrases, ai_excerpt])

    return (*highlight_phrases_paired(full_a, full_b, phrases), effective_flags)


class OverlapService:
    @staticmethod
    def _read_evidence_text(evidence: Evidence) -> str:
        return read_stored_evidence_text(evidence, EVIDENCE_UPLOAD_DIR)

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

        integrity_type = hit.get("integrity_type", "student_plagiarism")
        if integrity_type == "ai":
            overlap_type = OverlapType.semantic
        else:
            overlap_type = OverlapType.textual

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
    def _ai_doc_hits(db: Session, module_id: str) -> list[dict]:
        """Per-submission AI-generated content scan."""
        chunks, student_to_group = OverlapService._build_chunks_for_module(db, module_id)
        if not chunks:
            return []

        projects = db.query(Project).filter(Project.module_id == module_id).all()
        project_by_id = {str(p.id): p for p in projects}

        seen_evidence: set[str] = set()
        hits: list[dict] = []

        evidence_ids = list(dict.fromkeys(c.evidence_id for c in chunks))
        for evidence_id in evidence_ids[:_MAX_AI_DOC_SCANS_PER_RUN]:
            if evidence_id in seen_evidence:
                continue
            chunk = next((c for c in chunks if c.evidence_id == evidence_id), None)
            if not chunk:
                continue
            seen_evidence.add(evidence_id)

            evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
            if not evidence:
                continue
            full_text = OverlapService._read_evidence_text(evidence)
            if not full_text.strip():
                continue

            ai_result = detect_ai_segments(full_text)
            if ai_result.integrity_type != "ai":
                continue
            if ai_result.status == "none":
                continue

            group_id = student_to_group.get(evidence.student_id, "")
            group = project_by_id.get(group_id)
            hits.append(
                build_ai_only_hit(
                    student_id=evidence.student_id,
                    student_name=chunk.student_name,
                    evidence_id=str(evidence.id),
                    file_name=evidence.file_name,
                    group_id=group_id,
                    group_name=group.name if group else "",
                    ai_result=ai_result,
                    document_text=full_text,
                )
            )
        return hits

    @staticmethod
    def _ai_enriched_text_hits(db: Session, module_id: str) -> list[dict]:
        """TF-IDF candidate retrieval followed by on-premise LLM verification."""
        chunks, _ = OverlapService._build_chunks_for_module(db, module_id)
        evidence_text: dict[str, str] = {}
        for chunk in chunks:
            if chunk.evidence_id not in evidence_text:
                evidence = db.query(Evidence).filter(Evidence.id == chunk.evidence_id).first()
                if evidence:
                    evidence_text[chunk.evidence_id] = OverlapService._read_evidence_text(evidence)

        hits = OverlapService._text_hits_for_module(db, module_id)
        pair_hits: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for hit in hits:
            ev_a = str(hit["evidence_a_id"])
            ev_b = str(hit["evidence_b_id"])
            key = (min(ev_a, ev_b), max(ev_a, ev_b))
            pair_hits[key].append(hit)

        pair_best: dict[tuple[str, str], dict] = {}
        for key, group in pair_hits.items():
            pair_best[key] = max(group, key=lambda h: float(h.get("similarity", 0)))

        ai_cache: dict[str, IntegrityResult] = {}
        enriched: list[dict] = []
        for key, hit in list(pair_best.items())[:_MAX_AI_VERIFY_PER_RUN]:
            ev_a = str(hit["evidence_a_id"])
            ev_b = str(hit["evidence_b_id"])
            doc_a = evidence_text.get(ev_a, "")
            doc_b = evidence_text.get(ev_b, "")
            ranked = sorted(
                pair_hits.get(key, [hit]),
                key=lambda h: float(h.get("similarity", 0)),
                reverse=True,
            )
            extra_pairs = [
                (h.get("passage_a", ""), h.get("passage_b", ""))
                for h in ranked[1 : _MAX_PAIR_VERIFY_CHUNK_PAIRS + 1]
            ]
            verified = enrich_hit_with_ai(
                hit,
                document_a=doc_a,
                document_b=doc_b,
                extra_passage_pairs=extra_pairs,
            )
            if not verified:
                continue

            if ev_a not in ai_cache:
                ai_cache[ev_a] = detect_ai_segments(doc_a)
            if ev_b not in ai_cache:
                ai_cache[ev_b] = detect_ai_segments(doc_b)
            combined_ai = combine_ai_results(ai_cache[ev_a], ai_cache[ev_b])

            student_result = IntegrityResult(
                integrity_type=verified.get("integrity_type", "student_plagiarism"),
                confidence=float(verified.get("similarity", 0)),
                status=verified.get("status", "possible"),
                flags=[
                    IntegrityFlag(
                        flag_type=f.get("type", "student"),
                        confidence=float(f.get("confidence", 0)),
                        reason=f.get("reason", ""),
                        text=f.get("text", ""),
                        text_a=f.get("text_a", ""),
                        text_b=f.get("text_b", ""),
                    )
                    for f in verified.get("flags", [])
                ],
                explanation=verified.get("ai_explanation", ""),
                ai_verified=verified.get("ai_verified", False),
                detection_method=verified.get("detection_method", "ai_plagiarism"),
            )

            merged = merge_integrity_results(combined_ai, student_result)
            if merged.integrity_type == "none":
                continue

            verified["integrity_type"] = merged.integrity_type
            verified["similarity"] = merged.confidence
            verified["status"] = merged.status
            verified["ai_explanation"] = merged.explanation
            verified["flags"] = [f.to_dict() for f in merged.flags]
            verified["detection_method"] = merged.detection_method
            attach_integrity_metrics(
                verified,
                ai_result=combined_ai,
                student_confidence=student_result.confidence,
            )
            enriched.append(verified)
        return enriched

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

        for hit in OverlapService._ai_doc_hits(db, module_id):
            signal = OverlapService._text_hit_to_signal(hit, seen_pairs)
            if signal:
                created.append(signal)
            if len(created) >= _MAX_SIGNALS_PER_RUN:
                break

        if len(created) < _MAX_SIGNALS_PER_RUN:
            for hit in OverlapService._ai_enriched_text_hits(db, module_id):
                signal = OverlapService._text_hit_to_signal(hit, seen_pairs)
                if signal:
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
                row_status = "confirmed" if (signal.confidence or 0) >= 0.68 else "possible"
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
            "You are an assessment assistant for an Applied AI course platform.",
            "Overlap was detected using on-premise AI verification of student text.",
            "Write a short warning for a teacher. Keep it under 80 words.",
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
        return ollama_client.generate(
            prompt,
            temperature=0.3,
            **ollama_client.assessment_llm_options(),
        )
