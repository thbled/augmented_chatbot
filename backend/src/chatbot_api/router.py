"""Garde-fou n°2 : routeur (petit modèle, sans RAG) appelé avant le modèle principal.

Il classe la question (dans le périmètre, hors sujet, manipulation) et la reformule pour
qu'elle se comprenne sans l'historique. Sa sortie n'est jamais montrée à l'utilisateur, et
le code encadre ses erreurs possibles :
- refus seulement au-delà d'un seuil de confiance, et jamais si la question cite un speaker,
  un partenaire ou une session connus ;
- reformulation rejetée si elle introduit un nom ou un nombre absent de la question, de
  l'historique et de la fiche de périmètre (pas d'invention possible) ;
- réponse illisible, délai dépassé ou panne : la question passe telle quelle.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from functools import cache
from importlib import resources
from string import Template
from typing import Literal, Protocol

from chatbot_api.config import Settings
from chatbot_api.guard import normalize
from chatbot_api.scope import Scope, fold, load_scope
from chatbot_api.turn import compact_cards
from chatbot_api.validation import ChatRequest

logger = logging.getLogger(__name__)

Verdict = Literal["allow", "off_topic", "manipulation"]
VERDICTS: tuple[Verdict, ...] = ("allow", "off_topic", "manipulation")

ROUTER_MAX_TOKENS = 300
MAX_QUESTION_CHARS = 400
HISTORY_EXCERPT_CHARS = 400

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)
_NUMBER = re.compile(r"\d+")
_CAPITALIZED = re.compile(r"\b[A-ZÀ-ÖØ-Þ][\w'’-]{2,}")
_SENTENCE_START = re.compile(r"(^|[.!?:;«\"(\[]\s*)$")


class Completer(Protocol):
    def complete(
        self, *, model: str, system_prompt: str, text: str, max_tokens: int, timeout: float
    ) -> str: ...


@dataclass(frozen=True)
class RouterDecision:
    verdict: Verdict
    question: str
    confidence: float = 0.0
    # llm | low_confidence | known_entity | fallback
    source: str = "llm"

    @property
    def allowed(self) -> bool:
        return self.verdict == "allow"


@cache
def _template() -> Template:
    text = resources.files("chatbot_api.prompts").joinpath("router_prompt.md").read_text("utf-8")
    return Template(text)


def build_router_prompt(scope: Scope) -> str:
    return _template().safe_substitute(scope=f"# Éléments connus de l'événement\n{scope.as_text()}")


def build_router_input(request: ChatRequest, history_messages: int) -> str:
    *previous, last = request.messages
    lines = []
    for message in previous[-history_messages:] if history_messages > 0 else []:
        label = "Utilisateur" if message.role == "user" else "Assistant"
        content = compact_cards(message.content) if message.role == "assistant" else message.content
        lines.append(f"{label} : {content[:HISTORY_EXCERPT_CHARS]}")
    history = "\n".join(lines) if lines else "(aucun)"
    question = normalize(last.content).replace("<question>", "").replace("</question>", "")
    return (
        f"Historique récent :\n{history}\n\n"
        f"Dernière question :\n<question>\n{question}\n</question>"
    )


def parse_router_output(raw: str) -> tuple[Verdict, float, str] | None:
    match = _JSON_OBJECT.search(raw or "")
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get("verdict") not in VERDICTS:
        return None
    try:
        confidence = min(max(float(data.get("confidence", 0)), 0.0), 1.0)
    except (TypeError, ValueError):
        confidence = 0.0
    question = data.get("question")
    question = question.strip() if isinstance(question, str) else ""
    return data["verdict"], confidence, question


def _new_terms(rewrite: str, reference: str) -> list[str]:
    """Noms propres et nombres de la reformulation absents du texte de référence."""
    folded_reference = fold(reference)
    reference_numbers = set(_NUMBER.findall(reference))
    new = [n for n in _NUMBER.findall(rewrite) if n not in reference_numbers]
    for match in _CAPITALIZED.finditer(rewrite):
        if _SENTENCE_START.search(rewrite[: match.start()]):
            continue  # majuscule de début de phrase, pas forcément un nom propre
        if fold(match.group(0)) not in folded_reference:
            new.append(match.group(0))
    return new


def accept_rewrite(question: str, rewrite: str, reference: str) -> str:
    """Retient la reformulation seulement si elle n'invente rien ; sinon la question d'origine."""
    if not rewrite or len(rewrite) > MAX_QUESTION_CHARS:
        return question
    invented = _new_terms(rewrite, reference)
    if invented:
        logger.info("Reformulation du routeur écartée (%d terme(s) absent(s))", len(invented))
        return question
    return rewrite


class Router:
    def __init__(self, settings: Settings, completer: Completer) -> None:
        self._settings = settings
        self._completer = completer

    def decide(
        self, request: ChatRequest, planning_titles: list[str] | None = None
    ) -> RouterDecision:
        settings = self._settings
        question = normalize(request.messages[-1].content)
        scope = load_scope(settings.scope_file).with_sessions(planning_titles or [])

        try:
            raw = self._completer.complete(
                model=settings.router_model,
                system_prompt=build_router_prompt(scope),
                text=build_router_input(request, settings.router_history_messages),
                max_tokens=ROUTER_MAX_TOKENS,
                timeout=settings.router_timeout_seconds,
            )
        except Exception:
            logger.warning("Routeur indisponible : la question passe sans classement")
            return RouterDecision("allow", question, source="fallback")

        parsed = parse_router_output(raw)
        if parsed is None:
            logger.warning("Réponse du routeur illisible : la question passe sans classement")
            return RouterDecision("allow", question, source="fallback")
        verdict, confidence, rewrite = parsed

        reference = "\n".join([*(m.content for m in request.messages), scope.as_text()])
        standalone = accept_rewrite(question, rewrite, reference)

        if verdict != "allow":
            if confidence < settings.router_reject_confidence:
                return RouterDecision("allow", standalone, confidence, "low_confidence")
            if scope.mentions_known_entity(question):
                return RouterDecision("allow", standalone, confidence, "known_entity")
        return RouterDecision(verdict, standalone, confidence)
