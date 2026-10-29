"""Client du serveur LLM (API compatible OpenAI) et diffusion des réponses en flux."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any, Protocol

from openai import APIError, APITimeoutError, OpenAI

from chatbot_api.config import Settings
from chatbot_api.prompts import build_system_prompt
from chatbot_api.validation import ChatRequest

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Échec de l'appel au serveur LLM ; `code` est transmis au client."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ChatClient(Protocol):
    def stream_reply(self, request: ChatRequest) -> Iterator[str]: ...


class OpenAICompatibleClient:
    def __init__(self, settings: Settings, client: OpenAI | None = None) -> None:
        self._settings = settings
        self._client = client or OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=1,
        )
    
    def build_messages(self, request: ChatRequest) -> list[dict[str, str]]:
        system = build_system_prompt(self._settings, request.locale)
        return [
            {"role": "system", "content": system},
            *({"role": m.role, "content": m.content} for m in request.messages),
        ]

    def stream_reply(self, request: ChatRequest) -> Iterator[str]:
        """Produit les fragments de texte de la réponse au fil de l'eau.

        Les éventuels champs de raisonnement (`reasoning_content`, etc.) des modèles comme
        gpt-oss sont volontairement ignorés : seul le contenu final est transmis.
        """
        settings = self._settings
        params: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": self.build_messages(request),
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
            settings.llm_base_url, settings.llm_model, extra_body.get("kb_id"),
        )

        try:
            stream = self._client.chat.completions.create(**params)
            for chunk in stream:
                if not chunk.choices:
                    logger.warning("NO chunk.choices")
                    continue
                logger.warning("chunk.choices[0] %s", chunk.choices[0])
                text = chunk.choices[0].delta.content

                if text:
                    yield text
        except APITimeoutError as exc:
            logger.warning("Délai dépassé lors de l'appel au LLM")
            raise LLMError("llm_timeout", "Le serveur LLM n'a pas répondu à temps.") from exc
        except APIError as exc:
            logger.exception("Erreur du serveur LLM")
            raise LLMError("llm_unavailable", "Le serveur LLM est indisponible.") from exc
