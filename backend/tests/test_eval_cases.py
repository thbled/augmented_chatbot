"""Cohérence hors ligne du jeu d'évaluation avec le filtre déterministe."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chatbot_api.guard import inspect, normalize

CASES = [
    json.loads(line)
    for line in (Path(__file__).parent.parent / "evals" / "cases.jsonl").read_text().splitlines()
    if line
]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_guard_matches_expectation(case):
    allowed = inspect(normalize(case["question"])).allowed
    if case["expect"] == "blocked":
        assert not allowed
    elif case["expect"] == "answer":
        assert allowed
