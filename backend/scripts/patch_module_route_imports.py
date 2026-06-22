"""Inject shared imports into split module route files."""
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "endpoints" / "modules"
HEADER = '''"""Module API routes — {name}."""
from .router import router
from .shared import *  # noqa: F403

'''

for path in PKG.glob("*.py"):
    if path.name in {"__init__.py", "router.py", "shared.py", "deps.py", "mappers.py", "constants.py"}:
        continue
    text = path.read_text(encoding="utf-8")
    if "from .shared import" in text:
        continue
    # strip old minimal header
    lines = text.splitlines(keepends=True)
    if lines and lines[0].startswith('"""Module API routes'):
        idx = 0
        for i, line in enumerate(lines):
            if line.strip() == "from .router import router":
                idx = i + 1
                break
        body = "".join(lines[idx:])
    else:
        body = text
    path.write_text(HEADER.format(name=path.stem) + body.lstrip(), encoding="utf-8")
    print("patched", path.name)
