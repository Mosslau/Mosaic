"""Smoke test: every chapter's code.py must compile.

The legacy `agents/` track was removed; this test now guards the canonical
s01-s20 chapter code instead (one parametrized case per chapter).
"""

from pathlib import Path

import py_compile
import pytest


ROOT = Path(__file__).resolve().parents[1]
CHAPTER_FILES = sorted(ROOT.glob("s*_*/code.py"))
CHAPTER_IDS = [p.parent.name for p in CHAPTER_FILES]


@pytest.mark.parametrize("chapter_path", CHAPTER_FILES, ids=CHAPTER_IDS)
def test_chapter_compiles(chapter_path: Path) -> None:
    _ = py_compile.compile(str(chapter_path), doraise=True)


def test_all_20_chapters_present() -> None:
    assert len(CHAPTER_FILES) == 20, f"expected 20 chapters, got {len(CHAPTER_FILES)}"
