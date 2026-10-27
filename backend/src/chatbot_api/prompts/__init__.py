"""Construction du prompt système à partir du gabarit `system_prompt.md`."""

from __future__ import annotations

from datetime import datetime
from functools import cache
from importlib import resources
from string import Template
from zoneinfo import ZoneInfo

from chatbot_api.config import Settings
from chatbot_api.validation import Locale

_LOCALE_NAMES: dict[str, str] = {"fr": "français", "en": "anglais"}


@cache
def _template() -> Template:
    text = resources.files(__package__).joinpath("system_prompt.md").read_text(encoding="utf-8")
    return Template(text)


def build_system_prompt(settings: Settings, locale: Locale, now: datetime | None = None) -> str:
    tz = ZoneInfo(settings.event_timezone)
    current = (now or datetime.now(tz)).astimezone(tz)
    return _template().safe_substitute(
        event_name=settings.event_name,
        now=current.strftime("%A %d/%m/%Y %H:%M"),
        timezone=settings.event_timezone,
        locale_name=_LOCALE_NAMES.get(locale, "français"),
    )
