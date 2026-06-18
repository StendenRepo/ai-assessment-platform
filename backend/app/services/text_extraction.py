"""Best-effort plain-text extraction for module documents (rubrics, module books).

Unlike ``evidence_service._extract_text`` (which raises HTTP 422 on a bad file),
extraction here is *non-fatal*: a document that cannot be parsed yields ``None``
and the upload still succeeds. That is deliberate for G2-105 slice (a) — nothing
consumes this text yet, so a failed parse should never block a teacher from
replacing a rubric or module book. The extracted text is what the AI retrieval
(TF-IDF) will read once it is wired up; keeping it current on replace is the goal.

Supported extensions cover the formats the module endpoints accept:
rubric (.pdf, .xlsx) and module book (.pdf, .docx).
"""

import io


def extract_document_text(raw: bytes, ext: str) -> str | None:
    """Return plain text extracted from *raw* for file extension *ext*.

    *ext* is the lowercased extension including the leading dot (e.g. ".pdf").
    Returns ``None`` if the type is unsupported, the file cannot be parsed, or
    the result is empty after stripping. Never raises — extraction is best-effort.
    """
    try:
        if ext == ".pdf":
            text = _from_pdf(raw)
        elif ext == ".docx":
            text = _from_docx(raw)
        elif ext == ".xlsx":
            text = _from_xlsx(raw)
        elif ext in (".md", ".txt"):
            text = raw.decode("utf-8", errors="ignore")
        else:
            return None
    except Exception:
        # Intentionally silent: a real document that fails to parse leaves the
        # teacher with no extracted text and no error. Acceptable for slice (a)
        # because nothing reads this column yet; revisit when the AI consumes it.
        return None

    text = (text or "").strip()
    return text or None


def _from_pdf(raw: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def _from_docx(raw: bytes) -> str:
    from docx import Document as DocxDocument

    doc = DocxDocument(io.BytesIO(raw))
    return "\n".join(paragraph.text for paragraph in doc.paragraphs)


def _from_xlsx(raw: bytes) -> str:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    lines: list[str] = []
    for sheet in wb.worksheets:
        for row in sheet.iter_rows(values_only=True):
            cells = [str(c) for c in row if c is not None]
            if cells:
                lines.append(" ".join(cells))
    wb.close()
    return "\n".join(lines)
