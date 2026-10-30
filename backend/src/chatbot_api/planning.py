"""Planning en direct de l'événement (API REST de la régie).

Format attendu : `{..., "slots": [{"position", "scheduledStart" (ISO UTC), "durationAdjusted"
(secondes), "status" (PENDING | CURRENT | COMPLETED), "title", "type", "timerUid"}, ...]}`.
La réponse est mise en cache quelques secondes ; en cas d'indisponibilité, la dernière copie
valide est réutilisée. Le planning fait foi pour les horaires et le statut des créneaux du jour.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

import httpx

from chatbot_api.clock import EventClock

logger = logging.getLogger(__name__)

STATUSES = {"PENDING", "CURRENT", "COMPLETED"}
MAX_SLOTS_IN_PROMPT = 80


@dataclass(frozen=True)
class Slot:
    title: str
    start: datetime
    end: datetime
    status: str
    type: str = ""
    position: int = 0
    uid: str = ""


def parse_slots(payload: Any) -> list[Slot]:
    raw_slots = payload.get("slots") if isinstance(payload, dict) else None
    if not isinstance(raw_slots, list):
        raise ValueError("Réponse du planning sans liste `slots`")
    slots: list[Slot] = []
    for raw in raw_slots:
        if not isinstance(raw, dict):
            continue
        try:
            title = str(raw["title"]).strip()
            start = datetime.fromisoformat(str(raw["scheduledStart"]).replace("Z", "+00:00"))
            duration = int(raw.get("durationAdjusted") or 0)
        except (KeyError, TypeError, ValueError):
            logger.warning("Créneau du planning ignoré (format inattendu)")
            continue
        if not title or start.tzinfo is None:
            continue
        status = str(raw.get("status") or "").upper()
        slots.append(
            Slot(
                title=title,
                start=start,
                end=start + timedelta(seconds=max(duration, 0)),
                status=status if status in STATUSES else "",
                type=str(raw.get("type") or ""),
                position=int(raw.get("position") or 0),
                uid=str(raw.get("timerUid") or ""),
            )
        )
    return sorted(slots, key=lambda s: (s.start, s.position))


@dataclass(frozen=True)
class PlanningSnapshot:
    now: datetime
    slots: list[Slot]

    def _local(self, slot: Slot) -> Slot:
        tz = self.now.tzinfo
        return replace(slot, start=slot.start.astimezone(tz), end=slot.end.astimezone(tz))

    @property
    def today(self) -> list[Slot]:
        return [
            self._local(s)
            for s in self.slots
            if s.start.astimezone(self.now.tzinfo).date() == self.now.date()
        ]

    @property
    def current(self) -> list[Slot]:
        # Le statut de la régie prime ; à défaut, on se fie aux horaires.
        if any(s.status for s in self.slots):
            return [self._local(s) for s in self.slots if s.status == "CURRENT"]
        return [self._local(s) for s in self.slots if s.start <= self.now < s.end]

    def upcoming(self, limit: int = 3) -> list[Slot]:
        current = {s.uid or s.title for s in self.current}
        pending = [
            s
            for s in self.slots
            if (s.uid or s.title) not in current
            and s.status != "COMPLETED"
            and s.end > self.now
            and (s.status == "PENDING" or s.start >= self.now)
        ]
        return [self._local(s) for s in pending[:limit]]

    def mentioned_titles(self) -> list[str]:
        return [s.title for s in [*self.current, *self.upcoming()]]


def _line(slot: Slot) -> str:
    status = {"CURRENT": " — EN COURS", "COMPLETED": " — terminé"}.get(slot.status, "")
    kind = f" [{slot.type}]" if slot.type else ""
    return f"- {slot.start:%H:%M}–{slot.end:%H:%M} : {slot.title}{kind}{status}"


def _minutes(delta: timedelta) -> str:
    total = max(int(delta.total_seconds() // 60), 0)
    hours, minutes = divmod(total, 60)
    return f"{hours} h {minutes:02d}" if hours else f"{minutes} min"


def _current_line(slot: Slot, now: datetime) -> str:
    return (
        f"{_line(slot)} (commencé depuis {_minutes(now - slot.start)}, "
        f"se termine dans {_minutes(slot.end - now)})"
    )


def format_for_prompt(snapshot: PlanningSnapshot | None) -> str:
    if snapshot is None:
        return (
            "Le planning en direct est momentanément indisponible : appuie-toi sur le programme "
            "de la base de connaissances et précise que les horaires peuvent avoir évolué."
        )
    today = snapshot.today
    if not today:
        return "Aucun créneau n'est prévu aujourd'hui dans le planning en direct."
    current = snapshot.current
    upcoming = snapshot.upcoming()
    lines = ["En ce moment :"]
    lines += [_current_line(s, snapshot.now) for s in current] or ["- aucun créneau en cours"]
    lines += ["", "Ensuite :"]
    lines += [_line(s) for s in upcoming] or ["- plus aucun créneau aujourd'hui"]
    lines += ["", "Planning complet du jour :"]
    lines += [_line(s) for s in today[:MAX_SLOTS_IN_PROMPT]]
    return "\n".join(lines)


class PlanningClient:
    def __init__(
        self,
        url: str,
        clock: EventClock,
        ttl_seconds: float = 30.0,
        timeout_seconds: float = 4.0,
        client: httpx.Client | None = None,
        monotonic=time.monotonic,
    ) -> None:
        self._url = url
        self._clock = clock
        self._ttl = ttl_seconds
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._monotonic = monotonic
        self._lock = threading.Lock()
        self._slots: list[Slot] | None = None
        self._fetched_at = float("-inf")

    def _refresh(self) -> None:
        try:
            response = self._client.get(self._url)
            response.raise_for_status()
            self._slots = parse_slots(response.json())
        except (httpx.HTTPError, ValueError) as exc:
            # On garde la dernière copie valide ; nouvel essai au prochain cycle.
            logger.warning("Planning REST indisponible : %s", type(exc).__name__)
        self._fetched_at = self._monotonic()

    def snapshot(self) -> PlanningSnapshot | None:
        with self._lock:
            if self._monotonic() - self._fetched_at >= self._ttl:
                self._refresh()
            slots = self._slots
        if slots is None:
            return None
        offset = self._clock.day_offset()
        if offset:
            slots = [replace(s, start=s.start + offset, end=s.end + offset) for s in slots]
        return PlanningSnapshot(now=self._clock.now(), slots=slots)
