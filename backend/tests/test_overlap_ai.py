from unittest.mock import patch

from app.services.overlap.integrity import (
    assess_student_plagiarism,
    detect_ai_segments,
    enrich_hit_with_ai,
    merge_integrity_results,
    scan_document_pair_plagiarism,
    scan_evidence_pair_plagiarism,
    _near_duplicate_plagiarism_result,
    _flags_from_direct_text_comparison,
    IntegrityResult,
    IntegrityFlag,
)
from app.services.overlap.highlight import (
    apply_paired_student_highlights,
    compress_student_marker_ids,
)
from app.services.overlap.integrity.ai_policy import build_ai_result
from app.services.overlap.integrity.thresholds import (
    AI_CLASSIFIER_CONFIRMED,
    AI_CLASSIFIER_MIN,
)
from app.services.overlap.markers import apply_flags_to_document


def test_assess_student_plagiarism_uses_ai_response():
    ai_json = (
        '{"plagiarism_detected": true, "overall_confidence": 0.84, "status": "confirmed", '
        '"flags": [{"text_a": "JWT tokens and bcrypt hashing", '
        '"text_b": "JWT tokens with bcrypt hashing", "confidence": 0.84, '
        '"reason": "Paraphrased authentication paragraph"}], '
        '"explanation": "Both excerpts share the same authentication ideas with light edits."}'
    )
    with patch(
        "app.services.overlap.integrity.plagiarism_detection.ollama_client.generate",
        return_value=ai_json,
    ):
        result = assess_student_plagiarism(
            "Our team implemented JWT tokens and bcrypt hashing for login.",
            "Our team built JWT tokens with bcrypt hashing for login.",
            0.62,
        )
    assert result.integrity_type == "student_plagiarism"
    assert result.confidence == 0.84
    assert result.ai_verified is True
    assert result.flags[0].text_a == "JWT tokens and bcrypt hashing"


def test_assess_student_plagiarism_falls_back_when_ai_unavailable():
    with patch(
        "app.services.overlap.integrity.plagiarism_detection.ollama_client.generate",
        return_value=None,
    ):
        result = assess_student_plagiarism(
            "Our team built a custom auth module with JWT tokens",
            "Their group implemented a different login service using sessions",
            0.72,
        )
    assert result.integrity_type == "student_plagiarism"
    assert result.ai_verified is False
    assert "unavailable" in result.explanation.lower()


def test_detect_ai_segments_flags_ai_content():
    ai_json = (
        '{"ai_detected": true, "overall_confidence": 0.89, '
        '"flags": [{"text": "Furthermore it is important to note that", '
        '"confidence": 0.89, "reason": "Generic LLM hedging phrase"}], '
        '"explanation": "AI patterns detected"}'
    )
    long_text = " ".join(["word"] * 50) + " Furthermore it is important to note that the system works."
    with patch(
        "app.services.ai_detector_client.classify_text",
        return_value=None,
    ), patch(
        "app.services.overlap.integrity.ai_detection.ollama_client.generate",
        return_value=ai_json,
    ):
        result = detect_ai_segments(long_text)
    assert result.integrity_type == "ai"
    assert result.confidence >= 0.62
    assert result.flags


def test_detect_ai_segments_uses_heuristics_when_llm_unavailable():
    long_text = (
        " ".join(["word"] * 50)
        + " Furthermore it is important to note that the comprehensive system "
        "utilizes robust architecture. Additionally it is important to note that "
        "the seamless integration plays a crucial role. In conclusion the "
        "multifaceted design leverages best practices."
    )
    with patch(
        "app.services.ai_detector_client.classify_text",
        return_value=None,
    ), patch(
        "app.services.overlap.integrity.ai_detection.ollama_client.generate",
        return_value=None,
    ):
        result = detect_ai_segments(long_text)
    assert result.integrity_type == "ai"
    assert result.detection_method == "heuristic_ai"
    assert result.flags


def test_detect_ai_segments_prefers_classifier_over_llm():
    long_text = " ".join(["word"] * 50) + " This report was written entirely by a language model."
    classifier_payload = {
        "available": True,
        "model": "yuchuantian/AIGC_detector_env3",
        "ai_probability": 0.97,
        "human_probability": 0.03,
        "max_segment_probability": 0.99,
        "ai_window_fraction": 1.0,
        "label": "ai",
        "status": "confirmed",
        "explanation": "Classifier estimates ~97% AI-like content.",
        "segments": [
            {
                "start_word": 0,
                "text": "This report was written entirely by a language model.",
                "ai_probability": 0.97,
            }
        ],
    }
    with patch(
        "app.services.ai_detector_client.classify_text",
        return_value=classifier_payload,
    ), patch(
        "app.services.overlap.integrity.ai_detection.ollama_client.generate",
    ) as mock_llm:
        result = detect_ai_segments(long_text)
    assert result.integrity_type == "ai"
    assert result.confidence == 0.97
    assert result.detection_method == "classifier_roberta"
    mock_llm.assert_not_called()


def test_ai_policy_keeps_classifier_document_score_as_report_confidence():
    document_score = (AI_CLASSIFIER_MIN + AI_CLASSIFIER_CONFIRMED) / 2
    result = build_ai_result(
        [
            IntegrityFlag(
                "ai",
                0.97,
                "Classifier segment",
                text="This report was written entirely by a language model.",
            )
        ],
        confidence=document_score,
        ai_verified=True,
        detection_method="classifier_roberta",
        explanation="Classifier score.",
    )

    assert result.integrity_type == "ai"
    assert result.confidence == document_score
    assert result.status == "possible"


def test_scan_document_for_ai_flags_entirely_ai_submission():
    ai_json = (
        '{"ai_detected": true, "overall_confidence": 0.91, "status": "confirmed", '
        '"flags": [{"text": "This comprehensive report utilizes robust methodologies", '
        '"confidence": 0.91, "reason": "Generic AI tone throughout"}], '
        '"explanation": "Submission reads as entirely LLM-generated."}'
    )
    text = " ".join(["padding"] * 45) + " This comprehensive report utilizes robust methodologies."
    with patch(
        "app.services.overlap.integrity.ai_detection.ollama_client.generate",
        return_value=ai_json,
    ):
        from app.services.overlap.integrity import scan_document_for_ai

        result = scan_document_for_ai(text)
    assert result.integrity_type == "ai"
    assert result.detection_method == "ai_full_document"


def test_enrich_hit_with_ai_rejects_when_model_says_none():
    hit = {
        "passage_a": "Completely unique report A",
        "passage_b": "Completely unique report B",
        "similarity": 0.4,
        "status": "possible",
    }
    with patch(
        "app.services.overlap.integrity.plagiarism_detection.assess_student_plagiarism",
        return_value=IntegrityResult(
            integrity_type="none",
            confidence=0.1,
            status="none",
            explanation="No meaningful overlap.",
            ai_verified=True,
        ),
    ):
        assert enrich_hit_with_ai(hit) is None


def test_merge_integrity_results_both():
    ai = IntegrityResult(
        integrity_type="ai",
        confidence=0.9,
        status="confirmed",
        flags=[IntegrityFlag("ai", 0.9, "LLM tone", text="generic prose section")],
        ai_verified=True,
    )
    student = IntegrityResult(
        integrity_type="student_plagiarism",
        confidence=0.85,
        status="confirmed",
        flags=[
            IntegrityFlag(
                "student",
                0.85,
                "Paraphrased",
                text_a="shared idea",
                text_b="shared concept",
            )
        ],
        ai_verified=True,
    )
    merged = merge_integrity_results(ai, student)
    assert merged.integrity_type == "both"
    assert len(merged.flags) == 2


def test_apply_flags_to_document_embeds_typed_markers():
    flags = [
        {
            "type": "student",
            "match_id": 1,
            "confidence": 0.85,
            "reason": "Paraphrased section",
            "text_a": "the authentication module works",
            "text_b": "the authentication module works",
        }
    ]
    doc = "We built the authentication module works using JWT."
    marked = apply_flags_to_document(doc, flags, side="a")
    assert "⟦student:m1:85:Paraphrased section⟧" in marked
    assert "the authentication module works" in marked


def test_scan_document_pair_plagiarism_orders_flags():
    ai_json = (
        '{"plagiarism_detected": true, "overall_confidence": 0.88, "status": "confirmed", '
        '"flags": ['
        '{"order_in_a": 2, "text_a": "second shared paragraph about databases and storage design patterns here", '
        '"text_b": "second shared paragraph about databases and storage design patterns here", "confidence": 0.86, "reason": "Copy"}, '
        '{"order_in_a": 1, "text_a": "first shared introduction paragraph here with enough words to pass validation", '
        '"text_b": "first shared introduction paragraph here with enough words to pass validation", "confidence": 0.90, "reason": "Copy"}'
        '], "explanation": "Multiple overlaps."}'
    )
    doc_a = (
        "first shared introduction paragraph here with enough words to pass validation. "
        "Some unique middle content that is only in submission A and not shared. "
        "second shared paragraph about databases and storage design patterns here."
    )
    doc_b = (
        "first shared introduction paragraph here with enough words to pass validation. "
        "Other unique content that is only in submission B and not shared at all. "
        "second shared paragraph about databases and storage design patterns here."
    )
    with patch(
        "app.services.overlap.integrity.plagiarism_detection.ollama_client.generate",
        return_value=ai_json,
    ):
        result = scan_document_pair_plagiarism(doc_a, doc_b, tfidf_hint=0.7)
    assert result.integrity_type == "student_plagiarism"
    assert result.detection_method == "ai_full_document"
    assert result.flags[0].text_a.startswith("first shared")
    assert result.flags[1].text_a.startswith("second shared")


def test_paired_highlights_renumber_without_gaps():
    doc_a = (
        "Alpha one two three four five six seven. "
        "Beta one two three four five six seven. "
        "Gamma one two three four five six seven."
    )
    doc_b = (
        "Alpha one two three four five six seven. "
        "Missing beta entirely here. "
        "Gamma one two three four five six seven."
    )
    flags = [
        {
            "type": "student",
            "confidence": 0.9,
            "reason": "Match A",
            "text_a": "Alpha one two three four five six seven",
            "text_b": "Alpha one two three four five six seven",
        },
        {
            "type": "student",
            "confidence": 0.88,
            "reason": "Unpaired",
            "text_a": "Beta one two three four five six seven",
            "text_b": "Beta one two three four five six seven",
        },
        {
            "type": "student",
            "confidence": 0.87,
            "reason": "Match B",
            "text_a": "Gamma one two three four five six seven",
            "text_b": "Gamma one two three four five six seven",
        },
    ]
    marked_a, marked_b, effective = apply_paired_student_highlights(doc_a, doc_b, flags)
    student_ids = sorted(f["match_id"] for f in effective if f.get("type") == "student")
    assert student_ids == [1, 2]
    assert "⟦student:m1:" in marked_a and "⟦student:m2:" in marked_a
    assert "⟦student:m3:" not in marked_a
    assert "⟦student:m1:" in marked_b and "⟦student:m2:" in marked_b


def test_compress_student_marker_ids_removes_gaps():
    doc_a = "⟦student:m1:85:a⟧one⟦/student⟧ mid ⟦student:m2:85:b⟧two⟦/student⟧ end ⟦student:m4:85:c⟧three⟦/student⟧"
    doc_b = "⟦student:m1:85:a⟧one⟦/student⟧ mid ⟦student:m2:85:b⟧two⟦/student⟧ end ⟦student:m4:85:c⟧three⟦/student⟧"
    fixed_a, fixed_b = compress_student_marker_ids(doc_a, doc_b)
    assert "⟦student:m3:" in fixed_a
    assert "⟦student:m4:" not in fixed_a
    assert "⟦student:m3:" in fixed_b
    assert "⟦student:m4:" not in fixed_b


def test_portfolio_style_three_blocks_numbered_one_two_three():
    """START / MIDDLE / END overlap blocks should appear as Match 1, 2, 3 — not 1, 2, 4."""
    block_start_a = (
        "Our cohort implemented the authentication module using JWT tokens and bcrypt password hashing."
    )
    block_middle_a = (
        "For sprint testing we used pytest with fixtures for the database and httpx for API calls."
    )
    block_end_a = (
        "In summary the deliverable meets the rubric for code quality, testing, and documentation."
    )
    unique_a = "Kanban columns and argparse export handlers for CSV downloads. " * 3

    block_start_b = (
        "Our team implemented the authentication component using JWT tokens and bcrypt password hashing."
    )
    block_middle_b = (
        "For sprint testing we used pytest with fixtures for the db and httpx for API calls."
    )
    block_end_b = (
        "In conclusion the deliverable meets the rubric for code quality, testing, and documentation."
    )
    unique_b = "JWT middleware and Docker Compose for local development workflows. " * 3

    doc_a = f"{block_start_a}\n\n{unique_a}\n\n{block_middle_a}\n\n{unique_a}\n\n{block_end_a}"
    doc_b = f"{block_start_b}\n\n{unique_b}\n\n{block_middle_b}\n\n{unique_b}\n\n{block_end_b}"

    flags = [
        {
            "type": "student",
            "confidence": 0.9,
            "reason": "Shared template opening",
            "text_a": block_start_a,
            "text_b": block_start_b,
        },
        {
            "type": "student",
            "confidence": 0.88,
            "reason": "Slack thread paste",
            "text_a": block_middle_a,
            "text_b": block_middle_b,
        },
        {
            "type": "student",
            "confidence": 0.86,
            "reason": "Shared closing",
            "text_a": block_end_a,
            "text_b": block_end_b,
        },
    ]
    marked_a, marked_b, effective = apply_paired_student_highlights(doc_a, doc_b, flags)
    student_ids = [f["match_id"] for f in effective if f.get("type") == "student"]
    assert student_ids == [1, 2, 3]
    assert "⟦student:m4:" not in marked_a
    assert "⟦student:m4:" not in marked_b
    for mid in (1, 2, 3):
        marker = f"⟦student:m{mid}:"
        assert marker in marked_a
        assert marker in marked_b


def test_failed_middle_pair_does_not_leave_id_gap():
    """If match 3 cannot highlight on both sides, closing becomes Match 3 — not Match 4."""
    doc_a = (
        "Block one shared opening text here for testing. "
        "Block two shared middle pytest fixtures database. "
        "Block three shared closing summary rubric quality testing."
    )
    doc_b = (
        "Block one shared opening text here for testing. "
        "Only student B has this middle paragraph content. "
        "Block three shared closing summary rubric quality testing."
    )
    flags = [
        {
            "type": "student",
            "confidence": 0.9,
            "reason": "Opening",
            "text_a": "Block one shared opening text here for testing",
            "text_b": "Block one shared opening text here for testing",
        },
        {
            "type": "student",
            "confidence": 0.88,
            "reason": "Middle",
            "text_a": "Block two shared middle pytest fixtures database",
            "text_b": "Block two shared middle pytest fixtures database",
        },
        {
            "type": "student",
            "confidence": 0.86,
            "reason": "Closing",
            "text_a": "Block three shared closing summary rubric quality testing",
            "text_b": "Block three shared closing summary rubric quality testing",
        },
    ]
    marked_a, marked_b, effective = apply_paired_student_highlights(doc_a, doc_b, flags)
    student_ids = [f["match_id"] for f in effective if f.get("type") == "student"]
    assert student_ids == [1, 2]
    assert "⟦student:m4:" not in marked_a
    assert "⟦student:m1:" in marked_a
    assert "⟦student:m2:" in marked_a
    assert "⟦student:m2:" in marked_b


def test_near_duplicate_identical_documents():
    doc = (
        "Introduction paragraph with enough words to compare properly here today. "
        "Second paragraph explains the same project methodology in identical wording. "
        "Third paragraph concludes with shared results and identical summary text."
    )
    with patch("app.services.overlap.integrity.plagiarism_detection.ollama_client.generate") as llm:
        result = _near_duplicate_plagiarism_result(doc, doc, tfidf_hint=0.99)
    llm.assert_not_called()
    assert result is not None
    assert result.integrity_type == "student_plagiarism"
    assert result.confidence >= 0.98
    assert len(result.flags) >= 1
    assert result.detection_method == "direct_comparison"
    assert result.ai_verified is False


def test_direct_comparison_splits_long_identical_documents():
    sentence = (
        "This sentence repeats across the submission with enough words to count as a unit. "
    )
    doc = sentence * 40
    flags = _flags_from_direct_text_comparison(doc, doc, base_confidence=0.99)
    assert len(flags) >= 5


def test_scan_evidence_pair_uses_near_duplicate_for_identical_docs():
    doc = (
        "Opening section with sufficient words for integrity comparison testing here. "
        "Middle section repeats the same content in both student submissions exactly. "
        "Closing section also matches word for word between both uploaded files."
    )
    with patch("app.services.overlap.integrity.plagiarism_detection.ollama_client.generate") as llm:
        result = scan_evidence_pair_plagiarism(
            doc,
            doc,
            tfidf_hint=0.99,
            primary_passage_a=doc[:200],
            primary_passage_b=doc[:200],
        )
    llm.assert_not_called()
    assert result.confidence >= 0.98
    assert len(result.flags) >= 1
    assert result.detection_method == "direct_comparison"


def test_scan_evidence_pair_uses_excerpts_for_long_documents():
    long_a = "unique coursework paragraph with enough words for student A only. " * 400
    long_b = "different coursework paragraph with enough words for student B only. " * 400
    with patch(
        "app.services.overlap.integrity.plagiarism_detection.scan_document_pair_plagiarism",
    ) as full_scan, patch(
        "app.services.overlap.integrity.plagiarism_detection.assess_student_plagiarism",
        return_value=IntegrityResult(
            integrity_type="student_plagiarism",
            confidence=0.84,
            status="confirmed",
            flags=[
                IntegrityFlag(
                    flag_type="student",
                    confidence=0.84,
                    reason="Copied",
                    text_a="shared excerpt",
                    text_b="shared excerpt",
                )
            ],
            explanation="Copied passage.",
            ai_verified=True,
            detection_method="ai_plagiarism",
        ),
    ) as excerpt_scan:
        result = scan_evidence_pair_plagiarism(
            long_a,
            long_b,
            tfidf_hint=0.84,
            primary_passage_a="shared excerpt from chunk A with enough words here",
            primary_passage_b="shared excerpt from chunk B with enough words here",
        )
    full_scan.assert_not_called()
    excerpt_scan.assert_called()
    assert result.integrity_type == "student_plagiarism"


def test_enrich_hit_attaches_student_plagiarism_metrics():
    ai_json = (
        '{"plagiarism_detected": true, "overall_confidence": 0.84, "status": "confirmed", '
        '"flags": [{"text_a": "shared paragraph", "text_b": "shared paragraph", '
        '"confidence": 0.84, "reason": "Copied"}], "explanation": "Copied passage."}'
    )
    with patch(
        "app.services.overlap.integrity.plagiarism_detection.ollama_client.generate",
        return_value=ai_json,
    ):
        hit = enrich_hit_with_ai(
            {
                "passage_a": "Our kanban board tracks sprint tasks and daily standup notes for the API project",
                "passage_b": "Their scrum wall lists backlog items and retrospective action points for the web app",
                "similarity": 0.7,
            },
        )
    assert hit["student_match_count"] == 1
    assert hit["overlap_confidence_percent"] == 84
    assert "matched passage" in hit["metrics_summary"]
    assert "84% overlap confidence" in hit["metrics_summary"]

