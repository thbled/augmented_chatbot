"""Validation et normalisation de la requête de chat envoyée par le frontend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from chatbot_api.config import Settings

Locale = Literal["fr", "en"]
SUPPORTED_LOCALES: tuple[Locale, ...] = ("fr", "en")


class ValidationError(ValueError):
    """Requête invalide ; `code` est renvoyé au client pour qu'il affiche un message traduit."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class ChatRequest:
    messages: list[ChatMessage]
    locale: Locale


def parse_chat_request(payload: Any, settings: Settings) -> ChatRequest:
    """Valide le corps JSON et ne conserve que la fin de l'historique.

    Les messages `system` éventuellement envoyés par le client sont refusés : le prompt
    système est exclusivement géré côté serveur.
    """
    if not isinstance(payload, dict):
        raise ValidationError("invalid_payload", "Le corps de la requête doit être un objet JSON.")

    raw_messages = payload.get("messages")
    if not isinstance(raw_messages, list) or not raw_messages:
        raise ValidationError("invalid_messages", "`messages` doit être une liste non vide.")

    locale = payload.get("locale", "fr")
    if locale not in SUPPORTED_LOCALES:
        locale = "fr"

    messages: list[ChatMessage] = []
    for raw in raw_messages:
        if not isinstance(raw, dict):
            raise ValidationError("invalid_messages", "Chaque message doit être un objet.")
        role = raw.get("role")
        content = raw.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            raise ValidationError("invalid_messages", "Rôle ou contenu de message invalide.")
        content = content.strip()
        if not content:
            continue
        if role == "user" and len(content) > settings.max_user_message_chars:
            raise ValidationError("message_too_long", "Le message dépasse la longueur autorisée.")
        if role == "assistant":
            content = content[: settings.max_assistant_message_chars]
        messages.append(ChatMessage(role=role, content=content))

    if not messages or messages[-1].role != "user":
        raise ValidationError("invalid_messages", "Le dernier message doit venir de l'utilisateur.")

    history = messages[-settings.max_history_messages :]
    # L'historique tronqué doit commencer par un message utilisateur pour rester cohérent.
    while history and history[0].role != "user":
        history = history[1:]

    return ChatRequest(messages=history, locale=locale)
