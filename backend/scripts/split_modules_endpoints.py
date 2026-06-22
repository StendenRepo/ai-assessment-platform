"""One-off helper to split modules.py into the modules/ package. Run from backend/."""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "app" / "api" / "v1" / "endpoints" / "modules.py"
PKG = ROOT / "app" / "api" / "v1" / "endpoints" / "modules"

# 1-based inclusive line ranges from original modules.py
SECTIONS = {
    "crud.py": [(392, 403), (674, 876)],
    "templates.py": [(405, 672)],
    "documents.py": [(879, 1220)],
    "groups.py": [(1227, 1533)],
    "students.py": [(1540, 1902)],
    "overlap.py": [(1909, 1996)],
    "export.py": [(2003, 2372)],
}

COMMON_HEADER = '''"""Module API routes — {name}."""
'''

lines = SRC.read_text(encoding="utf-8").splitlines(keepends=True)

PKG.mkdir(parents=True, exist_ok=True)

(PKG / "router.py").write_text(
    '"""Shared APIRouter for module endpoints."""\nfrom fastapi import APIRouter\n\nrouter = APIRouter()\n',
    encoding="utf-8",
)

(PKG / "__init__.py").write_text(
    '''"""Module endpoints package."""
from .router import router
from . import crud, templates, documents, groups, students, overlap, export  # noqa: F401

__all__ = ["router"]
''',
    encoding="utf-8",
)

for filename, ranges in SECTIONS.items():
    chunks = []
    for start, end in ranges:
        chunks.extend(lines[start - 1 : end])
    body = "".join(chunks)
    # Replace local router with package router import
    content = COMMON_HEADER.format(name=filename.replace(".py", "")) + (
        "from .router import router\n\n" + body.lstrip()
    )
    (PKG / filename).write_text(content, encoding="utf-8")
    print(f"wrote {filename} ({sum(e - s + 1 for s, e in ranges)} lines)")

print("done")
