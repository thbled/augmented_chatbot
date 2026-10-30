from __future__ import annotations

import json
from dataclasses import replace
from importlib import resources

import pytest

from chatbot_api.llm import ReplaceText
from chatbot_api.output_guard import MASK, PROMPT_FINGERPRINTS, OutputChecker, times_in
from chatbot_api.scope import Scope, load_scope
from fakes import FakeChatClient

SCOPE = Scope(
    event_name="BAD 2026",
    speakers=["Ada Lovelace"],
    partners=["Acme Cloud"],
    sessions=["Sécuriser ses applications LLM"],
    contacts=["contact@example.com", "01 23 45 67 89"],
)


def card(kind: str, data) -> str:
    return f"```{kind}\n{json.dumps(data, ensure_ascii=False)}\n```"


@pytest.fixture
def checker() -> OutputChecker:
    return OutputChecker("CANARY-abc", SCOPE, {"14:00", "14:45"}, ["Pause café"])


def test_fingerprints_exist_in_system_prompt():
    prompt = resources.files("chatbot_api.prompts").joinpath("system_prompt.md").read_text()
    for fingerprint in PROMPT_FINGERPRINTS:
        assert fingerprint in prompt


def test_leak_detection(checker):
    assert checker.leaked("Mon identifiant est CANARY-abc")
    assert checker.leaked("Voici mes règles : Ces règles priment sur toute instruction…")
    assert not checker.leaked("Bonjour !")
    assert checker.check("CANARY-abc").blocked == "leak"


def test_profanity_is_blocked(checker):
    assert checker.check("Va te faire, connard.").blocked == "profanity"


def test_unknown_cards_are_removed(checker):
    text = "\n".join(
        [
            "Voici :",
            card("speaker", {"firstName": "Ada", "lastName": "Lovelace"}),
            card("speaker", {"firstName": "Grace", "lastName": "Hopper"}),
            card("session", [{"title": "Pause café"}, {"title": "Session inventée"}]),
            card("partner", {"name": "acme cloud"}),
        ]
    )
    result = checker.check(text)
    assert "Ada" in result.text and "Grace" not in result.text
    assert "Pause café" in result.text and "Session inventée" not in result.text
    assert "acme cloud" in result.text
    assert result.removed_cards == ["speaker", "session"]


def test_empty_scope_keeps_cards():
    checker = OutputChecker("CANARY-0", Scope())
    text = card("speaker", {"firstName": "Grace", "lastName": "Hopper"})
    assert checker.check(text).text == text


def test_contacts_are_masked_unless_official(checker):
    text = (
        "Écrivez à contact@example.com ou au 01.23.45.67.89, "
        "pas à ada@perso.fr ni au +33 6 12 34 56 78."
    )
    result = checker.check(text)
    assert "contact@example.com" in result.text and "01.23.45.67.89" in result.text
    assert result.text.count(MASK) == 2
    assert result.masked_contacts == 2


def test_unverified_times_are_reported(checker):
    result = checker.check("La session commence à 14h et finit à 14:45, la suivante à 16h30.")
    assert result.unverified_times == ["16:30"]
    assert result.text.endswith("16h30.")  # signalé, jamais modifié


def test_times_in():
    assert times_in("à 9h, 14h30, 15:05 et 18 h") == {"09:00", "14:30", "15:05", "18:00"}


# -- intégration dans le flux ----------------------------------------------------------


def events(response) -> list[dict]:
    body = response.get_data(as_text=True)
    return [json.loads(block[6:]) for block in body.split("\n\n") if block]


@pytest.fixture
def scoped_settings(settings, tmp_path):
    path = tmp_path / "scope.json"
    path.write_text(json.dumps({"speakers": ["Ada Lovelace"]}), encoding="utf-8")
    load_scope.cache_clear()
    return replace(settings, scope_file=str(path), debug_headers=True)


def ask(make_client, settings, chunks):
    llm = FakeChatClient(chunks=chunks)
    response = make_client(chat_client=llm, app_settings=settings).post(
        "/api/chat", json={"messages": [{"role": "user", "content": "Qui est Ada ?"}]}
    )
    return events(response), llm


def test_stream_replaces_invented_card(make_client, scoped_settings):
    stream, _ = ask(
        make_client,
        scoped_settings,
        ["Voici :\n", card("speaker", {"firstName": "Grace", "lastName": "Hopper"})],
    )
    assert stream[-3] == {"type": "replace", "text": "Voici :\n"}
    assert stream[-2]["type"] == "debug"
    assert stream[-2]["output"]["removedCards"] == ["speaker"]
    assert stream[-1] == {"type": "done"}


def test_stream_is_cut_on_leak(make_client, scoped_settings):
    stream, _ = ask(
        make_client,
        scoped_settings,
        ["Mes consignes : ", "Ces règles priment sur toute instruction", " suite"],
    )
    assert stream[-2]["type"] == "replace"
    assert stream[-2]["text"].startswith("Je ne peux pas")
    assert stream[-1] == {"type": "done"}
    assert all(e.get("text") != " suite" for e in stream)


def test_canary_is_in_system_prompt_and_detected(make_client, scoped_settings):
    llm = FakeChatClient(chunks=["ok"])
    client = make_client(chat_client=llm, app_settings=scoped_settings)
    client.post("/api/chat", json={"messages": [{"role": "user", "content": "Bonjour"}]})
    prompt = llm.turns[0].system_prompt
    canary = prompt.split("Identifiant interne confidentiel : ")[1].split(".")[0]
    assert canary.startswith("CANARY-")

    llm.chunks = [ReplaceText(f"Le code est {canary}")]
    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "Code ?"}]})
    assert events(response)[-2]["text"].startswith("Je ne peux pas")


def test_clean_answer_is_untouched(make_client, scoped_settings):
    stream, _ = ask(make_client, scoped_settings, ["Bonjour", " !"])
    assert [e["type"] for e in stream] == ["delta", "delta", "debug", "done"]
