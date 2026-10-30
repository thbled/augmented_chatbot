"""Fiche de périmètre de l'événement, utilisée par le routeur (sans RAG).

Elle liste ce qui fait partie de l'événement : nom, thématiques, speakers, partenaires,
sessions (fichier `scope.json` généré par `conference-tools build-kb`), complétés par les
titres du planning en direct. Elle sert à deux choses :
- donner au routeur le contexte nécessaire pour ne pas refuser une question légitime
  (« Qui est Dan Martin ? » quand Dan Martin est speaker) ;
- vérifier par le code qu'une question citant un élément connu n'est jamais refusée, et
  qu'une reformulation n'introduit pas de nom inventé.
"""

from __future__ import annotations

import json
import logging
import unicodedata
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from pathlib import Path

logger = logging.getLogger(__name__)

# Fichier embarqué par défaut (inclus dans le déploiement Vercel avec backend/src).
DEFAULT_SCOPE = "data/scope.json"
# Les noms trop courts (« IA », « Data ») déclencheraient des correspondances fortuites.
MIN_ENTITY_LENGTH = 4


def fold(text: str) -> str:
    """Minuscules sans accents, pour des comparaisons tolérantes."""
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(normalized.lower().split())


@dataclass(frozen=True)
class Scope:
    event_name: str = ""
    themes: list[str] = field(default_factory=list)
    speakers: list[str] = field(default_factory=list)
    partners: list[str] = field(default_factory=list)
    sessions: list[str] = field(default_factory=list)
    # Coordonnées officielles (e-mails, téléphones) que l'assistant peut communiquer.
    contacts: list[str] = field(default_factory=list)

    def with_sessions(self, titles: list[str]) -> Scope:
        merged = list(dict.fromkeys([*self.sessions, *titles]))
        return Scope(
            self.event_name, self.themes, self.speakers, self.partners, merged, self.contacts
        )

    @property
    def entities(self) -> list[str]:
        return [
            name
            for name in [*self.speakers, *self.partners, *self.sessions]
            if len(name) >= MIN_ENTITY_LENGTH
        ]

    def mentions_known_entity(self, text: str) -> bool:
        folded = fold(text)
        for name in self.entities:
            if fold(name) in folded:
                return True
            # Nom de famille seul (« Que présente Lovelace ? ») pour les speakers.
            if name in self.speakers:
                last = fold(name).split(" ")[-1]
                if len(last) >= MIN_ENTITY_LENGTH and f" {last}" in f" {folded}":
                    return True
        return False

    def as_text(self) -> str:
        lines = [f"Événement : {self.event_name or 'conférence professionnelle'}"]
        if self.themes:
            lines.append(f"Thématiques : {', '.join(self.themes)}")
        if self.speakers:
            lines.append(f"Speakers : {', '.join(self.speakers)}")
        if self.partners:
            lines.append(f"Partenaires : {', '.join(self.partners)}")
        if self.sessions:
            lines.append("Sessions et créneaux : " + " ; ".join(self.sessions))
        return "\n".join(lines)


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def parse_scope(data: object) -> Scope:
    if not isinstance(data, dict):
        return Scope()
    return Scope(
        event_name=str(data.get("eventName") or "").strip(),
        themes=_str_list(data.get("themes")),
        speakers=_str_list(data.get("speakers")),
        partners=_str_list(data.get("partners")),
        sessions=_str_list(data.get("sessions")),
        contacts=_str_list(data.get("contacts")),
    )


@cache
def load_scope(path: str = "") -> Scope:
    """Charge la fiche (chemin explicite, sinon fichier embarqué). Absente : fiche vide."""
    try:
        if path:
            raw = Path(path).read_text(encoding="utf-8")
        else:
            raw = resources.files(__package__).joinpath(DEFAULT_SCOPE).read_text(encoding="utf-8")
        return parse_scope(json.loads(raw))
    except (OSError, json.JSONDecodeError):
        logger.warning("Fiche de périmètre introuvable ou invalide : routeur sans liste de noms")
        return Scope()
