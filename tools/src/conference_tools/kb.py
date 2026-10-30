"""Génération de la base de connaissances (documents Markdown) à partir des données.

Chaque élément (speaker, session, partenaire) fait l'objet d'un document autonome :
une partie rédigée, riche en contexte pour la recherche sémantique, suivie du bloc de
carte (JSON compact) que le LLM recopie tel quel dans ses réponses.
"""

from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from conference_tools.models import ConferenceData, Partner, Session, Speaker

WEEKDAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MONTHS = [
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
]

CARD_NOTE = "Fiche à recopier telle quelle (bloc complet) pour afficher la carte dans la réponse :"


def format_day(day: date) -> str:
    return f"{WEEKDAYS[day.weekday()]} {day.day} {MONTHS[day.month - 1]} {day.year}"


def card_block(kind: str, card: dict[str, Any]) -> str:
    payload = json.dumps(card, ensure_ascii=False, separators=(",", ":"))
    return f"```{kind}\n{payload}\n```"


def _event_label(data: ConferenceData) -> str:
    return data.event.name or "l'événement"


def _session_line(session: Session) -> str:
    parts = [
        f"{format_day(session.day)}, {session.start_label}–{session.end_label}",
        f"« {session.title} »",
    ]
    if session.format:
        parts.append(f"({session.format})")
    if session.room:
        parts.append(f"— {session.room}")
    return " ".join(parts)


def _speaker_names(session: Session) -> str:
    return ", ".join(
        entry.name if not entry.speaker else entry.speaker.full_name for entry in session.speakers
    )


def speaker_document(speaker: Speaker, data: ConferenceData) -> str:
    role = ", ".join(part for part in (speaker.job_title, speaker.company) if part)
    lines = [f"# Speaker : {speaker.full_name}" + (f" — {role}" if role else ""), ""]
    intro = f"{speaker.full_name} intervient à {_event_label(data)}."
    if role:
        intro = f"{speaker.full_name} ({role}) intervient à {_event_label(data)}."
    lines += [intro, ""]
    if speaker.bio:
        lines += ["## Biographie", "", speaker.bio, ""]
    if speaker.expertise:
        lines += ["## Expertises", "", *(f"- {item}" for item in speaker.expertise), ""]
    if speaker.sessions:
        lines += ["## Interventions", ""]
        for session in speaker.sessions:
            others = [
                entry.speaker.full_name if entry.speaker else entry.name
                for entry in session.speakers
                if entry.speaker is not speaker
            ]
            suffix = f", avec {', '.join(others)}" if others else ""
            lines.append(f"- {_session_line(session)}{suffix}")
        lines.append("")
    if speaker.linkedin_url:
        lines += ["## Profil LinkedIn", "", speaker.linkedin_url, ""]
    lines += ["## Fiche", "", CARD_NOTE, "", card_block("speaker", speaker.to_card()), ""]
    return "\n".join(lines)


def session_document(session: Session, data: ConferenceData) -> str:
    lines = [f"# Session : {session.title}", ""]
    details = [
        f"- **Date** : {format_day(session.day)}",
        f"- **Horaire** : {session.start_label} – {session.end_label}",
    ]
    if session.room:
        details.append(f"- **Salle** : {session.room}")
    if session.format:
        details.append(f"- **Format** : {session.format}")
    if session.track:
        details.append(f"- **Thématique** : {session.track}")
    if session.language:
        details.append(f"- **Langue** : {session.language}")
    if session.speakers:
        details.append(f"- **Speakers** : {_speaker_names(session)}")
    if session.tags:
        details.append(f"- **Mots-clés** : {', '.join(session.tags)}")
    lines += [f"Session du programme de {_event_label(data)}.", "", *details, ""]
    if session.description:
        lines += ["## Description", "", session.description, ""]

    published = [e.speaker for e in session.speakers if e.is_published and e.speaker]
    if published:
        lines += ["## Les intervenants", ""]
        for speaker in published:
            role = ", ".join(part for part in (speaker.job_title, speaker.company) if part)
            expertise = (
                f" Expertises : {', '.join(speaker.expertise)}." if speaker.expertise else ""
            )
            lines.append(
                f"- **{speaker.full_name}**" + (f" — {role}." if role else ".") + expertise
            )
        lines.append("")
    lines += ["## Fiche", "", CARD_NOTE, "", card_block("session", session.to_card()), ""]
    return "\n".join(lines)


def partner_document(partner: Partner, data: ConferenceData) -> str:
    lines = [f"# Partenaire : {partner.name}", ""]
    intro = f"{partner.name} est partenaire de {_event_label(data)}"
    intro += f" (niveau {partner.tier})." if partner.tier else "."
    lines += [intro, ""]
    details = []
    if partner.sector:
        details.append(f"- **Secteur** : {partner.sector}")
    if partner.booth:
        details.append(f"- **Stand** : {partner.booth}")
    if partner.website_url:
        details.append(f"- **Site web** : {partner.website_url}")
    if details:
        lines += [*details, ""]
    if partner.description:
        lines += ["## Présentation", "", partner.description, ""]
    if partner.offer:
        lines += ["## Offre et solutions", "", partner.offer, ""]
    lines += ["## Fiche", "", CARD_NOTE, "", card_block("partner", partner.to_card()), ""]
    return "\n".join(lines)


def program_overview(data: ConferenceData) -> str:
    lines = [f"# Programme complet de {_event_label(data)}", ""]
    lines += [
        "Vue d'ensemble chronologique de toutes les sessions. Le détail de chaque session "
        "(description, speakers, fiche) figure dans son document dédié.",
        "",
    ]
    by_day: dict[date, list[Session]] = defaultdict(list)
    for session in data.sessions:
        by_day[session.day].append(session)
    for day in sorted(by_day):
        lines += [f"## Programme du {format_day(day)}", ""]
        lines += ["| Horaire | Session | Format | Salle | Speakers |", "|---|---|---|---|---|"]
        for s in by_day[day]:
            hours = f"{s.start_label}–{s.end_label}"
            cells = [hours, s.title, s.format, s.room, _speaker_names(s)]
            lines.append("| " + " | ".join(cell.replace("|", "/") for cell in cells) + " |")
        lines.append("")

    tracks: dict[str, list[Session]] = defaultdict(list)
    for session in data.sessions:
        if session.track:
            tracks[session.track].append(session)
    if tracks:
        lines += ["## Sessions par thématique", ""]
        for track in sorted(tracks):
            lines += [f"### {track}", "", *(f"- {_session_line(s)}" for s in tracks[track]), ""]
    return "\n".join(lines)


def speakers_overview(data: ConferenceData) -> str:
    lines = [f"# Liste des speakers de {_event_label(data)}", ""]
    lines += [
        "Pour présenter la liste, joindre la fiche `speaker` de chaque intervenant cité "
        "(bloc ci-dessous), plutôt qu'une liste en texte.",
        "",
    ]
    published = sorted(data.speakers, key=lambda s: s.last_name.lower())
    for speaker in published:
        role = ", ".join(part for part in (speaker.job_title, speaker.company) if part)
        expertise = f" — {', '.join(speaker.expertise)}" if speaker.expertise else ""
        lines.append(f"- **{speaker.full_name}**" + (f" ({role})" if role else "") + expertise)
    lines += ["", "## Fiches", "", CARD_NOTE, ""]
    lines += [card_block("speaker", s.to_card()) for s in published]
    lines.append("")
    return "\n".join(lines)


def partners_overview(data: ConferenceData) -> str:
    lines = [f"# Partenaires de {_event_label(data)}", ""]
    by_tier: dict[str, list[Partner]] = defaultdict(list)
    for partner in data.partners:
        by_tier[partner.tier or "Partenaire"].append(partner)
    for tier, partners in by_tier.items():
        lines += [f"## {tier}", ""]
        for partner in partners:
            sector = f" — {partner.sector}" if partner.sector else ""
            booth = f" (stand {partner.booth})" if partner.booth else ""
            lines.append(f"- **{partner.name}**{sector}{booth}")
        lines.append("")
    return "\n".join(lines)


def event_document(data: ConferenceData) -> str:
    lines = [f"# À propos de {_event_label(data)}", ""]
    for label, value in data.event.fields.items():
        lines.append(f"- **{label}** : {value}")
    if data.sessions:
        days = sorted({s.day for s in data.sessions})
        lines.append(f"- **Jours de programme** : {', '.join(format_day(d) for d in days)}")
    lines += [
        f"- **Nombre de sessions** : {len(data.sessions)}",
        f"- **Nombre de speakers** : {len(data.speakers)}",
        f"- **Nombre de partenaires** : {len(data.partners)}",
        "",
    ]
    return "\n".join(lines)


def practical_document(data: ConferenceData) -> str:
    lines = [f"# Informations pratiques — {_event_label(data)}", ""]
    by_category: dict[str, list] = defaultdict(list)
    for item in data.practical:
        by_category[item.category].append(item)
    for category, items in by_category.items():
        lines += [f"## {category}", ""]
        for item in items:
            lines += [f"### {item.title}", "", item.content, ""]
    return "\n".join(lines)


def build_knowledge_base(
    data: ConferenceData, out_dir: Path, static_dir: Path | None = None
) -> list[Path]:
    """Écrit la base de connaissances dans `out_dir` (vidé au préalable) et liste les fichiers."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    written: list[Path] = []

    def write(relative: str, content: str) -> None:
        path = out_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(path)

    write("evenement.md", event_document(data))
    if data.sessions:
        write("programme.md", program_overview(data))
    if data.speakers:
        write("speakers.md", speakers_overview(data))
    if data.partners:
        write("partenaires.md", partners_overview(data))
    if data.practical:
        write("infos_pratiques.md", practical_document(data))

    # Le consentement ne restreint que l'enrichissement automatique : tous publiés.
    for speaker in data.speakers:
        write(f"speakers/speaker_{speaker.id}.md", speaker_document(speaker, data))
    for session in data.sessions:
        write(f"sessions/session_{session.id}.md", session_document(session, data))
    for partner in data.partners:
        write(f"partenaires/partenaire_{partner.id}.md", partner_document(partner, data))

    if static_dir and static_dir.is_dir():
        for source in sorted(static_dir.rglob("*.md")):
            if source.name.lower() == "readme.md":
                continue
            write(str(source.relative_to(static_dir)), source.read_text(encoding="utf-8"))
    return written


_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?:\+\d{2,3}[\s.-]?|\b0)[1-9](?:[\s.-]?\d{2}){4}\b")


def official_contacts(data: ConferenceData) -> list[str]:
    """E-mails et téléphones publiés par l'organisation : les seuls que l'assistant peut citer."""
    texts = [*data.event.fields.values()]
    texts += [f"{i.title} {i.content}" for i in data.practical]
    texts += [f"{p.description} {p.offer}" for p in data.partners]
    found: list[str] = []
    for text in texts:
        found += _EMAIL.findall(text) + _PHONE.findall(text)
    return list(dict.fromkeys(c.strip() for c in found))


def build_scope(data: ConferenceData) -> dict[str, Any]:
    """Fiche de périmètre pour le routeur du backend : noms et thématiques de l'événement.

    Les noms des speakers sans consentement figurent aussi dans le programme public : ils
    sont inclus (nom seul), pour qu'une question à leur sujet ne soit pas refusée.
    """
    themes = data.event.fields.get("Thématiques", "")
    speakers = {s.full_name for s in data.speakers}
    for session in data.sessions:
        speakers.update(entry.name for entry in session.speakers if not entry.speaker)
    return {
        "eventName": data.event.name,
        "themes": [t.strip() for t in themes.split(";") if t.strip()],
        "speakers": sorted(speakers),
        "partners": [p.name for p in data.partners],
        "sessions": [s.title for s in data.sessions],
        "contacts": official_contacts(data),
        # Fiches des speakers : le backend les joint quand le LLM cite un nom sans sa carte.
        "speakerCards": [s.to_card() for s in data.speakers],
    }


def write_scope(data: ConferenceData, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_scope(data), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path
