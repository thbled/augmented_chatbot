"""Construction du prompt système à partir du gabarit `system_prompt.md`."""

from __future__ import annotations

from functools import cache
from importlib import resources
from string import Template

from chatbot_api.config import Settings

_LOCALE_NAMES: dict[str, str] = {"fr": "français", "en": "anglais"}

NO_PLANNING = "Aucun planning en direct n'est configuré : appuie-toi sur la base de connaissances."
NO_FACTS = "Aucun fait calculé pour cette question."


@cache
def _template() -> Template:
    text = resources.files(__package__).joinpath("system_prompt.md").read_text(encoding="utf-8")
    return Template(text)


def build_system_prompt(
    settings: Settings,
    locale: str,
    time_label: str,
    planning_text: str = "",
    facts_text: str = "",
    canary: str = "",
) -> str:
    return _template().safe_substitute(
        event_name=settings.event_name,
        now=time_label,
        timezone=settings.event_timezone,
        locale_name=_LOCALE_NAMES.get(locale, "français"),
        planning=planning_text or NO_PLANNING,
        facts=facts_text or NO_FACTS,
        canary=canary or "non défini",
    )
