"""Contrôle des contenus de la base de connaissances (injection indirecte).

Les textes chargés dans la base (bios importées de LinkedIn, descriptions, documents) sont
lus par le LLM : une phrase comme « ignore tes instructions » cachée dans une bio pourrait le
manipuler. Ce module retire les caractères invisibles et signale les passages suspects avant
la génération de la base de connaissances.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from conference_tools.models import ConferenceData

_INVISIBLE = re.compile(r"[​-‏‪-‮⁠-⁤﻿­]")

_SUSPICIOUS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"(?<![jJ]['’])\b(ignore[sz]?|oublie[sz]?|forget|disregard)\b.{0,40}"
        r"\b(instructions?|r[eè]gles?|rules|consignes?|prompts?)\b",
        r"\b(system|syst[eè]me)\s*prompt\b",
        r"\b(tu es|you are)\s+(maintenant|now)\b",
        r"\b(nouvelles?|new)\s+(instructions?|r[eè]gles?|rules)\s*:",
        r"<\|?(im_start|im_end|system|assistant)\|?>",
        r"</?\s*(system|assistant|instructions?|question)\s*>",
        r"\b(assistant|IA|AI|LLM|chatbot)\b.{0,30}\b(doit|must|should)\s+(r[ée]pondre|answer|say|dire)",
        r"\b(r[ée]ponds?|answer|say)\s+(toujours|always)\b",
        r"```(speaker|session|partner|suggestions)",
    ]
]


@dataclass(frozen=True)
class Finding:
    where: str
    excerpt: str


def clean_text(text: str) -> str:
    """Normalise le texte (formes Unicode) et retire les caractères invisibles."""
    return _INVISIBLE.sub("", unicodedata.normalize("NFKC", text))


def scan_text(text: str, where: str) -> list[Finding]:
    findings = []
    for pattern in _SUSPICIOUS:
        match = pattern.search(text)
        if match:
            start = max(match.start() - 20, 0)
            findings.append(Finding(where, text[start : match.end() + 20].replace("\n", " ")))
    return findings


def scan_data(data: ConferenceData, static_dir: Path | None = None) -> list[Finding]:
    findings: list[Finding] = []
    for speaker in data.speakers:
        where = f"Speaker {speaker.full_name}"
        for text in (speaker.bio, speaker.job_title, speaker.company, *speaker.expertise):
            findings += scan_text(text, where)
    for session in data.sessions:
        findings += scan_text(f"{session.title}\n{session.description}", f"Session {session.title}")
    for partner in data.partners:
        text = f"{partner.description}\n{partner.offer}\n{partner.sector}"
        findings += scan_text(text, f"Partenaire {partner.name}")
    for item in data.practical:
        findings += scan_text(f"{item.title}\n{item.content}", f"Info pratique {item.title}")
    for label, value in data.event.fields.items():
        findings += scan_text(value, f"Événement : {label}")
    if static_dir and static_dir.is_dir():
        for path in sorted(static_dir.rglob("*.md")):
            if path.name.lower() != "readme.md":
                findings += scan_text(path.read_text(encoding="utf-8"), f"Document {path.name}")
    return findings
