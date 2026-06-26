#!/usr/bin/env python3
"""Generate ~69% overlap scroll-test documents on the Desktop."""

from __future__ import annotations

import csv
import io
import random
import re
import shutil
import sys
from pathlib import Path

from docx import Document
from openpyxl import Workbook

ROOT = Path.home() / "Desktop" / "overlap-test-pack" / "04_scroll_test_69_percent"

PARAPHRASE_RATE = 0.38
PARAPHRASE_SEED = 42

SYNONYMS = {
    "implemented": "built",
    "authentication": "auth",
    "module": "component",
    "using": "with",
    "tokens": "token handling",
    "documented": "recorded",
    "every": "each",
    "added": "included",
    "integration": "end-to-end",
    "tests": "test cases",
    "login": "sign-in",
    "logout": "sign-out",
    "session": "user session",
    "refresh": "renewal",
    "tool": "utility",
    "persists": "stores",
    "tasks": "task items",
    "repository": "data access",
    "layer": "tier",
    "isolates": "separates",
    "business": "domain",
    "rules": "logic",
    "agreed": "aligned",
    "formatting": "style",
    "typed": "annotated",
    "function": "method",
    "signatures": "defs",
    "service": "application",
    "cohort": "team",
    "password": "credential",
    "CLI": "command-line",
    "pytest": "unittest",
    "fixtures": "setup helpers",
    "database": "db",
    "mocked": "stubbed",
    "external": "outside",
    "services": "APIs",
    "deterministic": "stable",
    "Coverage": "Test coverage",
    "highlighted": "flagged",
    "middleware": "interceptor",
    "summary": "conclusion",
    "deliverable": "submission",
    "demonstrated": "showed",
    "exported": "saved",
    "Technical": "Engineering",
    "debt": "follow-ups",
}

SHARED_OPENING = (
    "OVERLAP_BLOCK_START: Our cohort implemented the authentication module using JWT tokens "
    "and bcrypt password hashing. We documented every REST endpoint in README.md and added "
    "integration tests for login, logout, and session refresh. The CLI planning tool persists "
    "tasks in SQLite behind a repository layer that isolates SQL from business rules. We "
    "agreed on PEP8 formatting and typed function signatures across the service layer. "
    "This opening section was copied from a shared template before students personalised "
    "their reports."
)

SHARED_MIDDLE = (
    "OVERLAP_BLOCK_MIDDLE: For sprint testing we used pytest with fixtures for the database "
    "and httpx for API calls. We mocked external services and kept tests deterministic in CI. "
    "Coverage reports highlighted the auth middleware and repository modules as priorities. "
    "Pair reviews caught edge cases around expired tokens and malformed Authorization headers. "
    "Both submissions include this paragraph because it was pasted from the same Slack thread."
)

SHARED_CLOSING = (
    "OVERLAP_BLOCK_END: In summary the deliverable meets the rubric for code quality, testing, "
    "and documentation. We demonstrated the CLI flows during the review and exported tasks to CSV. "
    "Technical debt items were logged in the backlog for the next iteration of the project. "
    "The closing wording is suspiciously similar across both portfolios."
)

UNIQUE_A = (
    "## Student A — original middle section\n\n"
    + (
        "I refactored Kanban columns and argparse export handlers for CSV downloads. "
        * 14
    )
    + "Mentors reviewed migration scripts and timezone handling for due dates. "
    "This block is unique to Student A and should not match Student B."
)

UNIQUE_B = (
    "## Student B — original middle section\n\n"
    + (
        "I implemented JWT middleware and Docker Compose for local development workflows. "
        * 14
    )
    + "Reviewers praised pre-commit hooks and pylint configuration changes. "
    "This block is unique to Student B and should not match Student A."
)


def paraphrase(text: str, *, rate: float = PARAPHRASE_RATE, seed: int = 0) -> str:
    random.seed(seed)
    words = text.split()
    output: list[str] = []
    for word in words:
        key = re.sub(r"[^a-zA-Z]", "", word).lower()
        if key in SYNONYMS and random.random() < rate:
            replacement = SYNONYMS[key]
            if word and word[0].isupper():
                replacement = replacement[0].upper() + replacement[1:]
            output.append(replacement)
        else:
            output.append(word)
    return " ".join(output)


def build_document_a() -> str:
    return "\n\n".join(
        [
            "# Sprint 3 Portfolio — Student A",
            SHARED_OPENING,
            UNIQUE_A,
            SHARED_MIDDLE,
            UNIQUE_A,
            SHARED_CLOSING,
        ]
    )


def build_document_b() -> str:
    return "\n\n".join(
        [
            "# Sprint 3 Portfolio — Student B",
            paraphrase(SHARED_OPENING, seed=1),
            UNIQUE_B,
            paraphrase(SHARED_MIDDLE, seed=2),
            UNIQUE_B,
            paraphrase(SHARED_CLOSING, seed=3),
        ]
    )


def write_md(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def write_txt(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def write_docx(path: Path, content: str) -> None:
    doc = Document()
    for block in content.split("\n\n"):
        if block.startswith("# "):
            doc.add_heading(block[2:], level=1)
        elif block.startswith("## "):
            doc.add_heading(block[3:], level=2)
        else:
            doc.add_paragraph(block)
    doc.save(path)


def write_xlsx(path: Path, content: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Portfolio"
    for idx, block in enumerate(content.split("\n\n"), start=1):
        ws.append([f"block_{idx}", block])
    buf = io.BytesIO()
    wb.save(buf)
    path.write_bytes(buf.getvalue())


def write_csv(path: Path, content: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["block", "content"])
        for idx, block in enumerate(content.split("\n\n"), start=1):
            writer.writerow([f"block_{idx}", block])


def write_pdf(path: Path, content: str) -> None:
    from fpdf import FPDF

    def ascii_safe(value: str) -> str:
        return value.replace("\u2014", "-").replace("\u2013", "-")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, ascii_safe(content))
    pdf.output(str(path))


def write_student_files(folder: Path, content: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    stem = "portfolio_scroll_test"
    write_md(folder / f"{stem}.md", content)
    write_txt(folder / f"{stem}.txt", content)
    write_docx(folder / f"{stem}.docx", content)
    write_xlsx(folder / f"{stem}.xlsx", content)
    write_csv(folder / f"{stem}.csv", content)
    write_pdf(folder / f"{stem}.pdf", content)


def estimate_similarity(doc_a: str, doc_b: str) -> tuple[float, str]:
    backend = Path(__file__).resolve().parents[1] / "backend"
    sys.path.insert(0, str(backend))
    try:
        from app.services.overlap.text_detector import EvidenceChunk, detect_within_group
        from app.services.text_chunker import chunk_text
    except ModuleNotFoundError as exc:
        if exc.name != "sklearn":
            raise
        return estimate_similarity_fallback(doc_a, doc_b), "fallback local estimate"

    def chunks(doc: str, student_id: str) -> list[EvidenceChunk]:
        return [
            EvidenceChunk(student_id, student_id, student_id, f"{student_id}.md", i, part, "g1", "G")
            for i, part in enumerate(chunk_text(doc))
        ]

    hits = detect_within_group(chunks(doc_a, "a") + chunks(doc_b, "b"))
    return (hits[0]["similarity"] if hits else 0.0), "backend detector estimate"


def estimate_similarity_fallback(doc_a: str, doc_b: str) -> float:
    """Approximate similarity when local Python lacks backend ML dependencies."""
    import difflib

    return difflib.SequenceMatcher(None, doc_a, doc_b).ratio()


def main() -> None:
    doc_a = build_document_a()
    doc_b = build_document_b()
    similarity, similarity_label = estimate_similarity(doc_a, doc_b)

    if ROOT.exists():
        shutil.rmtree(ROOT)
    ROOT.mkdir(parents=True)

    write_student_files(ROOT / "student-a", doc_a)
    write_student_files(ROOT / "student-b", doc_b)

    readme = f"""# Scroll test — ~69% overlap

Realistic copy-paste pattern:

1. **Opening** — largely copied (look for `OVERLAP_BLOCK_START`)
2. **Middle** — original work unique to each student
3. **Middle overlap** — copied again from Slack (`OVERLAP_BLOCK_MIDDLE`)
4. **More original work** — unique again
5. **Closing** — copied conclusion (`OVERLAP_BLOCK_END`)

## Students

- `student-a/` — original template wording
- `student-b/` — lightly reworded copy (~38% word swaps)

Estimated {similarity_label}: **{round(similarity * 100)}%** (top chunk pair).

## How to test scrolling

1. Upload `student-a/portfolio_scroll_test.md` to one student.
2. Upload `student-b/portfolio_scroll_test.md` to another student in the same group.
3. **Review overlaps** → **Scan module**.
4. Open the hit between these two students (~69%).
5. Use synced scrolling on the detail page — you should need to scroll through the long middle section.

Word count: ~{len(doc_a.split())} words per file.
"""
    (ROOT / "README.md").write_text(readme, encoding="utf-8")

    print(f"Created {ROOT}")
    print(f"Estimated overlap: {round(similarity * 100)}%")
    print(f"Words per document: {len(doc_a.split())}")


if __name__ == "__main__":
    main()
