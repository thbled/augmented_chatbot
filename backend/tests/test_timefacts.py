from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from chatbot_api.planning import PlanningSnapshot, Slot
from chatbot_api.timefacts import compute_facts, extract_time_queries, match_titles

PARIS = ZoneInfo("Europe/Paris")
NOW = datetime(2026, 11, 18, 14, 10, tzinfo=PARIS)


def slot(hh_mm: str, minutes: int, title: str, status: str = "", kind: str = "") -> Slot:
    hour, minute = map(int, hh_mm.split(":"))
    start = NOW.replace(hour=hour, minute=minute)
    return Slot(title, start, start + timedelta(minutes=minutes), status, kind)


SLOTS = [
    slot("09:00", 30, "Accueil café", "COMPLETED"),
    slot("09:30", 45, "Keynote sécurité", "COMPLETED"),
    slot("12:00", 90, "Déjeuner", "COMPLETED"),
    slot("14:00", 45, "Sécuriser ses applications LLM", "CURRENT"),
    slot("15:00", 45, "ATLASSIAN: New ways of Working avec l'IA", "PENDING"),
    slot("15:45", 15, "Pause café", "PENDING"),
    slot("18:30", 60, "Cocktail de clôture", "PENDING"),
]
SNAPSHOT = PlanningSnapshot(now=NOW, slots=SLOTS)


def times(text: str) -> list[str]:
    return [
        q.start.strftime("%d %H:%M") + (q.end.strftime("–%H:%M") if q.end else "")
        for q in extract_time_queries(text, NOW)
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Que se passe-t-il à 15h12 ?", ["18 15:12"]),
        ("Et à 15 h ?", ["18 15:00"]),
        ("Quoi à 15 heures 30 ?", ["18 15:30"]),
        ("What's on at 15:12?", ["18 15:12"]),
        ("What's on at 3:12 pm?", ["18 15:12"]),
        ("And at 9am?", ["18 09:00"]),
        ("Qu'y a-t-il à midi ?", ["18 12:00"]),
        ("Et dans 20 minutes ?", ["18 14:30"]),
        ("Et dans 1 h ?", ["18 15:10"]),
        ("Dans une demi-heure ?", ["18 14:40"]),
        ("What about in an hour?", ["18 15:10"]),
        ("Qu'y a-t-il cet après-midi ?", ["18 12:00–18:00"]),
        ("Le programme de ce soir ?", ["18 18:00–23:59"]),
        ("Et demain à 10h ?", ["19 10:00"]),
        ("Que se passe-t-il demain ?", ["19 00:00–23:59"]),
        ("À partir de 15h, que faire ?", ["18 15:00"]),
        ("La session dure 2h ?", []),
        ("Combien de speakers ?", []),
        ("Qui est le speaker principal ?", []),
    ],
)
def test_extract_time_queries(text, expected):
    assert times(text) == expected


def test_fact_in_the_middle_of_a_session():
    facts = compute_facts("Que se passe-t-il à 15h12 ?", SNAPSHOT)
    assert facts.lines == [
        "À 15:12 : « ATLASSIAN: New ways of Working avec l'IA » (15:00–15:45) — commencé depuis "
        "12 min, se termine dans 33 min.",
        "Créneau suivant : « Pause café » (15:45–16:00).",
    ]
    assert facts.titles == ["ATLASSIAN: New ways of Working avec l'IA", "Pause café"]


def test_fact_between_sessions():
    facts = compute_facts("Et à 17h ?", SNAPSHOT)
    assert facts.lines == [
        "À 17:00 : aucun créneau en cours (après « Pause café » (15:45–16:00)).",
        "Créneau suivant : « Cocktail de clôture » (18:30–19:30).",
    ]


def test_fact_before_first_slot_and_other_day():
    assert compute_facts("À 8h ?", SNAPSHOT).lines[0] == (
        "À 08:00 : aucun créneau en cours (avant le premier créneau)."
    )
    assert compute_facts("Et demain à 10h ?", SNAPSHOT).lines == [
        "Le 19/11/2026 : aucun créneau au planning (journées : 18/11/2026)."
    ]


def test_range_facts():
    facts = compute_facts("Qu'y a-t-il ce soir ?", SNAPSHOT)
    assert facts.lines == [
        "Le soir (18:00–23:59) : 1 créneau(x) :",
        "  - « Cocktail de clôture » (18:30–19:30)",
    ]
    assert facts.as_text().startswith("- Le soir")


def test_title_lookup_with_status():
    facts = compute_facts("À quelle heure commence la pause café ?", SNAPSHOT)
    assert facts.lines == ["« Pause café » (15:45–16:00) : à venir, commence dans 1 h 35."]
    current = compute_facts(
        "Il reste combien de temps à « Sécuriser ses applications LLM » ?", SNAPSHOT
    )
    assert current.lines[-1].endswith("en cours, se termine dans 35 min.")
    done = compute_facts("La keynote sécurité est finie ?", SNAPSHOT)
    assert done.lines == ["« Keynote sécurité » (09:30–10:15) : terminé."]


def test_match_titles_requires_significant_overlap():
    assert match_titles("Parle-moi des nouvelles façons de travailler", SLOTS) == []
    assert [s.title for s in match_titles("la session Atlassian new ways of working", SLOTS)] == [
        "ATLASSIAN: New ways of Working avec l'IA"
    ]


def test_no_facts_without_planning_or_time():
    assert compute_facts("À 15h ?", None).lines == []
    assert compute_facts("Qui sont les speakers ?", SNAPSHOT).lines == []
