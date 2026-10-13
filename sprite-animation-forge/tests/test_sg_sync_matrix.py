"""The docs/14 checker itself: it must fail on what it is meant to catch."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_matrix as sm  # noqa: E402

REAL = "sprite-animation-forge/tests/test_sg_sync_matrix.py::test_sg_matrix_parse_reads_rows_and_not_adopted"


def doc(rows="", skipped=""):
    return f"### A. x\n\n| sprite-gen 기능 | 구현 | 테스트 ID |\n|---|---|---|\n{rows}\n### B. y\n\n## 미채택\n\n| 항목 | 사유 |\n|---|---|\n{skipped}\n"


def test_sg_matrix_parse_reads_rows_and_not_adopted():
    rows, skipped = sm.parse(doc(f"| f | impl | {REAL} |\n", "| pixel-draw | 유료 |\n"))
    assert rows["A"] == [["f", "impl", REAL]] and rows["B"] == [] and skipped == [["pixel-draw", "유료"]]


def test_sg_matrix_a_listed_test_that_does_not_exist_is_an_error():
    errors = sm.check(doc("| f | i | sprite-animation-forge/tests/test_sg_provider.py::test_nope |\n"), run=False)
    assert errors and "no such test function" in errors[0]
    errors = sm.check(doc("| f | i | sprite-animation-forge/tests/missing.py::test_x |\n"), run=False)
    assert errors and "file not found" in errors[0]


def test_sg_matrix_an_incomplete_row_is_an_error():
    assert sm.check(doc("| f | | |\n"), run=False)


def test_sg_matrix_final_needs_every_area_and_enough_complete_not_adopted_rows():
    ok_row = f"| f | i | {REAL} |\n"
    errors = sm.check(doc(ok_row, "| a | r |\n| b | r |\n"), final=True, run=False)
    assert any("area B: no rows" in e for e in errors) and any("not-adopted table has 2" in e for e in errors)
    assert not sm.check(doc(ok_row), final=False, run=False)
    blank_reason = sm.check(doc(ok_row, "".join(f"| item{i} | |\n" for i in range(6))), final=True, run=False)
    assert any("not-adopted table has 0" in e for e in blank_reason)


def test_sg_matrix_listed_tests_must_pass(tmp_path, monkeypatch):
    failing = tmp_path / "test_fails.py"
    failing.write_text("def test_f():\n    assert False\n")
    monkeypatch.setattr(sm, "REPO", tmp_path)
    errors = sm.check(doc("| f | i | test_fails.py::test_f |\n"))
    assert errors and "do not pass" in errors[0]
