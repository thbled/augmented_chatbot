from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from openai import APITimeoutError

from chatbot_api.llm import LLMError, OpenAICompatibleClient
from chatbot_api.prompts import build_system_prompt
from chatbot_api.validation import ChatMessage, ChatRequest


def chunk(content: str | None, **delta_extra):
    delta = SimpleNamespace(content=content, **delta_extra)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


class FakeCompletions:
    def __init__(self, chunks=None, error: Exception | None = None) -> None:
        self.chunks = chunks or []
        self.error = error
        self.params: dict | None = None

    def create(self, **params):
        self.params = params
        if self.error:
            raise self.error
        return iter(self.chunks)


def fake_openai(completions: FakeCompletions):
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


REQUEST = ChatRequest(messages=[ChatMessage(role="user", content="Qui est Ada ?")], locale="en")


def test_stream_reply_yields_content_only(settings):
    completions = FakeCompletions(
        chunks=[
            chunk(None, reasoning_content="je réfléchis"),
            chunk("Ada "),
            SimpleNamespace(choices=[]),
            chunk("Lovelace"),
        ]
    )
    client = OpenAICompatibleClient(settings, client=fake_openai(completions))
    assert list(client.stream_reply(REQUEST)) == ["Ada ", "Lovelace"]

    params = completions.params
    assert params["model"] == "test-model"
    assert params["stream"] is True
    assert params["messages"][0]["role"] == "system"
    assert params["messages"][1:] == [{"role": "user", "content": "Qui est Ada ?"}]
    assert "reasoning_effort" not in params
    assert "extra_body" not in params


def test_stream_reply_forwards_optional_params(settings):
    completions = FakeCompletions()
    custom = replace(settings, llm_reasoning_effort="low", llm_extra_body={"files": [{"id": "kb"}]})
    list(OpenAICompatibleClient(custom, client=fake_openai(completions)).stream_reply(REQUEST))
    assert completions.params["reasoning_effort"] == "low"
    assert completions.params["extra_body"] == {"files": [{"id": "kb"}]}


def test_stream_reply_maps_timeout(settings):
    error = APITimeoutError(request=httpx.Request("POST", "http://llm.test"))
    client = OpenAICompatibleClient(settings, client=fake_openai(FakeCompletions(error=error)))
    with pytest.raises(LLMError) as exc:
        list(client.stream_reply(REQUEST))
    assert exc.value.code == "llm_timeout"


def test_system_prompt_contains_context(settings):
    now = datetime(2026, 11, 12, 8, 30, tzinfo=UTC)
    prompt = build_system_prompt(settings, "en", now=now)
    assert "Conf Test" in prompt
    assert "12/11/2026 09:30" in prompt  # converti en Europe/Paris
    assert "anglais" in prompt
    assert "```suggestions" in prompt
    assert "$" not in prompt
