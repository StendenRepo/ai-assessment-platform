from openpyxl import Workbook

from app.ai.ai_judge import _parse_verdict
from app.ai.chunking import chunk_text
from app.ai.evidence_matcher import EvidenceChunk, match_criteria
from app.ai.rubric_criteria import Criterion, extract_criteria


class TestChunking:
    def test_empty_text_yields_no_chunks(self):
        assert chunk_text("") == []
        assert chunk_text("   \n  ") == []

    def test_short_text_is_a_single_chunk(self):
        assert chunk_text("One short sentence.") == ["One short sentence."]

    def test_long_text_splits_into_overlapping_chunks(self):
        text = ". ".join(f"sentence number {i} has several words here" for i in range(20))
        chunks = chunk_text(text, chunk_size=20, overlap=5)
        assert len(chunks) > 1
        assert all(len(c.split()) <= 25 for c in chunks)

    def test_a_quote_is_drawn_verbatim_from_the_source_words(self):
        text = "The architecture uses clean layered design. Tests cover the modules."
        for chunk in chunk_text(text, chunk_size=8, overlap=2):
            for word in chunk.split():
                assert word in text

    def test_markdown_markers_are_stripped_from_quotes(self):
        text = (
            "## Testing\n"
            "We wrote **comprehensive** unit tests for the modules.\n"
            "- covering the booking calculation and pricing rules\n"
        )
        chunks = chunk_text(text, chunk_size=60, overlap=15)
        joined = " ".join(chunks)
        assert "#" not in joined
        assert "*" not in joined
        assert "- covering" not in joined
        assert "Testing. We wrote comprehensive unit tests" in joined

    def test_chunks_start_at_a_sentence_boundary(self):
        text = " ".join(f"Sentence number {i} carries several words here." for i in range(30))
        chunks = chunk_text(text, chunk_size=20, overlap=6)
        assert len(chunks) > 1
        assert all(c[0].isupper() for c in chunks)


class TestRubricCriteria:
    def test_xlsx_one_row_per_criterion(self, tmp_path):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["Criterion", "Description"])
        sheet.append(["Clean code", "Student writes clean, readable code"])
        sheet.append(["Testing", "Student writes unit tests"])
        path = tmp_path / "rubric.xlsx"
        workbook.save(path)

        criteria = extract_criteria(path, ".xlsx", None)

        keys = [c.key for c in criteria]
        assert keys == ["Clean code", "Testing"]
        assert "readable code" in criteria[0].text

    def test_duplicate_keys_are_made_unique(self, tmp_path):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["Quality", "first aspect of quality work"])
        sheet.append(["Quality", "second aspect of quality work"])
        path = tmp_path / "dupes.xlsx"
        workbook.save(path)

        keys = [c.key for c in extract_criteria(path, ".xlsx", None)]
        assert keys == ["Quality", "Quality (2)"]

    def test_text_fallback_when_not_xlsx(self):
        text = "Student designs a clean architecture\nStudent writes thorough tests\nx"
        criteria = extract_criteria(None, ".pdf", text)
        assert [c.key for c in criteria] == [
            "Student designs a clean architecture",
            "Student writes thorough tests",
        ]


class TestMatcher:
    def _chunks(self):
        return [
            EvidenceChunk("e1", 0, "We built a clean layered architecture with design patterns."),
            EvidenceChunk("e1", 1, "The grocery shopping list included milk and bread."),
        ]

    def test_match_is_grounded_in_a_real_chunk(self):
        criteria = [Criterion(key="arch", text="clean architecture and design patterns")]
        results = match_criteria(criteria, self._chunks(), threshold=0.05, top_k=3)
        result = results[0]
        assert result.matches
        best = result.matches[0]
        assert best.chunk.chunk_index == 0
        assert "architecture" in best.chunk.text
        assert 0.0 < best.score <= 1.0

    def test_unrelated_criterion_has_no_match(self):
        criteria = [Criterion(key="bio", text="photosynthesis in marine plankton")]
        results = match_criteria(criteria, self._chunks(), threshold=0.05, top_k=3)
        assert results[0].matches == []

    def test_no_chunks_means_every_criterion_uncovered(self):
        criteria = [Criterion(key="a", text="anything at all")]
        results = match_criteria(criteria, [], threshold=0.05, top_k=3)
        assert results[0].matches == []


class TestAiJudgeParsing:
    def test_supported_verdict_with_valid_choice(self):
        v = _parse_verdict('{"supported": true, "best": 2, "reason": "ok"}', {1, 2})
        assert v == {"supported": True, "best": 2, "reason": "ok"}

    def test_choice_outside_candidate_list_is_rejected(self):
        v = _parse_verdict('{"supported": true, "best": 9, "reason": "x"}', {1, 2})
        assert v["supported"] is False
        assert v["best"] is None

    def test_supported_without_a_choice_is_not_supported(self):
        v = _parse_verdict('{"supported": true, "best": null, "reason": "x"}', {1})
        assert v["supported"] is False

    def test_not_supported_keeps_reason(self):
        v = _parse_verdict('{"supported": false, "best": null, "reason": "no match"}', {1})
        assert v["supported"] is False
        assert v["reason"] == "no match"

    def test_leaked_excerpt_prefix_is_stripped(self):
        v = _parse_verdict(
            '{"supported": true, "best": 1, "reason": "Excerpt 1 shows clean architecture"}',
            {1},
        )
        assert v["reason"] == "Shows clean architecture"

    def test_the_excerpt_prefix_is_stripped(self):
        v = _parse_verdict(
            '{"supported": true, "best": 2, "reason": "The excerpt describes unit tests"}',
            {2},
        )
        assert v["reason"] == "Describes unit tests"

    def test_reason_without_prefix_is_unchanged(self):
        v = _parse_verdict(
            '{"supported": true, "best": 1, "reason": "Mentions reusable components"}',
            {1},
        )
        assert v["reason"] == "Mentions reusable components"
