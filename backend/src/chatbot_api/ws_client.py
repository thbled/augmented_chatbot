"""Client RAG via l'API WebSocket de la plateforme (KB attachée par workspaceId)."""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Iterator
from typing import Any

from websockets.exceptions import WebSocketException
from websockets.sync.client import connect

from chatbot_api.config import Settings
from chatbot_api.llm import LLMError  # ou déplace LLMError dans un module commun
from chatbot_api.prompts import build_system_prompt
from chatbot_api.validation import ChatRequest

logger = logging.getLogger(__name__)


class WebSocketRagClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _build_text(self, request: ChatRequest) -> str:
        # Le payload documenté prend un seul champ `text`. L'historique est donc replié dans le texte.
        *previous, last = request.messages
        if not previous:
            return last.content
        transcript = "\n".join(f"{m.role}: {m.content}" for m in previous)
        return f"Historique de la conversation :\n{transcript}\n\nQuestion actuelle : {last.content}"

    def _build_payload(self, request: ChatRequest) -> dict[str, Any]:
        s = self._settings
        return {
            "action": "run",
            "modelInterface": "multimodal",
            "adapterInterfaceVersion": "v2",
            "data": {
                "mode": "chain",
                "text": self._build_text(request),
                "modelName": s.llm_model,
                "provider": s.ws_provider,
                "sessionId": str(uuid.uuid4()),
                "workspaceId": s.ws_workspace_id,
                "systemPrompt": build_system_prompt(s, request.locale),
                "files": [],
                "modelKwargs": {
                    "maxTokens": max(1, min(s.llm_max_tokens, 4096)),       # plage documentée : 1 à 4096
                    "temperature": max(0.1, min(s.llm_temperature, 1.0)),   # plage documentée : 0,1 à 1
                    "streaming": True,
                    "topP": 0.9,
                },
                "ragKwargs": {"docLimit": min(s.ws_doc_limit, 10)},         # maximum documenté : 10
            },
        }

    def stream_reply(self, request: ChatRequest) -> Iterator[str]:
        s = self._settings
        deadline = time.monotonic() + s.llm_timeout_seconds
        got_tokens = False
        try:
            with connect(
                s.ws_url,
                additional_headers={"x-api-key": s.llm_api_key},
                open_timeout=15,
            ) as ws:
                ws.send(json.dumps(self._build_payload(request)))
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError
                    msg = json.loads(ws.recv(timeout=remaining))
                    action = msg.get("action")
                    data = msg.get("data", {})
                    if action == "llm_new_token":
                        value = data.get("token", {}).get("value")
                        if value:
                            got_tokens = True
                            yield value
                    elif action == "final_response":
                        if not got_tokens and data.get("content"):
                            yield data["content"]  # cas sans tokens intermédiaires
                        return
                    elif action == "error":
                        # Format observé en pratique, non documenté : détail loggé, jamais renvoyé tel quel.
                        logger.error("Erreur WebSocket plateforme : %s", data.get("content"))
                        raise LLMError("llm_unavailable", "Le serveur LLM est indisponible.")
                    # autres messages (heartbeat, etc.) : ignorés
        except TimeoutError as exc:
            logger.warning("Délai dépassé lors de l'appel WebSocket")
            raise LLMError("llm_timeout", "Le serveur LLM n'a pas répondu à temps.") from exc
        except (WebSocketException, OSError, json.JSONDecodeError) as exc:
            logger.exception("Erreur de connexion WebSocket")
            raise LLMError("llm_unavailable", "Le serveur LLM est indisponible.") from exc