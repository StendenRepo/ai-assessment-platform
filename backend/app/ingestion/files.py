"""Extract plain text from uploaded evidence (FR-03 formats)."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path


SUPPORTED_EXTENSIONS = {
    ".txt",
    ".md",
    ".pdf",
    ".docx",
    ".doc",
    ".pptx",
    ".ppt",
    ".xlsx",
    ".xls",
    ".zip",
}


def extract_text_from_bytes(filename: str, data: bytes) -> str:
    suffix = Path(filename or "upload.txt").suffix.lower()
    if suffix in (".txt", ".md"):
        return data.decode("utf-8", errors="replace")
    if suffix == ".pdf":
        return _pdf(data)
    if suffix in (".docx",):
        return _docx(data)
    if suffix in (".pptx",):
        return _pptx(data)
    if suffix in (".xlsx", ".xls"):
        return _xlsx(data)
    if suffix == ".zip":
        return _zip_archive(data)
    return data.decode("utf-8", errors="replace")


def _pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _docx(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _pptx(data: bytes) -> str:
    from pptx import Presentation

    prs = Presentation(io.BytesIO(data))
    parts: list[str] = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text:
                parts.append(shape.text)
    return "\n".join(parts)


def _xlsx(data: bytes) -> str:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    parts: list[str] = []
    for sheet in wb.worksheets:
        for row in sheet.iter_rows(values_only=True):
            cells = [str(c) for c in row if c is not None]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _zip_archive(data: bytes) -> str:
    parts: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in zf.namelist():
            if name.endswith("/") or name.startswith("__MACOSX"):
                continue
            lower = name.lower()
            if not any(
                lower.endswith(ext)
                for ext in (".txt", ".md", ".py", ".js", ".java", ".pdf", ".docx")
            ):
                continue
            try:
                raw = zf.read(name)
                if lower.endswith((".txt", ".md", ".py", ".js", ".java")):
                    parts.append(f"--- {name} ---\n{raw.decode('utf-8', errors='replace')}")
                elif lower.endswith(".docx"):
                    parts.append(f"--- {name} ---\n{_docx(raw)}")
                elif lower.endswith(".pdf"):
                    parts.append(f"--- {name} ---\n{_pdf(raw)}")
            except Exception:
                parts.append(f"--- {name} --- (could not extract)")
    return "\n\n".join(parts) if parts else "(empty or unsupported zip contents)"


def parse_rubric_lines(text: str) -> list[dict]:
    """Heuristic rubric criteria from uploaded module book / rubric document."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    criteria: list[dict] = []
    for i, line in enumerate(lines[:20]):
        if len(line) < 8:
            continue
        criteria.append(
            {
                "id": f"c{i + 1}",
                "title": line[:120],
                "description": line,
            }
        )
    if not criteria:
        criteria = [
            {
                "id": "c1",
                "title": "Technical contribution",
                "description": "Evidence of technical work.",
            },
            {
                "id": "c2",
                "title": "Documentation",
                "description": "Quality of documentation.",
            },
            {
                "id": "c3",
                "title": "Collaboration",
                "description": "Team collaboration and communication.",
            },
        ]
    return criteria
