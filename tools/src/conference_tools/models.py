"""Modèle de données de la conférence et format des cartes affichées par l'application.

Le JSON produit par les méthodes `to_card()` est le contrat partagé avec le frontend
(voir `frontend/src/types/cards.ts`) : le LLM le recopie tel quel dans ses réponses.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, time
from typing import Any

# Les cartes sont recopiées par le LLM à chaque réponse : on limite les textes longs pour
# garder des réponses rapides. Le texte complet reste dans la partie rédigée du document.
CARD_BIO_MAX_CHARS = 600
CARD_SUMMARY_MAX_CHARS = 240


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")


def truncate(text: str, max_chars: int) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    cut = text[: max_chars - 1].rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:.") + "…"


def _compact(card: dict[str, Any]) -> dict[str, Any]:
    """Retire les champs vides pour alléger le JSON."""
    return {key: value for key, value in card.items() if value not in ("", None, [], {})}


@dataclass
class EventInfo:
    fields: dict[str, str] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.fields.get("Nom de l'événement", "")


@dataclass
class Speaker:
    id: str
    first_name: str
    last_name: str
    consent: bool
    linkedin_url: str = ""
    photo_url: str = ""
    company: str = ""
    job_title: str = ""
    bio: str = ""
    expertise: list[str] = field(default_factory=list)
    sessions: list[Session] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def to_card(self) -> dict[str, Any]:
        return _compact(
            {
                "id": self.id,
                "firstName": self.first_name,
                "lastName": self.last_name,
                "jobTitle": self.job_title,
                "company": self.company,
                "photoUrl": self.photo_url,
                "bio": truncate(self.bio, CARD_BIO_MAX_CHARS),
                "expertise": self.expertise,
                "linkedinUrl": self.linkedin_url,
                "sessions": [session.to_reference() for session in self.sessions],
            }
        )


@dataclass
class SessionSpeaker:
    """Intervenant tel que cité dans le programme (résolu ou non dans l'onglet Speakers)."""

    name: str
    speaker: Speaker | None = None

    @property
    def is_published(self) -> bool:
        # Le consentement ne concerne que la collecte automatique (LinkedIn) : toute
        # donnée saisie dans le classeur est publiable.
        return self.speaker is not None


@dataclass
class Session:
    id: str
    day: date
    start: time
    end: time
    title: str
    format: str = ""
    room: str = ""
    track: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    language: str = ""
    speakers: list[SessionSpeaker] = field(default_factory=list)

    @property
    def start_label(self) -> str:
        return self.start.strftime("%H:%M")

    @property
    def end_label(self) -> str:
        return self.end.strftime("%H:%M")

    def to_reference(self) -> dict[str, Any]:
        return _compact(
            {
                "id": self.id,
                "title": self.title,
                "date": self.day.isoformat(),
                "start": self.start_label,
                "end": self.end_label,
                "room": self.room,
            }
        )

    def to_card(self) -> dict[str, Any]:
        speakers = []
        for entry in self.speakers:
            if entry.is_published and entry.speaker:
                speakers.append(
                    _compact(
                        {
                            "id": entry.speaker.id,
                            "name": entry.speaker.full_name,
                            "photoUrl": entry.speaker.photo_url,
                        }
                    )
                )
            else:
                speakers.append({"name": entry.name})
        return _compact(
            {
                "id": self.id,
                "title": self.title,
                "date": self.day.isoformat(),
                "start": self.start_label,
                "end": self.end_label,
                "room": self.room,
                "format": self.format,
                "track": self.track,
                "language": self.language,
                "summary": truncate(self.description, CARD_SUMMARY_MAX_CHARS),
                "tags": self.tags,
                "speakers": speakers,
            }
        )


@dataclass
class Partner:
    id: str
    name: str
    tier: str = ""
    logo_url: str = ""
    website_url: str = ""
    sector: str = ""
    description: str = ""
    offer: str = ""
    booth: str = ""

    def to_card(self) -> dict[str, Any]:
        return _compact(
            {
                "id": self.id,
                "name": self.name,
                "tier": self.tier,
                "logoUrl": self.logo_url,
                "websiteUrl": self.website_url,
                "sector": self.sector,
                "summary": truncate(self.description, CARD_SUMMARY_MAX_CHARS),
                "booth": self.booth,
            }
        )


@dataclass
class PracticalInfo:
    category: str
    title: str
    content: str


@dataclass
class ConferenceData:
    event: EventInfo
    speakers: list[Speaker]
    sessions: list[Session]
    partners: list[Partner]
    practical: list[PracticalInfo]
