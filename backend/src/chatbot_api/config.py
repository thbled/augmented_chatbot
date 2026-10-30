"""Configuration chargée depuis les variables d'environnement (et `.env` en local)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


class ConfigError(ValueError):
    """Configuration invalide ou incomplète."""


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "oui"}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} doit être un entier (reçu : {raw!r})") from exc


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} doit être un nombre (reçu : {raw!r})") from exc


def _get_json_object(name: str) -> dict[str, Any]:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{name} doit contenir un objet JSON valide") from exc
    if not isinstance(value, dict):
        raise ConfigError(f"{name} doit contenir un objet JSON")
    return value


def _get_first(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return None


def _get_date(name: str) -> date | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} doit être une date AAAA-MM-JJ (reçu : {raw!r})") from exc


def _get_datetime(name: str) -> datetime | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).replace(tzinfo=None)
    except ValueError as exc:
        raise ConfigError(f"{name} doit être au format AAAA-MM-JJTHH:MM (reçu : {raw!r})") from exc


def _get_list(name: str) -> list[str]:
    raw = os.getenv(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_temperature: float = 0.3
    llm_max_tokens: int = 2500
    llm_timeout_seconds: float = 45.0
    llm_reasoning_effort: str | None = None
    llm_extra_body: dict[str, Any] = field(default_factory=dict)
    llm_kb_id: str = ""
    ws_url: str = ""
    ws_provider: str = ""
    ws_workspace_id: str = ""
    ws_doc_limit: int = 10
    # "text" : historique replié dans le champ `text` ; "system" : dans le prompt système
    # (le champ `text` ne contient alors que la question, ce qui améliore la recherche RAG).
    ws_history_in: str = "text"
    ws_debug_raw: bool = False

    event_name: str = "la conférence"
    event_timezone: str = "Europe/Paris"
    # Développement uniquement : jour simulé (heure réelle) ou instant simulé complet.
    event_fake_date: date | None = None
    event_fake_now: datetime | None = None

    planning_url: str = ""
    planning_ttl_seconds: float = 30.0

    guard_enabled: bool = True

    # Garde-fou LAYA (optionnel, local, CPU) : détection des manipulations. Vide = désactivé.
    laya_model_dir: str = ""
    laya_threshold: float = 0.8
    laya_threads: int = 0  # 0 = choix automatique d'onnxruntime

    # Garde-fou n°2 : routeur (petit modèle, sans RAG). Vide = désactivé.
    router_model: str = ""
    router_timeout_seconds: float = 6.0
    # Confiance minimale pour refuser une question ; en deçà, elle passe.
    router_reject_confidence: float = 0.8
    # Nombre de messages d'historique transmis au routeur pour reformuler la question.
    router_history_messages: int = 4
    # Fiche de périmètre générée par `conference-tools build-kb` (noms, thématiques…).
    scope_file: str = ""
    # Développement : expose les décisions des garde-fous dans des en-têtes HTTP.
    debug_headers: bool = False
    # Développement : une ligne JSON par appel à /api/chat (question, garde-fous, réponse).
    # Vide = désactivé. Contient le texte des questions : ne pas activer en production.
    trace_file: str = ""

    # 0 = pas de limite en nombre : toute la conversation est transmise, dans la limite
    # de `max_history_chars` (les messages les plus anciens sont retirés au-delà).
    max_history_messages: int = 0
    max_history_chars: int = 60000
    # Dans la copie envoyée au LLM uniquement : remplace le JSON des cartes des anciennes
    # réponses par un repère court (l'affichage dans l'application n'est pas concerné).
    history_compact_cards: bool = True
    max_user_message_chars: int = 2000
    max_assistant_message_chars: int = 12000

    rate_limit_enabled: bool = True
    rate_limit_max_requests: int = 100
    rate_limit_window_seconds: int = 86400
    redis_rest_url: str | None = None
    redis_rest_token: str | None = None
    ip_hash_salt: str = ""

    cors_origins: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> Settings:
        base_url = os.getenv("LLM_BASE_URL", "").strip()
        api_key = os.getenv("LLM_API_KEY", "").strip()
        llm_kb_id = os.getenv("LLM_KB_ID", "").strip()
        model = os.getenv("LLM_MODEL", "").strip()
        ws_url = os.getenv("WS_URL", "").strip() or "wss://ws.generative-eu.engine.capgemini.com/"
        ws_provider = os.getenv("WS_PROVIDER", "").strip() or "bedrock"
        ws_workspace_id = os.getenv("WS_WORKSPACE_ID", "").strip()
        ws_doc_limit = _get_int("WS_DOC_LIMIT", 10)
        required = [("LLM_API_KEY", api_key), ("LLM_MODEL", model)]
        if not ws_workspace_id:
            # LLM_BASE_URL ne sert qu'au client HTTP compatible OpenAI.
            required.append(("LLM_BASE_URL", base_url))
        missing = [name for name, value in required if not value]
        if missing:
            raise ConfigError(f"Variables d'environnement manquantes : {', '.join(missing)}")

        if os.getenv("WS_HISTORY_IN", "text").strip().lower() not in {"", "text", "system"}:
            raise ConfigError("WS_HISTORY_IN doit valoir text ou system")

        reasoning_effort = os.getenv("LLM_REASONING_EFFORT", "").strip().lower() or None
        if reasoning_effort not in {None, "low", "medium", "high"}:
            raise ConfigError("LLM_REASONING_EFFORT doit valoir low, medium ou high")

        return cls(
            llm_base_url=base_url,
            llm_api_key=api_key,
            llm_model=model,
            llm_kb_id=llm_kb_id,
            ws_url=ws_url,
            ws_provider=ws_provider,
            ws_workspace_id=ws_workspace_id,
            ws_doc_limit=ws_doc_limit,
            ws_history_in=os.getenv("WS_HISTORY_IN", "").strip().lower() or "text",
            ws_debug_raw=_get_bool("WS_DEBUG_RAW", False),
            llm_temperature=_get_float("LLM_TEMPERATURE", 0.3),
            llm_max_tokens=_get_int("LLM_MAX_TOKENS", 2500),
            llm_timeout_seconds=_get_float("LLM_TIMEOUT_SECONDS", 45.0),
            llm_reasoning_effort=reasoning_effort,
            llm_extra_body=_get_json_object("LLM_EXTRA_BODY"),
            event_name=os.getenv("EVENT_NAME", "").strip() or "la conférence",
            event_timezone=os.getenv("EVENT_TIMEZONE", "").strip() or "Europe/Paris",
            event_fake_date=_get_date("EVENT_FAKE_DATE"),
            event_fake_now=_get_datetime("EVENT_FAKE_NOW"),
            planning_url=os.getenv("PLANNING_URL", "").strip(),
            planning_ttl_seconds=_get_float("PLANNING_TTL_SECONDS", 30.0),
            guard_enabled=_get_bool("GUARD_ENABLED", True),
            laya_model_dir=os.getenv("LAYA_MODEL_DIR", "").strip(),
            laya_threshold=_get_float("LAYA_THRESHOLD", 0.8),
            laya_threads=_get_int("LAYA_THREADS", 0),
            router_model=os.getenv("ROUTER_MODEL", "").strip(),
            router_timeout_seconds=_get_float("ROUTER_TIMEOUT_SECONDS", 6.0),
            router_reject_confidence=_get_float("ROUTER_REJECT_CONFIDENCE", 0.8),
            router_history_messages=_get_int("ROUTER_HISTORY_MESSAGES", 4),
            scope_file=os.getenv("SCOPE_FILE", "").strip(),
            debug_headers=_get_bool("DEBUG_HEADERS", False),
            trace_file=os.getenv("TRACE_FILE", "").strip(),
            max_history_messages=_get_int("MAX_HISTORY_MESSAGES", 0),
            max_history_chars=_get_int("MAX_HISTORY_CHARS", 60000),
            history_compact_cards=_get_bool("HISTORY_COMPACT_CARDS", True),
            max_user_message_chars=_get_int("MAX_USER_MESSAGE_CHARS", 2000),
            max_assistant_message_chars=_get_int("MAX_ASSISTANT_MESSAGE_CHARS", 12000),
            rate_limit_enabled=_get_bool("RATE_LIMIT_ENABLED", True),
            rate_limit_max_requests=_get_int("RATE_LIMIT_MAX_REQUESTS", 100),
            rate_limit_window_seconds=_get_int("RATE_LIMIT_WINDOW_SECONDS", 86400),
            # Noms posés par l'intégration Upstash de Vercel, ou noms Upstash natifs.
            redis_rest_url=_get_first("KV_REST_API_URL", "UPSTASH_REDIS_REST_URL"),
            redis_rest_token=_get_first("KV_REST_API_TOKEN", "UPSTASH_REDIS_REST_TOKEN"),
            ip_hash_salt=os.getenv("IP_HASH_SALT", ""),
            cors_origins=_get_list("CORS_ORIGINS"),
        )
