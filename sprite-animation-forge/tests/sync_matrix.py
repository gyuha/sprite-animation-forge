"""Checks docs/14-sprite-gen-sync.md: every (sprite-gen feature -> implementation -> test id) row names tests that exist and pass.

    uv run python sprite-animation-forge/tests/sync_matrix.py            rows so far (what a task checks before it seals)
    uv run python sprite-animation-forge/tests/sync_matrix.py --final    also: areas A-D each have >= 1 row, the
                                                                         not-adopted table has >= 5 rows with a reason

Row format (one per line of a markdown table under a ``### A.`` .. ``### D.`` heading):
    | feature | implementation | sprite-animation-forge/tests/test_x.py::test_name, ... |
Not-adopted rows (under ``## 미채택``): ``| item | reason |``. A parametrized test is named by its function.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOC = REPO / "docs" / "14-sprite-gen-sync.md"
AREAS = ("A", "B", "C", "D")
MIN_NOT_ADOPTED = 5


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse(text: str) -> tuple[dict[str, list[list[str]]], list[list[str]]]:
    rows: dict[str, list[list[str]]] = {a: [] for a in AREAS}
    skipped: list[list[str]] = []
    area, in_skipped = None, False
    for line in text.splitlines():
        head = re.match(r"^#{2,3}\s+([A-D])\.", line)
        if head:
            area, in_skipped = head.group(1), False
        elif line.startswith("## 미채택"):
            area, in_skipped = None, True
        elif line.startswith("## "):
            area, in_skipped = None, False
        if not line.startswith("|") or re.match(r"^\|[\s:|-]+\|?$", line):
            continue
        cells = _cells(line)
        if cells[0] in ("sprite-gen 기능", "항목"):
            continue
        if in_skipped:
            skipped.append(cells)
        elif area:
            rows[area].append(cells)
    return rows, skipped


def _test_exists(test_id: str) -> str | None:
    path, _, name = test_id.partition("::")
    file = REPO / path
    if not file.is_file():
        return f"{test_id}: file not found"
    if not name:
        return f"{test_id}: no test name"
    tree = ast.parse(file.read_text(encoding="utf-8"))
    names = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return None if name.split("[")[0] in names else f"{test_id}: no such test function"


def check(text: str, final: bool = False, run: bool = True) -> list[str]:
    rows, skipped = parse(text)
    errors, ids = [], []
    for area, area_rows in rows.items():
        for cells in area_rows:
            if len(cells) < 3 or not all(cells[:3]):
                errors.append(f"area {area}: incomplete row {cells}")
                continue
            for tid in (t.strip().strip("`") for t in cells[2].split(",")):
                problem = _test_exists(tid)
                errors.append(f"area {area}: {problem}") if problem else ids.append(tid)
    if final:
        errors += [f"area {a}: no rows" for a in AREAS if not rows[a]]
        good = [s for s in skipped if len(s) >= 2 and s[0] and s[1]]
        if len(good) < MIN_NOT_ADOPTED:
            errors.append(f"not-adopted table has {len(good)} complete rows, need >= {MIN_NOT_ADOPTED}")
    if run and ids and not errors:
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *dict.fromkeys(ids)],
                              cwd=REPO, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            errors.append("listed tests do not pass:\n" + "\n".join(proc.stdout.splitlines()[-15:]))
    return errors


def main() -> int:
    if not DOC.is_file():
        print(f"missing {DOC.relative_to(REPO)}")
        return 1
    errors = check(DOC.read_text(encoding="utf-8"), final="--final" in sys.argv)
    rows, skipped = parse(DOC.read_text(encoding="utf-8"))
    print("rows:", {a: len(r) for a, r in rows.items()}, "not adopted:", len(skipped))
    for e in errors:
        print("ERROR", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
