from __future__ import annotations

import json
from dataclasses import replace

from chatbot_api.llm import LLMError
from chatbot_api.rate_limit import MemoryRateLimiter
from fakes import FakeChatClient


def read_events(response) -> list[dict]:
    body = response.get_data(as_text=True)
    return [json.loads(block[len("data: ") :]) for block in body.split("\n\n") if block]


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_chat_streams_deltas_then_done(client, fake_client):
    response = client.post(
        "/api/chat", json={"messages": [{"role": "user", "content": "Salut"}], "locale": "fr"}
    )
    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"
    assert response.headers["Cache-Control"].startswith("no-cache")
    assert read_events(response) == [
        {"type": "delta", "text": "Bonjour"},
        {"type": "delta", "text": " !"},
        {"type": "done"},
    ]
    assert fake_client.requests[0].messages[0].content == "Salut"


def test_chat_rejects_invalid_payload(client):
    response = client.post("/api/chat", json={"messages": []})
    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid_messages"}


def test_chat_rejects_non_json(client):
    response = client.post("/api/chat", data="pas du json", content_type="text/plain")
    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid_payload"}


def test_chat_rejects_too_long_message(client):
    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "x" * 51}]})
    assert response.status_code == 400
    assert response.get_json() == {"error": "message_too_long"}


def test_chat_rejects_oversized_body(client):
    response = client.post(
        "/api/chat",
        data=json.dumps({"messages": [{"role": "user", "content": "x" * 300_000}]}),
        content_type="application/json",
    )
    assert response.status_code == 413
    assert response.get_json() == {"error": "payload_too_large"}


def test_chat_emits_error_event_when_llm_fails(make_client):
    failing = FakeChatClient(chunks=["Début"], error=LLMError("llm_timeout", "timeout"))
    response = make_client(chat_client=failing).post(
        "/api/chat", json={"messages": [{"role": "user", "content": "Salut"}]}
    )
    assert read_events(response) == [
        {"type": "delta", "text": "Début"},
        {"type": "error", "code": "llm_timeout"},
    ]


def test_chat_hides_unexpected_errors(make_client):
    failing = FakeChatClient(chunks=[], error=RuntimeError("secret detail"))
    response = make_client(chat_client=failing).post(
        "/api/chat", json={"messages": [{"role": "user", "content": "Salut"}]}
    )
    assert read_events(response) == [{"type": "error", "code": "internal_error"}]
    assert "secret" not in response.get_data(as_text=True)


def test_chat_rate_limit_per_ip(make_client):
    client = make_client(rate_limiter=MemoryRateLimiter(max_requests=2, window_seconds=60))
    body = {"messages": [{"role": "user", "content": "Salut"}]}
    headers_a = {"X-Real-IP": "10.0.0.1"}

    first = client.post("/api/chat", json=body, headers=headers_a)
    assert first.headers["X-RateLimit-Remaining"] == "1"
    assert client.post("/api/chat", json=body, headers=headers_a).status_code == 200

    blocked = client.post("/api/chat", json=body, headers=headers_a)
    assert blocked.status_code == 429
    assert blocked.get_json() == {"error": "rate_limited"}
    assert int(blocked.headers["Retry-After"]) > 0

    other_ip = client.post("/api/chat", json=body, headers={"X-Real-IP": "10.0.0.2"})
    assert other_ip.status_code == 200


def test_invalid_requests_do_not_consume_quota(make_client):
    client = make_client(rate_limiter=MemoryRateLimiter(max_requests=1, window_seconds=60))
    client.post("/api/chat", json={"messages": []})
    ok = client.post("/api/chat", json={"messages": [{"role": "user", "content": "Salut"}]})
    assert ok.status_code == 200


def test_cors_only_for_allowed_origins(make_client, settings):
    client = make_client(app_settings=replace(settings, cors_origins=["https://ok.test"]))
    allowed = client.get("/api/health", headers={"Origin": "https://ok.test"})
    assert allowed.headers["Access-Control-Allow-Origin"] == "https://ok.test"
    denied = client.get("/api/health", headers={"Origin": "https://evil.test"})
    assert "Access-Control-Allow-Origin" not in denied.headers
