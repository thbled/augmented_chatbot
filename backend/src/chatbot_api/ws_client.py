"""Client RAG via l'API WebSocket de la plateforme (KB attachée par workspaceId).

Les tokens (`llm_new_token`) peuvent arriver dans le désordre : ils sont remis dans l'ordre
de leur `sequenceNumber` avant diffusion. À la fin, le contenu de `final_response` fait foi
et remplace le texte diffusé (événement `ReplaceText`), ce qui garantit une réponse complète
et correctement ordonnée même si des tokens manquent ou arrivent en retard.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Iterator
from typing import Any

from websockets.exceptions import WebSocketException
from websockets.sync.client import connect

from chatbot_api.config import Settings
from chatbot_api.llm import LLMError, ReplaceText, ReplyChunk
from chatbot_api.turn import PreparedTurn

logger = logging.getLogger(__name__)

# Au-delà de ce nombre de tokens en attente d'un trou de séquence, on cesse d'attendre.
MAX_PENDING_TOKENS = 20

_CITATION = re.compile(
    r"\s*\[(?:Doc(?:ument)?|Source)\s*\d+(?:\s*[,;]\s*(?:(?:Doc(?:ument)?|Source)\s*)?\d+)*\]",
    re.IGNORECASE,
)
_TRAILING_CITATION = re.compile(r"\s*\[(?:Doc(?:ument)?|Source)[^\]\n]*$", re.IGNORECASE)

_ROLE_LABELS = {"user": "Utilisateur", "assistant": "Assistant"}


def strip_citations(text: str) -> str:
    """Retire les renvois aux documents ajoutés par la plateforme (« [Doc 1] »)."""
    return _TRAILING_CITATION.sub("", _CITATION.sub("", text))


class TokenOrderer:
    """Remet dans l'ordre les tokens d'une exécution (`runId`) selon `sequenceNumber`."""

    def __init__(self) -> None:
        self.run_id: Any = None
        self._pending: dict[int, str] = {}
        self._next: int | None = None

    def _switch_run(self, run_id: Any) -> bool:
        """Prend en compte `runId` ; vrai si une nouvelle exécution remplace la précédente."""
        if run_id is None:
            return False
        changed = self.run_id is not None and run_id != self.run_id
        if changed:
            self._pending.clear()
            self._next = None
        self.run_id = run_id
        return changed

    def add(self, token: dict[str, Any]) -> tuple[list[str], bool]:
        """Ajoute un token ; renvoie les fragments prêts à diffuser et si une nouvelle
        exécution a commencé (le texte déjà diffusé doit alors être effacé)."""
        value = token.get("value")
        if not isinstance(value, str) or not value:
            return [], False
        seq = token.get("sequenceNumber")
        if not isinstance(seq, int):
            return [value], False  # pas de numéro : ordre d'arrivée

        reset = self._switch_run(token.get("runId"))
        if self._next is not None and seq < self._next:
            return [], reset  # arrivé trop tard : rétabli par la réponse finale
        self._pending[seq] = value
        if self._next is None and seq <= 1:
            self._next = seq
        # Trou persistant (token perdu) : on reprend au plus petit numéro disponible.
        stalled = self._next is None or self._next not in self._pending
        if stalled and len(self._pending) > MAX_PENDING_TOKENS:
            self._next = min(self._pending)

        ready: list[str] = []
        while self._next is not None and self._next in self._pending:
            ready.append(self._pending.pop(self._next))
            self._next += 1
        return ready, reset


class WebSocketRagClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @staticmethod
    def _transcript(turn: PreparedTurn) -> str:
        return "\n".join(
            f"{_ROLE_LABELS.get(m.role, m.role)} : {m.content}" for m in turn.messages[:-1]
        )

    def _build_text(self, turn: PreparedTurn) -> str:
        question = turn.messages[-1].content
        if turn.retrieval_hint:
            question = f"{question}\n{turn.retrieval_hint}"
        transcript = self._transcript(turn)
        if self._settings.ws_history_in == "system" or not transcript:
            return question
        # Le payload documenté prend un seul champ `text` : l'historique y est replié.
        return f"Historique de la conversation :\n{transcript}\n\nQuestion actuelle :\n{question}"

    def _build_system_prompt(self, turn: PreparedTurn) -> str:
        transcript = self._transcript(turn)
        if self._settings.ws_history_in != "system" or not transcript:
            return turn.system_prompt
        return f"{turn.system_prompt}\n\n# Historique de la conversation\n{transcript}"

    def _payload(
        self,
        *,
        text: str,
        system_prompt: str,
        model: str,
        workspace_id: str,
        streaming: bool,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        s = self._settings
        data: dict[str, Any] = {
            "mode": "chain",
            "text": text,
            "modelName": model,
            "provider": s.ws_provider,
            "sessionId": str(uuid.uuid4()),
            "systemPrompt": system_prompt,
            "files": [],
            "modelKwargs": {
                "maxTokens": max(1, min(max_tokens, 4096)),  # plage documentée : 1 à 4096
                "temperature": max(0.1, min(temperature, 1.0)),  # plage documentée : 0,1 à 1
                "streaming": streaming,
                "topP": 0.9,
            },
        }
        if workspace_id:  # sans workspaceId : appel direct au modèle, sans recherche RAG
            data["workspaceId"] = workspace_id
            data["ragKwargs"] = {"docLimit": min(s.ws_doc_limit, 10)}  # maximum documenté : 10
        return {
            "action": "run",
            "modelInterface": "multimodal",
            "adapterInterfaceVersion": "v2",
            "data": data,
        }

    def _build_payload(self, turn: PreparedTurn) -> dict[str, Any]:
        s = self._settings
        return self._payload(
            text=self._build_text(turn),
            system_prompt=self._build_system_prompt(turn),
            model=s.llm_model,
            workspace_id=s.ws_workspace_id,
            streaming=True,
            max_tokens=s.llm_max_tokens,
            temperature=s.llm_temperature,
        )

    def _messages(self, payload: dict[str, Any], timeout: float) -> Iterator[tuple[str, dict]]:
        """Envoie la requête et produit les messages reçus (`action`, `data`) jusqu'à la
        réponse finale. Les erreurs de transport sont converties en `LLMError`."""
        s = self._settings
        deadline = time.monotonic() + timeout
        try:
            with connect(
                s.ws_url,
                additional_headers={"x-api-key": s.llm_api_key},
                open_timeout=min(15, timeout),
            ) as ws:
                ws.send(json.dumps(payload))
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError
                    raw = ws.recv(timeout=remaining)
                    if s.ws_debug_raw:
                        logger.info("WS brut : %s", str(raw)[:4000])
                    msg = json.loads(raw)
                    action = msg.get("action")
                    data = msg.get("data") or {}
                    if action == "error":
                        # Format observé en pratique, non documenté : détail loggé, jamais renvoyé.
                        logger.error("Erreur WebSocket plateforme : %s", data.get("content"))
                        raise LLMError("llm_unavailable", "Le serveur LLM est indisponible.")
                    yield action, data
                    if action == "final_response":
                        return
                    # autres messages (heartbeat, etc.) : transmis puis ignorés par l'appelant
        except TimeoutError as exc:
            logger.warning("Délai dépassé lors de l'appel WebSocket")
            raise LLMError("llm_timeout", "Le serveur LLM n'a pas répondu à temps.") from exc
        except (WebSocketException, OSError, json.JSONDecodeError) as exc:
            logger.exception("Erreur de connexion WebSocket")
            raise LLMError("llm_unavailable", "Le serveur LLM est indisponible.") from exc

    def stream_reply(self, turn: PreparedTurn) -> Iterator[ReplyChunk]:
        orderer = TokenOrderer()
        payload = self._build_payload(turn)
        for action, data in self._messages(payload, self._settings.llm_timeout_seconds):
            if action == "llm_new_token":
                ready, reset = orderer.add(data.get("token") or {})
                if reset:
                    yield ReplaceText("")
                yield from ready
            elif action == "final_response":
                content = data.get("content")
                if isinstance(content, str) and content.strip():
                    yield ReplaceText(strip_citations(content))

    def complete(
        self, *, model: str, system_prompt: str, text: str, max_tokens: int, timeout: float
    ) -> str:
        """Appel court, sans RAG ni diffusion en flux (utilisé par le routeur)."""
        payload = self._payload(
            text=text,
            system_prompt=system_prompt,
            model=model,
            workspace_id="",
            streaming=False,
            max_tokens=max_tokens,
            temperature=0.1,
        )
        tokens: list[str] = []
        for action, data in self._messages(payload, timeout):
            if action == "llm_new_token":
                value = (data.get("token") or {}).get("value")
                if isinstance(value, str):
                    tokens.append(value)
            elif action == "final_response":
                content = data.get("content")
                if isinstance(content, str) and content.strip():
                    return content
        return "".join(tokens)
