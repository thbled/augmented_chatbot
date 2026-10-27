"""Configuration chargée depuis les variables d'environnement (et `.env` en local)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
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
    llm_timeout_seconds: float = 55.0
    llm_reasoning_effort: str | None = None
    llm_extra_body: dict[str, Any] = field(default_factory=dict)

    event_name: str = "la conférence"
    event_timezone: str = "Europe/Paris"

    max_history_messages: int = 12
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
        model = os.getenv("LLM_MODEL", "").strip()
        missing = [
            name
            for name, value in (
                ("LLM_BASE_URL", base_url),
                ("LLM_API_KEY", api_key),
                ("LLM_MODEL", model),
            )
            if not value
        ]
        if missing:
            raise ConfigError(f"Variables d'environnement manquantes : {', '.join(missing)}")

        reasoning_effort = os.getenv("LLM_REASONING_EFFORT", "").strip().lower() or None
        if reasoning_effort not in {None, "low", "medium", "high"}:
            raise ConfigError("LLM_REASONING_EFFORT doit valoir low, medium ou high")

        return cls(
            llm_base_url=base_url,
            llm_api_key=api_key,
            llm_model=model,
            llm_temperature=_get_float("LLM_TEMPERATURE", 0.3),
            llm_max_tokens=_get_int("LLM_MAX_TOKENS", 2500),
            llm_timeout_seconds=_get_float("LLM_TIMEOUT_SECONDS", 55.0),
            llm_reasoning_effort=reasoning_effort,
            llm_extra_body=_get_json_object("LLM_EXTRA_BODY"),
            event_name=os.getenv("EVENT_NAME", "").strip() or "la conférence",
            event_timezone=os.getenv("EVENT_TIMEZONE", "").strip() or "Europe/Paris",
            max_history_messages=_get_int("MAX_HISTORY_MESSAGES", 12),
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
