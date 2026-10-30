from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import httpx
import pytest

from chatbot_api.clock import EventClock
from chatbot_api.planning import PlanningClient, format_for_prompt, parse_slots

# Jour réel des données de test (la régie de test suit la date du jour).
REAL_NOW = datetime(2026, 10, 29, 13, 10, tzinfo=UTC)  # 14:10 à Paris


def slot(start: str, minutes: int, status: str, title: str, uid: str = "") -> dict:
    return {
        "position": 0,
        "durationAdjusted": minutes * 60,
        "scheduledStart": start,
        "status": status,
        "timerUid": uid or title,
        "title": title,
        "type": "activity",
    }


PAYLOAD = {
    "event": "ignoré",
    "slots": [
        slot("2026-10-29T07:00:00Z", 30, "COMPLETED", "Préparation de la salle"),
        slot("2026-10-29T12:30:00Z", 60, "CURRENT", "Atelier IA générative"),
        slot("2026-10-29T13:30:00Z", 45, "PENDING", "Keynote sécurité"),
        slot("2026-10-29T14:15:00Z", 30, "PENDING", "Pause café"),
        {"title": "Créneau invalide"},
    ],
}


def make_client(settings, payload=PAYLOAD, status_code=200, clock_now=REAL_NOW, ttl=30.0):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status_code, json=payload)

    ticks = iter(range(0, 10_000, 10))
    clock = EventClock(settings, now=lambda: clock_now)
    client = PlanningClient(
        "https://planning.test/slots?id=e77c",
        clock,
        ttl_seconds=ttl,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        monotonic=lambda: next(ticks),
    )
    return client, calls


def test_parse_slots_skips_invalid_entries():
    slots = parse_slots(PAYLOAD)
    assert [s.title for s in slots][:2] == ["Préparation de la salle", "Atelier IA générative"]
    assert len(slots) == 4
    assert slots[1].end.hour == 13 and slots[1].end.minute == 30


def test_parse_slots_requires_list():
    with pytest.raises(ValueError):
        parse_slots({"items": []})


def test_snapshot_current_and_upcoming(settings):
    client, calls = make_client(settings)
    snapshot = client.snapshot()
    assert [s.title for s in snapshot.current] == ["Atelier IA générative"]
    assert [s.title for s in snapshot.upcoming()] == ["Keynote sécurité", "Pause café"]
    assert snapshot.current[0].start.strftime("%H:%M") == "13:30"  # heure de Paris
    assert str(calls[0].url) == "https://planning.test/slots?id=e77c"

    text = format_for_prompt(snapshot)
    assert "- 13:30–14:30 : Atelier IA générative [activity] — EN COURS" in text
    assert "- 08:00–08:30 : Préparation de la salle [activity] — terminé" in text


def test_fake_date_shifts_slots_to_event_day(settings):
    dev = replace(settings, event_fake_date=date(2026, 11, 18))
    client, _ = make_client(dev)
    snapshot = client.snapshot()
    assert snapshot.now.date() == date(2026, 11, 18)
    assert snapshot.now.strftime("%H:%M") == "14:10"
    assert {s.start.date() for s in snapshot.today} == {date(2026, 11, 18)}
    assert [s.title for s in snapshot.current] == ["Atelier IA générative"]


def test_cache_and_stale_fallback(settings):
    responses = iter([httpx.Response(200, json=PAYLOAD), httpx.Response(503)])
    clock = EventClock(settings, now=lambda: REAL_NOW)
    ticks = iter([0, 0, 5, 100, 100])
    client = PlanningClient(
        "https://planning.test",
        clock,
        ttl_seconds=30,
        client=httpx.Client(transport=httpx.MockTransport(lambda _: next(responses))),
        monotonic=lambda: next(ticks),
    )
    first = client.snapshot()  # appel REST
    assert client.snapshot().slots == first.slots  # cache (5 s < 30 s)
    assert client.snapshot().slots == first.slots  # REST en erreur : dernière copie valide


def test_unavailable_planning(settings):
    client, _ = make_client(settings, status_code=500)
    assert client.snapshot() is None
    assert "indisponible" in format_for_prompt(None)


def test_status_less_slots_use_times(settings):
    payload = {"slots": [{**s, "status": ""} for s in PAYLOAD["slots"][:3]]}
    client, _ = make_client(settings, payload=payload)
    assert [s.title for s in client.snapshot().current] == ["Atelier IA générative"]
