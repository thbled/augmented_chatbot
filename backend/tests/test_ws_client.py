from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from chatbot_api import ws_client
from chatbot_api.clock import EventClock
from chatbot_api.llm import LLMError, ReplaceText
from chatbot_api.turn import TurnBuilder
from chatbot_api.validation import ChatMessage, ChatRequest
from chatbot_api.ws_client import TokenOrderer, WebSocketRagClient, strip_citations


def token(seq, value, run="r1"):
    return {"value": value, "sequenceNumber": seq, "runId": run}


def test_orderer_reorders_out_of_order_tokens():
    orderer = TokenOrderer()
    emitted = []
    for seq, value in [(0, "At 14:52, "), (2, "titled "), (1, "the program, "), (3, "ATLASSIAN")]:
        ready, reset = orderer.add(token(seq, value))
        assert not reset
        emitted += ready
    assert "".join(emitted) == "At 14:52, the program, titled ATLASSIAN"


def test_orderer_starts_at_one_and_waits_for_first_token():
    orderer = TokenOrderer()
    assert orderer.add(token(2, "b")) == ([], False)
    assert orderer.add(token(1, "a")) == (["a", "b"], False)


def test_orderer_without_sequence_numbers_keeps_arrival_order():
    orderer = TokenOrderer()
    assert orderer.add({"value": "x"}) == (["x"], False)
    assert orderer.add({"value": ""}) == ([], False)


def test_orderer_resets_on_new_run():
    orderer = TokenOrderer()
    orderer.add(token(0, "question reformulée"))
    assert orderer.add(token(0, "Réponse", run="r2")) == (["Réponse"], True)


def test_orderer_skips_persistent_gap():
    orderer = TokenOrderer()
    orderer.add(token(0, "a"))
    emitted = []
    for seq in range(2, 2 + ws_client.MAX_PENDING_TOKENS + 1):
        emitted += orderer.add(token(seq, str(seq)))[0]
    assert emitted[0] == "2"  # le token 1 n'est jamais arrivé : on reprend à 2


def test_strip_citations():
    assert (
        strip_citations("Session à 14h [Doc 1]. Salle A [Doc 2, 3].") == "Session à 14h. Salle A."
    )
    assert strip_citations("Titre « IA » [Doc") == "Titre « IA »"


class FakeSocket:
    def __init__(self, messages):
        self.messages = [json.dumps(m) for m in messages]
        self.sent = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def send(self, data):
        self.sent.append(json.loads(data))

    def recv(self, timeout=None):
        return self.messages.pop(0)


@pytest.fixture
def ws_settings(settings):
    return replace(settings, ws_workspace_id="ws-1", ws_url="wss://ws.test", ws_provider="bedrock")


def make_turn(settings, *messages):
    chat = ChatRequest([ChatMessage(role=r, content=c) for r, c in messages], "fr")
    clock = EventClock(settings, now=lambda: datetime(2026, 11, 18, 9, 0, tzinfo=UTC))
    return TurnBuilder(settings, clock).build(chat)


def run(monkeypatch, settings, messages, turn=None):
    socket = FakeSocket(messages)
    monkeypatch.setattr(ws_client, "connect", lambda *a, **k: socket)
    turn = turn or make_turn(settings, ("user", "Quoi de neuf ?"))
    return list(WebSocketRagClient(settings).stream_reply(turn)), socket


def test_stream_reorders_then_final_response_wins(monkeypatch, ws_settings):
    chunks, socket = run(
        monkeypatch,
        ws_settings,
        [
            {"action": "llm_new_token", "data": {"token": token(0, "Bon")}},
            {"action": "llm_new_token", "data": {"token": token(2, " !")}},
            {"action": "llm_new_token", "data": {"token": token(1, "jour")}},
            {"action": "heartbeat"},
            {"action": "final_response", "data": {"content": "Bonjour ! [Doc 1]"}},
        ],
    )
    assert chunks == ["Bon", "jour", " !", ReplaceText("Bonjour !")]
    payload = socket.sent[0]["data"]
    assert payload["workspaceId"] == "ws-1"
    assert payload["text"].endswith("<question>\nQuoi de neuf ?\n</question>")
    assert "Tu es l'assistant officiel" in payload["systemPrompt"]


def test_stream_error_is_masked(monkeypatch, ws_settings):
    with pytest.raises(LLMError) as exc:
        run(monkeypatch, ws_settings, [{"action": "error", "data": {"content": "détail interne"}}])
    assert exc.value.code == "llm_unavailable"


def test_history_placement(monkeypatch, ws_settings):
    history = (("user", "Qui est Ada ?"), ("assistant", "Une speaker."), ("user", "Et ensuite ?"))
    final = [{"action": "final_response", "data": {"content": "ok"}}]

    _, socket = run(monkeypatch, ws_settings, list(final), make_turn(ws_settings, *history))
    text = socket.sent[0]["data"]["text"]
    assert text.startswith("Historique de la conversation :\nUtilisateur : Qui est Ada ?")

    in_system = replace(ws_settings, ws_history_in="system")
    _, socket = run(monkeypatch, in_system, list(final), make_turn(in_system, *history))
    data = socket.sent[0]["data"]
    assert data["text"].startswith("[Heure locale du serveur")
    assert "# Historique de la conversation\nUtilisateur : Qui est Ada ?" in data["systemPrompt"]
