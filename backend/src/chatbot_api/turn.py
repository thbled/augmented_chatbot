"""Préparation d'un tour de conversation avant l'appel au LLM.

- l'heure de référence vient exclusivement du serveur (jamais du client ni de la question) ;
- la question est encadrée par des balises : c'est une donnée, pas une instruction ;
- dans la copie de l'historique envoyée au LLM, les cartes JSON des anciennes réponses sont
  remplacées par un repère court (l'application, elle, conserve et affiche tout) ;
- le planning en direct est injecté dans le prompt système ;
- pour les questions liées au moment présent, les titres des créneaux concernés sont ajoutés
  à la requête de recherche, afin que le RAG retrouve les bonnes fiches.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from chatbot_api.clock import EventClock
from chatbot_api.config import Settings
from chatbot_api.guard import normalize
from chatbot_api.output_guard import times_in
from chatbot_api.planning import PlanningClient, format_for_prompt
from chatbot_api.prompts import build_system_prompt
from chatbot_api.timefacts import compute_facts
from chatbot_api.validation import ChatMessage, ChatRequest

_CARD_BLOCK = re.compile(r"```(speaker|session|partner|place)[ \t]*\n(.*?)\n?```", re.DOTALL)
_SUGGESTIONS_BLOCK = re.compile(r"```suggestions[ \t]*\n.*?\n?```", re.DOTALL)
_QUESTION_TAGS = re.compile(r"</?\s*question\s*>", re.IGNORECASE)

_TIME_RELATED = re.compile(
    r"\b(maintenant|en ce moment|en cours|actuellement|tout de suite|ensuite|apr[eè]s|"
    r"prochaine?s?|suivante?s?|bient[oô]t|aujourd'hui|ce matin|cet apr[eè]s-midi|ce soir|"
    r"programme|planning|now|right now|ongoing|current(ly)?|next|upcoming|later|today|"
    r"this (morning|afternoon|evening)|agenda|schedule)\b",
    re.IGNORECASE,
)

_CARD_LABELS = {
    "speaker": "fiche speaker",
    "session": "fiche session",
    "partner": "fiche partenaire",
    "place": "fiche lieu",
}


def _card_name(kind: str, body: str) -> str:
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return ""
    items = data if isinstance(data, list) else [data]
    names = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if kind == "speaker":
            name = f"{item.get('firstName', '')} {item.get('lastName', '')}".strip()
        else:
            name = str(item.get("title") or item.get("name") or "")
        if name:
            names.append(name)
    return ", ".join(names)


def compact_cards(content: str) -> str:
    """Remplace les blocs de cartes par `[fiche speaker : Ada Lovelace]` et retire les
    suggestions, inutiles pour le contexte."""

    def replace(match: re.Match[str]) -> str:
        label = _CARD_LABELS[match.group(1)]
        name = _card_name(match.group(1), match.group(2))
        return f"[{label} : {name}]" if name else f"[{label}]"

    content = _SUGGESTIONS_BLOCK.sub("", content)
    return _CARD_BLOCK.sub(replace, content).strip()


def wrap_question(question: str, time_label: str) -> str:
    safe = _QUESTION_TAGS.sub("", normalize(question))
    return f"[Heure locale du serveur : {time_label}]\n<question>\n{safe}\n</question>"


@dataclass(frozen=True)
class PreparedTurn:
    locale: str
    system_prompt: str
    messages: list[ChatMessage]
    question: str
    retrieval_hints: list[str] = field(default_factory=list)
    # Titres des créneaux du jour (planning en direct) et horaires de référence (planning,
    # faits calculés, heure courante, question) : utilisés par le contrôle de la réponse.
    planning_titles: list[str] = field(default_factory=list)
    reference_times: set[str] = field(default_factory=set)
    facts: list[str] = field(default_factory=list)

    @property
    def retrieval_hint(self) -> str:
        """Contexte ajouté sous la question pour la recherche documentaire (vide si aucun)."""
        if not self.retrieval_hints:
            return ""
        return "Contexte de recherche :\n" + "\n".join(f"- {h}" for h in self.retrieval_hints)

    @property
    def retrieval_query(self) -> str:
        """Texte destiné à la recherche documentaire : la question, enrichie si besoin."""
        if not self.retrieval_hint:
            return self.question
        return f"{self.question}\n{self.retrieval_hint}"


class TurnBuilder:
    def __init__(
        self,
        settings: Settings,
        clock: EventClock,
        planning: PlanningClient | None = None,
        canary: str = "",
    ) -> None:
        self._settings = settings
        self._clock = clock
        self._planning = planning
        self._canary = canary

    def planning_titles(self) -> list[str]:
        """Titres des créneaux du jour (pour la fiche de périmètre du routeur)."""
        snapshot = self._planning.snapshot() if self._planning else None
        return [s.title for s in snapshot.today] if snapshot else []

    def build(self, request: ChatRequest, standalone: str | None = None) -> PreparedTurn:
        """`standalone` : question reformulée par le routeur, utilisée pour la recherche
        uniquement (le modèle principal reçoit toujours la question d'origine)."""
        snapshot = self._planning.snapshot() if self._planning else None
        planning_text = format_for_prompt(snapshot) if self._planning else ""
        time_label = self._clock.label(request.locale)

        *previous, last = request.messages
        history = [
            ChatMessage(role=m.role, content=compact_cards(m.content))
            if m.role == "assistant" and self._settings.history_compact_cards
            else m
            for m in previous
        ]
        question = last.content

        hints: list[str] = []
        if standalone and standalone.strip().lower() != question.strip().lower():
            hints.append(f"Question reformulée : {standalone.strip()}")

        # Faits horaires calculés par le code (heures, périodes, titres cités dans la question).
        facts = compute_facts(f"{question}\n{standalone or ''}", snapshot)
        titles = list(facts.titles)
        if snapshot and _TIME_RELATED.search(f"{question} {standalone or ''}"):
            titles += [t for t in snapshot.mentioned_titles() if t not in titles]
        if titles:
            hints.append("Créneaux concernés : " + " ; ".join(titles))

        reference_times = times_in(f"{question}\n{facts.as_text()}\n{time_label}")
        if snapshot:
            reference_times |= {f"{s.start:%H:%M}" for s in snapshot.today}
            reference_times |= {f"{s.end:%H:%M}" for s in snapshot.today}

        wrapped = wrap_question(question, time_label)
        return PreparedTurn(
            locale=request.locale,
            system_prompt=build_system_prompt(
                self._settings,
                request.locale,
                time_label,
                planning_text,
                facts.as_text(),
                self._canary,
            ),
            messages=[*history, ChatMessage(role="user", content=wrapped)],
            question=question,
            retrieval_hints=hints,
            planning_titles=[s.title for s in snapshot.today] if snapshot else [],
            reference_times=reference_times,
            facts=facts.lines,
        )
