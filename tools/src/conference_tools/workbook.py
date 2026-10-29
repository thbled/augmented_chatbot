"""Modèle Excel de saisie des données de la conférence : création et lecture."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

from conference_tools.models import (
    ConferenceData,
    EventInfo,
    Partner,
    PracticalInfo,
    Session,
    SessionSpeaker,
    Speaker,
    slugify,
)

SHEET_INSTRUCTIONS = "Instructions"
SHEET_EVENT = "Événement"
SHEET_SPEAKERS = "Speakers"
SHEET_PROGRAM = "Programme"
SHEET_PARTNERS = "Partenaires"
SHEET_PRACTICAL = "Infos pratiques"

LIST_SEPARATOR = ";"
MAX_ROWS = 500

YES_NO = ["Oui", "Non"]
SESSION_FORMATS = [
    "Keynote",
    "Conférence",
    "Table ronde",
    "Atelier",
    "Démo",
    "Pitch",
    "Pause",
    "Networking",
    "Accueil",
]
SESSION_LANGUAGES = ["FR", "EN", "FR/EN"]
PARTNER_TIERS = ["Platinum", "Gold", "Silver", "Bronze", "Partenaire", "Exposant", "Média"]
PRACTICAL_CATEGORIES = [
    "Accès",
    "Horaires",
    "Accueil",
    "Restauration",
    "Wi-Fi",
    "Accessibilité",
    "Vestiaire",
    "Contact",
    "Sécurité",
    "Divers",
]

EVENT_FIELDS: list[tuple[str, str]] = [
    ("Nom de l'événement", "Nom affiché par l'assistant."),
    ("Édition / thème", "Thème de l'édition, slogan."),
    ("Dates", "Ex. : 12 et 13 novembre 2026."),
    ("Lieu", "Nom du lieu."),
    ("Adresse", "Adresse complète."),
    ("Site web", "URL du site officiel."),
    ("Organisateur", "Entité organisatrice."),
    ("Contact", "E-mail ou téléphone de l'accueil."),
    ("Description", "Présentation de l'événement en quelques phrases (public, objectifs)."),
    ("Thématiques", "Grandes thématiques traitées, séparées par ;"),
    ("Réseaux sociaux / hashtag", "Ex. : #MaConf2026"),
]


@dataclass(frozen=True)
class Column:
    key: str
    header: str
    help: str
    width: int = 20
    required: bool = False
    choices: list[str] | None = None
    kind: str = "text"  # text | list | date | time | url

    @property
    def label(self) -> str:
        return f"{self.header} *" if self.required else self.header


SPEAKER_COLUMNS = [
    Column(
        "id",
        "Identifiant",
        "Optionnel. Généré automatiquement (prenom-nom). À renseigner seulement pour "
        "distinguer deux homonymes.",
        16,
    ),
    Column("first_name", "Prénom", "Prénom du speaker.", 16, required=True),
    Column("last_name", "Nom", "Nom du speaker.", 18, required=True),
    Column(
        "linkedin_url",
        "URL LinkedIn",
        "Ex. : https://www.linkedin.com/in/identifiant",
        36,
        kind="url",
    ),
    Column(
        "consent",
        "Consentement",
        "Oui = autorisation écrite reçue d'utiliser et publier les informations du profil "
        "(bio, photo, LinkedIn). Sans « Oui », seul le nom apparaît dans le programme.",
        14,
        required=True,
        choices=YES_NO,
    ),
    Column(
        "consent_date",
        "Date du consentement",
        "Date de réception de l'autorisation (traçabilité RGPD).",
        14,
        kind="date",
    ),
    Column(
        "photo_url",
        "URL photo",
        "URL https de la photo, ou chemin relatif à l'application "
        "(ex. /images/speakers/ada-lovelace.jpg). Format carré conseillé, 400×400 px minimum.",
        36,
        kind="url",
    ),
    Column("company", "Entreprise", "Entreprise ou organisation actuelle.", 22),
    Column("job_title", "Poste", "Intitulé du poste actuel.", 26),
    Column(
        "bio",
        "Biographie",
        "Bio professionnelle à la 3e personne, 400 à 900 caractères : parcours, réalisations, "
        "sujets de prédilection.",
        60,
    ),
    Column(
        "expertise",
        "Expertises",
        "3 à 6 domaines d'expertise séparés par ; (ex. : IA générative; MLOps; Cloud)",
        36,
        kind="list",
    ),
]

PROGRAM_COLUMNS = [
    Column("id", "Identifiant", "Optionnel. Généré automatiquement à partir du titre.", 16),
    Column("day", "Date", "Date de la session (JJ/MM/AAAA).", 12, required=True, kind="date"),
    Column("start", "Début", "Heure de début (HH:MM).", 9, required=True, kind="time"),
    Column("end", "Fin", "Heure de fin (HH:MM).", 9, required=True, kind="time"),
    Column("title", "Titre", "Titre de la session.", 40, required=True),
    Column("format", "Format", "Type de session.", 14, choices=SESSION_FORMATS),
    Column("room", "Salle", "Salle ou espace.", 14),
    Column("track", "Thématique", "Parcours ou thématique principale.", 20),
    Column(
        "speakers",
        "Speakers",
        "Intervenants séparés par ; — « Prénom Nom » ou identifiant de l'onglet Speakers.",
        30,
        kind="list",
    ),
    Column(
        "description",
        "Description",
        "Résumé de la session : sujet, enjeux, ce que le public va apprendre.",
        60,
    ),
    Column(
        "tags",
        "Mots-clés",
        "Mots-clés séparés par ; (facilitent les recommandations).",
        30,
        kind="list",
    ),
    Column("language", "Langue", "Langue de la session.", 9, choices=SESSION_LANGUAGES),
]

PARTNER_COLUMNS = [
    Column("id", "Identifiant", "Optionnel. Généré automatiquement à partir du nom.", 16),
    Column("name", "Nom", "Nom de l'entreprise.", 22, required=True),
    Column("tier", "Niveau", "Niveau de partenariat.", 12, choices=PARTNER_TIERS),
    Column(
        "logo_url",
        "URL logo",
        "URL https du logo, ou chemin relatif (ex. /images/partners/acme.svg). "
        "Fond transparent conseillé.",
        34,
        kind="url",
    ),
    Column("website_url", "Site web", "URL du site de l'entreprise.", 30, kind="url"),
    Column("sector", "Secteur d'activité", "Ex. : Cybersécurité, Conseil, Cloud…", 22),
    Column("description", "Présentation", "Présentation de l'entreprise (300 à 800 car.).", 60),
    Column(
        "offer",
        "Offre / solutions",
        "Produits, services ou offres mis en avant pendant l'événement.",
        40,
    ),
    Column("booth", "Stand", "Numéro ou emplacement du stand.", 10),
]

PRACTICAL_COLUMNS = [
    Column(
        "category",
        "Catégorie",
        "Thème de l'information.",
        16,
        required=True,
        choices=PRACTICAL_CATEGORIES,
    ),
    Column("title", "Question / titre", "Ex. : Comment venir en transports ?", 36, required=True),
    Column("content", "Réponse", "Réponse complète et autonome.", 70, required=True),
]

SHEET_COLUMNS: dict[str, list[Column]] = {
    SHEET_SPEAKERS: SPEAKER_COLUMNS,
    SHEET_PROGRAM: PROGRAM_COLUMNS,
    SHEET_PARTNERS: PARTNER_COLUMNS,
    SHEET_PRACTICAL: PRACTICAL_COLUMNS,
}

EXAMPLE_EVENT = {
    "Nom de l'événement": "Business Agility Days 2026",
    "Édition / thème": "L'IA au service de l'entreprise",
    "Dates": "12 novembre 2026",
    "Lieu": "Centre des congrès",
    "Adresse": "1 place de l'Exemple, 75000 Paris",
    "Site web": "https://www.example.com",
    "Organisateur": "Association Exemple",
    "Contact": "contact@example.com",
    "Description": "Une journée de conférences et d'ateliers pour les décideurs et experts "
    "techniques autour de l'IA, de la data et du cloud.",
    "Thématiques": "IA générative; Data; Cloud; Cybersécurité",
    "Réseaux sociaux / hashtag": "#TechSummit2026",
}

EXAMPLE_ROWS: dict[str, list[dict[str, Any]]] = {
    SHEET_SPEAKERS: [
        {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "linkedin_url": "https://www.linkedin.com/in/exemple-ada",
            "consent": "Oui",
            "consent_date": date(2026, 9, 1),
            "photo_url": "/images/speakers/ada-lovelace.jpg",
            "company": "Analytical Engines",
            "job_title": "Directrice scientifique",
            "bio": "Ada Lovelace dirige la recherche d'Analytical Engines, où elle conçoit des "
            "algorithmes d'IA appliqués à l'industrie. Pionnière de la programmation, elle "
            "intervient régulièrement sur l'éthique et la gouvernance des modèles.",
            "expertise": "IA générative; Algorithmique; Gouvernance de l'IA",
        },
        {
            "first_name": "Alan",
            "last_name": "Turing",
            "linkedin_url": "https://www.linkedin.com/in/exemple-alan",
            "consent": "Oui",
            "consent_date": date(2026, 9, 3),
            "photo_url": "",
            "company": "Bletchley Labs",
            "job_title": "Responsable sécurité",
            "bio": "Alan Turing pilote la cybersécurité de Bletchley Labs. Spécialiste de la "
            "cryptographie, il accompagne les entreprises dans la sécurisation de leurs "
            "systèmes d'IA.",
            "expertise": "Cybersécurité; Cryptographie; Sécurité des LLM",
        },
    ],
    SHEET_PROGRAM: [
        {
            "day": date(2026, 11, 12),
            "start": time(9, 0),
            "end": time(9, 30),
            "title": "Accueil café",
            "format": "Accueil",
            "room": "Hall",
        },
        {
            "day": date(2026, 11, 12),
            "start": time(9, 30),
            "end": time(10, 15),
            "title": "L'IA générative en entreprise : du prototype à la production",
            "format": "Keynote",
            "room": "Amphi A",
            "track": "IA générative",
            "speakers": "Ada Lovelace",
            "description": "Retour d'expérience sur l'industrialisation de cas d'usage d'IA "
            "générative : choix des modèles, évaluation, coûts et gouvernance.",
            "tags": "LLM; MLOps; Gouvernance",
            "language": "FR",
        },
        {
            "day": date(2026, 11, 12),
            "start": time(10, 30),
            "end": time(11, 15),
            "title": "Sécuriser ses applications LLM",
            "format": "Conférence",
            "room": "Salle 2",
            "track": "Cybersécurité",
            "speakers": "Alan Turing; Ada Lovelace",
            "description": "Injection de prompt, fuite de données, empoisonnement : panorama "
            "des menaces et bonnes pratiques de défense.",
            "tags": "Sécurité; LLM; RAG",
            "language": "FR",
        },
    ],
    SHEET_PARTNERS: [
        {
            "name": "Acme Cloud",
            "tier": "Gold",
            "logo_url": "/images/partners/acme-cloud.svg",
            "website_url": "https://www.example.com",
            "sector": "Cloud souverain",
            "description": "Acme Cloud propose une infrastructure cloud souveraine pour "
            "héberger les applications critiques et les modèles d'IA des entreprises.",
            "offer": "Hébergement GPU, plateforme MLOps managée",
            "booth": "B12",
        }
    ],
    SHEET_PRACTICAL: [
        {
            "category": "Accès",
            "title": "Comment venir ?",
            "content": "Métro ligne 1, station Exemple (5 minutes à pied). Parking payant "
            "sur place.",
        },
        {
            "category": "Wi-Fi",
            "title": "Quel est le Wi-Fi ?",
            "content": "Réseau « TechSummit-Guest », sans mot de passe.",
        },
    ],
}

INSTRUCTIONS = [
    "Modèle de données de la conférence",
    "",
    "Ce classeur alimente la base de connaissances de l'assistant. Une ligne = un élément.",
    "Les colonnes marquées * sont obligatoires. Survolez un en-tête pour afficher l'aide.",
    "Les lignes d'exemple sont à remplacer par vos données.",
    "",
    "Onglets :",
    "• Événement : informations générales (une valeur par ligne).",
    "• Speakers : un intervenant par ligne. Le consentement « Oui » est requis pour publier "
    "la bio, la photo et le lien LinkedIn.",
    "• Programme : une session par ligne. Colonne Speakers : « Prénom Nom » séparés par ;.",
    "• Partenaires : une entreprise par ligne.",
    "• Infos pratiques : une question / réponse par ligne.",
    "",
    "Listes : séparer les valeurs par un point-virgule (;).",
    "Dates : JJ/MM/AAAA. Heures : HH:MM.",
    "Images : URL https, ou fichier déposé dans frontend/public/images/… et référencé par "
    "un chemin commençant par /images/.",
    "",
    "Ensuite :",
    "1. (optionnel) Pré-remplir les speakers depuis les PDF LinkedIn : "
    "uv run conference-tools linkedin-import <classeur> --pdf-dir <dossier>",
    "2. Vérifier : uv run conference-tools validate <classeur>",
    "3. Générer la base de connaissances : uv run conference-tools build-kb <classeur> --out kb",
    "4. Charger le contenu du dossier kb dans la base de connaissances du serveur LLM.",
]

HEADER_FILL = PatternFill("solid", fgColor="1F2A44")
HEADER_FONT = Font(bold=True, color="FFFFFF")
REQUIRED_FILL = PatternFill("solid", fgColor="3B4A7A")


def _style_header(ws: Worksheet, columns: list[Column]) -> None:
    for index, column in enumerate(columns, start=1):
        cell = ws.cell(row=1, column=index, value=column.label)
        cell.font = HEADER_FONT
        cell.fill = REQUIRED_FILL if column.required else HEADER_FILL
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        cell.comment = Comment(column.help, "Modèle")
        ws.column_dimensions[get_column_letter(index)].width = column.width
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(columns))}1"


def _add_validations(ws: Worksheet, columns: list[Column]) -> None:
    for index, column in enumerate(columns, start=1):
        letter = get_column_letter(index)
        cell_range = f"{letter}2:{letter}{MAX_ROWS}"
        validation: DataValidation | None = None
        if column.choices:
            validation = DataValidation(
                type="list", formula1=f'"{",".join(column.choices)}"', allow_blank=True
            )
            validation.error = "Choisissez une valeur dans la liste."
        elif column.kind == "date":
            validation = DataValidation(type="date", operator="greaterThan", formula1="36526")
            validation.error = "Saisissez une date (JJ/MM/AAAA)."
            for row in range(2, MAX_ROWS + 1):
                ws[f"{letter}{row}"].number_format = "DD/MM/YYYY"
        elif column.kind == "time":
            validation = DataValidation(
                type="time", operator="between", formula1="0", formula2="0.999988"
            )
            validation.error = "Saisissez une heure (HH:MM)."
            for row in range(2, MAX_ROWS + 1):
                ws[f"{letter}{row}"].number_format = "HH:MM"
        if validation:
            validation.showErrorMessage = True
            validation.add(cell_range)
            ws.add_data_validation(validation)
        if not column.choices and column.kind == "text" and column.width >= 40:
            for row in range(2, MAX_ROWS + 1):
                ws[f"{letter}{row}"].alignment = Alignment(wrap_text=True, vertical="top")


def create_template(path: Path, with_examples: bool = True) -> None:
    workbook = Workbook()
    instructions = workbook.active
    instructions.title = SHEET_INSTRUCTIONS
    instructions.column_dimensions["A"].width = 110
    for row, line in enumerate(INSTRUCTIONS, start=1):
        cell = instructions.cell(row=row, column=1, value=line)
        cell.alignment = Alignment(wrap_text=True)
    instructions["A1"].font = Font(bold=True, size=14)

    event = workbook.create_sheet(SHEET_EVENT)
    event.append(["Champ", "Valeur"])
    for index in (1, 2):
        event.cell(row=1, column=index).font = HEADER_FONT
        event.cell(row=1, column=index).fill = HEADER_FILL
    event.column_dimensions["A"].width = 28
    event.column_dimensions["B"].width = 90
    for row, (label, help_text) in enumerate(EVENT_FIELDS, start=2):
        label_cell = event.cell(row=row, column=1, value=label)
        label_cell.comment = Comment(help_text, "Modèle")
        label_cell.font = Font(bold=True)
        value = EXAMPLE_EVENT.get(label, "") if with_examples else ""
        event.cell(row=row, column=2, value=value).alignment = Alignment(wrap_text=True)

    for sheet_name, columns in SHEET_COLUMNS.items():
        ws = workbook.create_sheet(sheet_name)
        _style_header(ws, columns)
        _add_validations(ws, columns)
        if with_examples:
            for row_index, row in enumerate(EXAMPLE_ROWS[sheet_name], start=2):
                for col_index, column in enumerate(columns, start=1):
                    value = row.get(column.key)
                    if value not in (None, ""):
                        ws.cell(row=row_index, column=col_index, value=value)

    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


# --------------------------------------------------------------------------- lecture


class WorkbookError(ValueError):
    """Classeur illisible ou non conforme au modèle."""


@dataclass
class ReadReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return " ".join(str(value).split()) if not isinstance(value, str) else value.strip()


def _split_list(value: Any) -> list[str]:
    return [item.strip() for item in cell_text(value).split(LIST_SEPARATOR) if item.strip()]


def parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = cell_text(value)
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_time(value: Any) -> time | None:
    if isinstance(value, datetime):
        return value.time().replace(second=0, microsecond=0)
    if isinstance(value, time):
        return value.replace(second=0, microsecond=0)
    match = re.fullmatch(r"(\d{1,2})\s*[:hH]\s*(\d{2})?", cell_text(value))
    if not match:
        return None
    hours, minutes = int(match.group(1)), int(match.group(2) or 0)
    if hours > 23 or minutes > 59:
        return None
    return time(hours, minutes)


def is_yes(value: Any) -> bool:
    return cell_text(value).lower() in {"oui", "yes", "o", "y", "x", "true", "1"}


def _url(value: Any, where: str, report: ReadReport) -> str:
    text = cell_text(value)
    if text and not (text.startswith(("https://", "http://", "/"))):
        report.warnings.append(f"{where} : URL ignorée (doit commencer par https:// ou /) : {text}")
        return ""
    return text


def _rows(workbook, sheet_name: str) -> list[tuple[int, dict[str, Any]]]:
    if sheet_name not in workbook.sheetnames:
        raise WorkbookError(f"Onglet manquant : « {sheet_name} »")
    ws = workbook[sheet_name]
    columns = SHEET_COLUMNS[sheet_name]
    by_header = {column.header: column for column in columns}
    headers = [cell_text(cell.value).rstrip(" *") for cell in ws[1]]
    missing = [column.header for column in columns if column.header not in headers]
    if missing:
        raise WorkbookError(f"Onglet « {sheet_name} » : colonnes manquantes : {', '.join(missing)}")

    rows: list[tuple[int, dict[str, Any]]] = []
    for row_index, values in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        record = {
            by_header[header].key: value
            for header, value in zip(headers, values, strict=False)
            if header in by_header
        }
        if any(cell_text(value) for value in record.values()):
            rows.append((row_index, record))
    return rows


def _unique_id(base: str, used: set[str]) -> str:
    candidate, counter = base, 2
    while candidate in used:
        candidate = f"{base}-{counter}"
        counter += 1
    used.add(candidate)
    return candidate


def read_workbook(path: Path) -> tuple[ConferenceData, ReadReport]:
    try:
        workbook = load_workbook(path, data_only=True)
    except (OSError, ValueError, KeyError) as exc:
        raise WorkbookError(f"Impossible d'ouvrir {path} : {exc}") from exc

    report = ReadReport()
    event = EventInfo()
    if SHEET_EVENT in workbook.sheetnames:
        for label, value in workbook[SHEET_EVENT].iter_rows(min_row=2, max_col=2, values_only=True):
            if cell_text(label) and cell_text(value):
                event.fields[cell_text(label)] = cell_text(value)
    if not event.name:
        report.warnings.append("Onglet Événement : nom de l'événement non renseigné.")

    speakers = _read_speakers(workbook, report)
    sessions = _read_sessions(workbook, speakers, report)
    partners = _read_partners(workbook, report)
    practical = _read_practical(workbook, report)
    return ConferenceData(event, speakers, sessions, partners, practical), report


def _read_speakers(workbook, report: ReadReport) -> list[Speaker]:
    speakers: list[Speaker] = []
    used: set[str] = set()
    for row, record in _rows(workbook, SHEET_SPEAKERS):
        where = f"Speakers ligne {row}"
        first, last = cell_text(record.get("first_name")), cell_text(record.get("last_name"))
        if not first or not last:
            report.errors.append(f"{where} : prénom et nom obligatoires.")
            continue
        explicit_id = slugify(cell_text(record.get("id")))
        base_id = explicit_id or slugify(f"{first} {last}")
        if explicit_id and explicit_id in used:
            report.errors.append(f"{where} : identifiant en double « {explicit_id} ».")
            continue
        consent = is_yes(record.get("consent"))
        if not consent:
            report.warnings.append(
                f"{where} ({first} {last}) : pas de consentement, profil non publié."
            )
        speaker = Speaker(
            id=_unique_id(base_id, used),
            first_name=first,
            last_name=last,
            consent=consent,
            linkedin_url=_url(record.get("linkedin_url"), where, report),
            photo_url=_url(record.get("photo_url"), where, report),
            company=cell_text(record.get("company")),
            job_title=cell_text(record.get("job_title")),
            bio=cell_text(record.get("bio")),
            expertise=_split_list(record.get("expertise")),
        )
        if consent and not speaker.bio:
            report.warnings.append(f"{where} ({speaker.full_name}) : biographie vide.")
        speakers.append(speaker)
    return speakers


def _read_sessions(workbook, speakers: list[Speaker], report: ReadReport) -> list[Session]:
    lookup: dict[str, Speaker] = {}
    for speaker in speakers:
        lookup[speaker.id] = speaker
        lookup.setdefault(slugify(speaker.full_name), speaker)

    sessions: list[Session] = []
    used: set[str] = set()
    for row, record in _rows(workbook, SHEET_PROGRAM):
        where = f"Programme ligne {row}"
        title = cell_text(record.get("title"))
        day = parse_date(record.get("day"))
        start = parse_time(record.get("start"))
        end = parse_time(record.get("end"))
        if not title or not day or not start or not end:
            report.errors.append(f"{where} : titre, date, début et fin obligatoires et valides.")
            continue
        if end <= start:
            report.errors.append(f"{where} : l'heure de fin doit suivre l'heure de début.")
            continue

        session_speakers: list[SessionSpeaker] = []
        for name in _split_list(record.get("speakers")):
            speaker = lookup.get(slugify(name))
            if speaker is None:
                report.warnings.append(f"{where} : speaker « {name} » absent de l'onglet Speakers.")
            session_speakers.append(SessionSpeaker(name=name, speaker=speaker))

        base_id = slugify(cell_text(record.get("id"))) or slugify(title)[:48]
        session = Session(
            id=_unique_id(base_id.strip("-"), used),
            day=day,
            start=start,
            end=end,
            title=title,
            format=cell_text(record.get("format")),
            room=cell_text(record.get("room")),
            track=cell_text(record.get("track")),
            description=cell_text(record.get("description")),
            tags=_split_list(record.get("tags")),
            language=cell_text(record.get("language")),
            speakers=session_speakers,
        )
        sessions.append(session)
        for entry in session_speakers:
            if entry.speaker:
                entry.speaker.sessions.append(session)

    sessions.sort(key=lambda s: (s.day, s.start, s.room))
    for speaker in speakers:
        speaker.sessions.sort(key=lambda s: (s.day, s.start))
    return sessions


def _read_partners(workbook, report: ReadReport) -> list[Partner]:
    partners: list[Partner] = []
    used: set[str] = set()
    for row, record in _rows(workbook, SHEET_PARTNERS):
        where = f"Partenaires ligne {row}"
        name = cell_text(record.get("name"))
        if not name:
            report.errors.append(f"{where} : nom obligatoire.")
            continue
        partners.append(
            Partner(
                id=_unique_id(slugify(cell_text(record.get("id"))) or slugify(name), used),
                name=name,
                tier=cell_text(record.get("tier")),
                logo_url=_url(record.get("logo_url"), where, report),
                website_url=_url(record.get("website_url"), where, report),
                sector=cell_text(record.get("sector")),
                description=cell_text(record.get("description")),
                offer=cell_text(record.get("offer")),
                booth=cell_text(record.get("booth")),
            )
        )
    return partners


def _read_practical(workbook, report: ReadReport) -> list[PracticalInfo]:
    items: list[PracticalInfo] = []
    for row, record in _rows(workbook, SHEET_PRACTICAL):
        title, content = cell_text(record.get("title")), cell_text(record.get("content"))
        if not title or not content:
            report.errors.append(f"Infos pratiques ligne {row} : question et réponse obligatoires.")
            continue
        items.append(PracticalInfo(cell_text(record.get("category")) or "Divers", title, content))
    return items
