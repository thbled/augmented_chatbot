"""Heure de référence de l'événement, contrôlée uniquement par le serveur.

En développement, `EVENT_FAKE_DATE` fige le jour (l'heure reste réelle) et `EVENT_FAKE_NOW`
fige l'instant complet. Le décalage en jours entre le jour simulé et le jour réel est aussi
appliqué au planning REST (dont les données de test suivent la date réelle).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from chatbot_api.config import Settings

WEEKDAYS = {
    "fr": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}


class EventClock:
    def __init__(self, settings: Settings, now: Callable[[], datetime] | None = None) -> None:
        self.tz = ZoneInfo(settings.event_timezone)
        self._fake_date = settings.event_fake_date
        self._fake_now = settings.event_fake_now
        self._real_now = now or (lambda: datetime.now(self.tz))

    def now(self) -> datetime:
        if self._fake_now:
            return self._fake_now.replace(tzinfo=self.tz)
        real = self._real_now().astimezone(self.tz)
        if self._fake_date:
            return real.replace(
                year=self._fake_date.year, month=self._fake_date.month, day=self._fake_date.day
            )
        return real

    def day_offset(self) -> timedelta:
        """Écart entre le jour simulé et le jour réel (nul en production)."""
        simulated: date = self.now().date()
        real: date = self._real_now().astimezone(self.tz).date()
        return timedelta(days=(simulated - real).days)

    def label(self, locale: str = "fr") -> str:
        current = self.now()
        weekday = WEEKDAYS.get(locale, WEEKDAYS["fr"])[current.weekday()]
        return f"{weekday} {current:%d/%m/%Y %H:%M}"
