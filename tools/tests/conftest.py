from __future__ import annotations

from pathlib import Path

import pytest

from conference_tools.workbook import create_template


@pytest.fixture
def template_path(tmp_path: Path) -> Path:
    path = tmp_path / "conference.xlsx"
    create_template(path)
    return path
