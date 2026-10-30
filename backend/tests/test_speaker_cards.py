"""Ajout automatique des cartes de speakers absentes de la réponse du LLM."""

import json
import re

from chatbot_api.output_guard import OutputChecker
from chatbot_api.scope import Scope

ADA = {"id": "ada", "firstName": "Ada", "lastName": "Lovelace", "jobTitle": "CTO"}
ALAN = {"id": "alan", "firstName": "Alan", "lastName": "Turing"}
SCOPE = Scope(speakers=["Ada Lovelace", "Alan Turing"], speaker_cards=[ADA, ALAN])


def cards(text: str) -> list[dict]:
    found = []
    for body in re.findall(r"```speaker\n(.*?)\n```", text, re.DOTALL):
        data = json.loads(body)
        found += data if isinstance(data, list) else [data]
    return found


def test_markdown_list_becomes_cards():
    text = (
        "Voici les speakers :\n\n- Ada Lovelace (CTO)\n"
        "- **Alan Turing** — chercheur\n\nBonne visite."
    )
    result = OutputChecker("", SCOPE).check(text)
    assert [c["id"] for c in cards(result.text)] == ["ada", "alan"]
    assert "- Ada" not in result.text
    assert result.text.startswith("Voici les speakers :")
    assert result.text.rstrip().endswith("Bonne visite.")
    assert result.added_cards == ["ada lovelace", "alan turing"]


def test_existing_card_not_duplicated_and_prose_mention_added():
    text = f"Ada Lovelace ouvre la journée avec Alan Turing.\n\n```speaker\n{json.dumps(ADA)}\n```"
    result = OutputChecker("", SCOPE).check(text)
    assert sorted(c["id"] for c in cards(result.text)) == ["ada", "alan"]


def test_cards_inserted_before_suggestions():
    text = 'Parlez à Alan Turing.\n\n```suggestions\n["Qui est Ada ?"]\n```'
    result = OutputChecker("", SCOPE).check(text)
    assert result.text.index("```speaker") < result.text.index("```suggestions")
    assert [c["id"] for c in cards(result.text)] == ["alan"]  # Ada citée dans la suggestion


def test_no_cards_without_data():
    text = "- Ada Lovelace"
    assert OutputChecker("", Scope(speakers=["Ada Lovelace"])).check(text).text == text
