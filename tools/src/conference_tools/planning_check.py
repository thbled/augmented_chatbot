"""Cohérence entre le planning en direct (API de la régie) et le programme du classeur.

Le planning REST fait foi pour les horaires du jour ; la base de connaissances (générée depuis
le classeur) apporte le détail des sessions. Un écart entre les deux (session absente d'un
côté, horaires différents) produirait des réponses contradictoires : ce contrôle le détecte
avant l'événement. La comparaison porte sur l'heure locale (événement d'une journée), ce qui
permet aussi de vérifier des données de test datées d'un autre jour.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from conference_tools.models import Session, slugify


@dataclass(frozen=True)
class LiveSlot:
    title: str
    start: time
    end: time
    type: str = ""


@dataclass
class PlanningReport:
    matched: list[tuple[Session, LiveSlot]] = field(default_factory=list)
    time_mismatches: list[str] = field(default_factory=list)
    only_live: list[LiveSlot] = field(default_factory=list)
    only_workbook: list[Session] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.time_mismatches and not self.only_workbook


def parse_live_slots(payload: Any, timezone: str) -> list[LiveSlot]:
    tz = ZoneInfo(timezone)
    raw_slots = payload.get("slots") if isinstance(payload, dict) else None
    if not isinstance(raw_slots, list):
        raise ValueError("Réponse du planning sans liste `slots`")
    slots = []
    for raw in raw_slots:
        try:
            start = datetime.fromisoformat(str(raw["scheduledStart"]).replace("Z", "+00:00"))
            end = start + timedelta(seconds=int(raw.get("durationAdjusted") or 0))
            title = str(raw["title"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if title and start.tzinfo:
            local_start, local_end = start.astimezone(tz), end.astimezone(tz)
            slots.append(
                LiveSlot(title, local_start.time(), local_end.time(), str(raw.get("type") or ""))
            )
    return sorted(slots, key=lambda s: s.start)


def fetch_live_slots(url: str, timezone: str, client: httpx.Client | None = None) -> list[LiveSlot]:
    client = client or httpx.Client(timeout=10)
    response = client.get(url)
    response.raise_for_status()
    return parse_live_slots(response.json(), timezone)


def _words(title: str) -> set[str]:
    return {w for w in re.split(r"-", slugify(title)) if len(w) >= 3}


def _same_title(a: str, b: str) -> bool:
    if slugify(a) == slugify(b):
        return True
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return False
    return len(wa & wb) / min(len(wa), len(wb)) >= 0.8


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def compare(sessions: list[Session], live: list[LiveSlot], tolerance: int = 5) -> PlanningReport:
    report = PlanningReport()
    remaining = list(live)
    for session in sessions:
        match = next((s for s in remaining if _same_title(session.title, s.title)), None)
        if match is None:
            report.only_workbook.append(session)
            continue
        remaining.remove(match)
        report.matched.append((session, match))
        start_gap = abs(_minutes(session.start) - _minutes(match.start))
        end_gap = abs(_minutes(session.end) - _minutes(match.end))
        if start_gap > tolerance or end_gap > tolerance:
            report.time_mismatches.append(
                f"« {session.title} » : classeur {session.start_label}–{session.end_label}, "
                f"planning {match.start:%H:%M}–{match.end:%H:%M}"
            )
    report.only_live = remaining
    return report
