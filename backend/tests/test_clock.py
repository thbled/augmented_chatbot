from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from chatbot_api.clock import EventClock

REAL_NOW = datetime(2026, 10, 29, 13, 52, tzinfo=UTC)


def test_real_time_in_event_timezone(settings):
    clock = EventClock(settings, now=lambda: REAL_NOW)
    assert clock.now().strftime("%Y-%m-%d %H:%M") == "2026-10-29 14:52"
    assert clock.day_offset() == timedelta(0)
    assert clock.label("fr") == "jeudi 29/10/2026 14:52"
    assert clock.label("en") == "Thursday 29/10/2026 14:52"


def test_fake_date_keeps_real_time(settings):
    clock = EventClock(replace(settings, event_fake_date=date(2026, 11, 18)), now=lambda: REAL_NOW)
    assert clock.now().strftime("%Y-%m-%d %H:%M") == "2026-11-18 14:52"
    assert clock.day_offset() == timedelta(days=20)
    assert clock.label("fr").startswith("mercredi 18/11/2026")


def test_fake_now_freezes_everything(settings):
    fake = datetime(2026, 11, 18, 10, 5)
    clock = EventClock(replace(settings, event_fake_now=fake), now=lambda: REAL_NOW)
    assert clock.now().strftime("%Y-%m-%d %H:%M") == "2026-11-18 10:05"
    assert clock.day_offset() == timedelta(days=20)
