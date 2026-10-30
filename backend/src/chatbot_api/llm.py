"""Client du serveur LLM (API compatible OpenAI) et diffusion des réponses en flux."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol

from openai import APIError, APITimeoutError, OpenAI

from chatbot_api.config import Settings
from chatbot_api.turn import PreparedTurn

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Échec de l'appel au serveur LLM ; `code` est transmis au client."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ReplaceText:
    """Texte complet faisant foi, qui remplace tout ce qui a été diffusé jusque-là."""

    text: str


ReplyChunk = str | ReplaceText


class ChatClient(Protocol):
    def stream_reply(self, turn: PreparedTurn) -> Iterator[ReplyChunk]: ...

    def complete(
        self, *, model: str, system_prompt: str, text: str, max_tokens: int, timeout: float
    ) -> str: ...


class OpenAICompatibleClient:
    def __init__(self, settings: Settings, client: OpenAI | None = None) -> None:
        self._settings = settings
        self._client = client or OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=1,
        )

    def build_messages(self, turn: PreparedTurn) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": turn.system_prompt},
            *({"role": m.role, "content": m.content} for m in turn.messages),
        ]

    def stream_reply(self, turn: PreparedTurn) -> Iterator[ReplyChunk]:
        """Produit les fragments de texte de la réponse au fil de l'eau.

        Les éventuels champs de raisonnement (`reasoning_content`, etc.) des modèles comme
        gpt-oss sont volontairement ignorés : seul le contenu final est transmis.
        """
        settings = self._settings
        params: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": self.build_messages(turn),
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
            "stream": True,
        }
        if settings.llm_reasoning_effort:
            params["reasoning_effort"] = settings.llm_reasoning_effort

        # kb_id n'est pas un paramètre natif du SDK : il passe par extra_body.
        extra_body: dict[str, Any] = dict(settings.llm_extra_body or {})
        if settings.llm_kb_id:
            extra_body["kb_id"] = settings.llm_kb_id
        if extra_body:
            params["extra_body"] = extra_body

        logger.info(
            "LLM base_url=%s model=%s kb_id=%s",
            settings.llm_base_url,
            settings.llm_model,
            extra_body.get("kb_id"),
        )

        try:
            stream = self._client.chat.completions.create(**params)
            for chunk in stream:
                if not chunk.choices:
                    continue
                logger.debug("chunk.choices[0] %s", chunk.choices[0])
                text = chunk.choices[0].delta.content
                if text:
                    yield text
        except APITimeoutError as exc:
            logger.warning("Délai dépassé lors de l'appel au LLM")
            raise LLMError("llm_timeout", "Le serveur LLM n'a pas répondu à temps.") from exc
        except APIError as exc:
            logger.exception("Erreur du serveur LLM")
            raise LLMError("llm_unavailable", "Le serveur LLM est indisponible.") from exc

    def complete(
        self, *, model: str, system_prompt: str, text: str, max_tokens: int, timeout: float
    ) -> str:
        """Appel court, sans diffusion en flux (utilisé par le routeur)."""
        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0,
                max_tokens=max_tokens,
                timeout=timeout,
            )
        except APITimeoutError as exc:
            raise LLMError("llm_timeout", "Le serveur LLM n'a pas répondu à temps.") from exc
        except APIError as exc:
            raise LLMError("llm_unavailable", "Le serveur LLM est indisponible.") from exc
        if not response.choices:
            return ""
        return response.choices[0].message.content or ""
