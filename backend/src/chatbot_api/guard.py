"""Garde-fou n°1 : filtre déterministe appliqué avant tout appel au LLM.

Il normalise la question (caractères invisibles, formes Unicode) et bloque les tentatives de
manipulation les plus courantes (contournement des règles, extraction du prompt, faux balisage
de rôles, charges encodées). Volontairement conservateur : les cas ambigus sont laissés au
prompt système et aux garde-fous suivants, pour ne pas refuser de questions légitimes.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass

# Caractères de largeur nulle et de contrôle de direction, souvent utilisés pour masquer du texte.
_INVISIBLE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff\u00ad]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_PATTERNS: dict[str, list[str]] = {
    "override": [
        # Le lookbehind évite « j'ignore les règles » (= je ne connais pas les règles).
        r"(?<![jJ]['’])(?<![jJ]e )\bignore[sz]?\b.{0,40}"
        r"\b(instructions?|r[eè]gles?|rules|prompts?|consignes?)\b",
        r"(?<![jJ]['’])\b(oublie[sz]?|forget|disregard)\b.{0,40}"
        r"\b(instructions?|r[eè]gles?|rules|consignes?)\b",
        r"\b(nouvelles?|new)\s+(instructions?|r[eè]gles?|rules)\s*:",
        r"\b(developer|d[ée]veloppeur|god|admin|debug)\s+mode\b",
        r"\bmode\s+(d[ée]veloppeur|admin|debug|sans\s+filtre)\b",
        r"\bjail\s?break",
        r"\b(act as|agis comme|tu es|you are)\s+(now\s+|maintenant\s+)?(un\s+|an?\s+)?DAN\b",
        r"\b(without|sans)\s+(any\s+|aucun\s+)?(filters?|filtres?|censure|censorship)\b",
    ],
    "prompt_leak": [
        r"\b(system|syst[eè]me)\s*prompt\b",
        r"\bprompt\s+(system|syst[eè]me|initial)\b",
        r"\b(r[ée]p[eè]te|repeat|print|affiche|show|reveal|r[ée]v[eè]le)\b.{0,40}"
        r"\b(instructions?|consignes?|above|ci-dessus|au-dessus|plus haut|initial|pr[ée]c[ée]dent)",
        r"\b(tes|your)\s+(instructions?|consignes?)\s+(initiales?|syst[eè]me|original)",
    ],
    "role_injection": [
        r"<\|?(im_start|im_end|system|assistant)\|?>",
        r"</?\s*(system|assistant|instructions?|question)\s*>",
        r"^\s*#{2,}\s*(system|instruction)",
        r"\[(INST|SYS)\]",
    ],
    "encoded_payload": [
        r"[A-Za-z0-9+/]{120,}={0,2}",
    ],
}

_COMPILED = {
    category: [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in patterns]
    for category, patterns in _PATTERNS.items()
}

REFUSALS = {
    "fr": (
        "Je ne peux pas donner suite à cette demande. Je suis là pour vous accompagner pendant "
        "l'événement : programme, speakers, partenaires, sujets abordés et informations pratiques."
    ),
    "en": (
        "I can't help with that request. I'm here to support you during the event: agenda, "
        "speakers, partners, topics and practical information."
    ),
}

OFF_TOPIC = {
    "fr": (
        "Cette question sort du cadre de l'événement. Je peux en revanche vous renseigner sur le "
        "programme, les speakers, les partenaires, les sujets abordés et les informations "
        "pratiques."
    ),
    "en": (
        "That question is outside the scope of the event. I can, however, help with the agenda, "
        "speakers, partners, topics and practical information."
    ),
}

REFUSAL_SUGGESTIONS = {
    "fr": [
        "Que se passe-t-il en ce moment ?",
        "Qui sont les speakers ?",
        "Quel est le programme ?",
    ],
    "en": ["What's happening right now?", "Who are the speakers?", "What's on the agenda?"],
}


@dataclass(frozen=True)
class GuardVerdict:
    allowed: bool
    category: str = ""


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = _INVISIBLE.sub("", text)
    return _CONTROL.sub("", text)


def inspect(text: str) -> GuardVerdict:
    for category, patterns in _COMPILED.items():
        if any(pattern.search(text) for pattern in patterns):
            return GuardVerdict(allowed=False, category=category)
    return GuardVerdict(allowed=True)


def refusal_message(locale: str, kind: str = "manipulation") -> str:
    """Refus poli et localisé, suivi de suggestions ; `kind` : manipulation ou off_topic."""
    texts = OFF_TOPIC if kind == "off_topic" else REFUSALS
    suggestions = json.dumps(
        REFUSAL_SUGGESTIONS.get(locale, REFUSAL_SUGGESTIONS["fr"]), ensure_ascii=False
    )
    return f"{texts.get(locale, texts['fr'])}\n\n```suggestions\n{suggestions}\n```"
