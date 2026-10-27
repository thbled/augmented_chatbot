from __future__ import annotations

import pytest

from chatbot_api.config import ConfigError, Settings

REQUIRED = {"LLM_BASE_URL": "http://llm.test/v1", "LLM_API_KEY": "k", "LLM_MODEL": "m"}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in [
        *REQUIRED,
        "RATE_LIMIT_ENABLED",
        "RATE_LIMIT_MAX_REQUESTS",
        "LLM_EXTRA_BODY",
        "LLM_REASONING_EFFORT",
        "KV_REST_API_URL",
        "UPSTASH_REDIS_REST_URL",
        "CORS_ORIGINS",
    ]:
        monkeypatch.delenv(name, raising=False)


def set_env(monkeypatch, **values):
    for name, value in {**REQUIRED, **values}.items():
        monkeypatch.setenv(name, value)


def test_defaults(monkeypatch):
    set_env(monkeypatch)
    settings = Settings.from_env()
    assert settings.rate_limit_enabled is True
    assert settings.rate_limit_max_requests == 100
    assert settings.rate_limit_window_seconds == 86400
    assert settings.llm_extra_body == {}


def test_missing_required(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "m")
    with pytest.raises(ConfigError, match="LLM_BASE_URL"):
        Settings.from_env()


def test_parses_values(monkeypatch):
    set_env(
        monkeypatch,
        RATE_LIMIT_ENABLED="false",
        LLM_EXTRA_BODY='{"files": []}',
        LLM_REASONING_EFFORT="HIGH",
        UPSTASH_REDIS_REST_URL="https://r.test",
        CORS_ORIGINS="https://a.test, https://b.test",
    )
    settings = Settings.from_env()
    assert settings.rate_limit_enabled is False
    assert settings.llm_extra_body == {"files": []}
    assert settings.llm_reasoning_effort == "high"
    assert settings.redis_rest_url == "https://r.test"
    assert settings.cors_origins == ["https://a.test", "https://b.test"]


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("LLM_EXTRA_BODY", "[1]"),
        ("LLM_EXTRA_BODY", "{oops"),
        ("RATE_LIMIT_MAX_REQUESTS", "beaucoup"),
        ("LLM_REASONING_EFFORT", "max"),
    ],
)
def test_invalid_values(monkeypatch, name, value):
    set_env(monkeypatch, **{name: value})
    with pytest.raises(ConfigError):
        Settings.from_env()
