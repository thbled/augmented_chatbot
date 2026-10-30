from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from openai import APITimeoutError

from chatbot_api.clock import EventClock
from chatbot_api.llm import LLMError, OpenAICompatibleClient
from chatbot_api.prompts import build_system_prompt
from chatbot_api.turn import TurnBuilder
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
NOW = datetime(2026, 11, 18, 8, 30, tzinfo=UTC)


@pytest.fixture
def turn(settings):
    return TurnBuilder(settings, EventClock(settings, now=lambda: NOW)).build(REQUEST)


def test_stream_reply_yields_content_only(settings, turn):
    completions = FakeCompletions(
        chunks=[
            chunk(None, reasoning_content="je réfléchis"),
            chunk("Ada "),
            SimpleNamespace(choices=[]),
            chunk("Lovelace"),
        ]
    )
    client = OpenAICompatibleClient(settings, client=fake_openai(completions))
    assert list(client.stream_reply(turn)) == ["Ada ", "Lovelace"]

    params = completions.params
    assert params["model"] == "test-model"
    assert params["stream"] is True
    assert params["messages"][0]["role"] == "system"
    assert params["messages"][0]["content"] == turn.system_prompt
    assert params["messages"][1]["role"] == "user"
    assert params["messages"][1]["content"].endswith("<question>\nQui est Ada ?\n</question>")
    assert "reasoning_effort" not in params
    assert "extra_body" not in params


def test_stream_reply_forwards_optional_params(settings, turn):
    completions = FakeCompletions()
    custom = replace(settings, llm_reasoning_effort="low", llm_extra_body={"files": [{"id": "kb"}]})
    list(OpenAICompatibleClient(custom, client=fake_openai(completions)).stream_reply(turn))
    assert completions.params["reasoning_effort"] == "low"
    assert completions.params["extra_body"] == {"files": [{"id": "kb"}]}


def test_stream_reply_maps_timeout(settings, turn):
    error = APITimeoutError(request=httpx.Request("POST", "http://llm.test"))
    client = OpenAICompatibleClient(settings, client=fake_openai(FakeCompletions(error=error)))
    with pytest.raises(LLMError) as exc:
        list(client.stream_reply(turn))
    assert exc.value.code == "llm_timeout"


def test_system_prompt_contains_context(settings):
    prompt = build_system_prompt(settings, "en", "Wednesday 18/11/2026 09:30", "- 09:00 Keynote")
    assert "Conf Test" in prompt
    assert "Wednesday 18/11/2026 09:30" in prompt
    assert "**anglais**" in prompt
    assert "- 09:00 Keynote" in prompt
    assert "```suggestions" in prompt
    assert "$" not in prompt


def test_system_prompt_without_planning(settings):
    prompt = build_system_prompt(settings, "fr", "mercredi 18/11/2026 09:30")
    assert "Aucun planning en direct" in prompt
