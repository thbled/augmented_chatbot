"""Faits horaires calculés par le code (et non déduits par le LLM).

La question est analysée par des expressions régulières (français et anglais) :
- heures : « 15h12 », « 15 h », « 15 heures 30 », « 15:12 », « 3 pm », « midi » ;
- heures relatives : « dans 20 minutes », « dans une demi-heure », « in an hour » ;
- périodes : « ce matin », « cet après-midi », « ce soir » (et équivalents anglais) ;
- jours relatifs : « demain », « hier » ;
- titres de session cités (« la keynote sécurité »), rapprochés des titres du planning.

Pour chaque élément reconnu, le créneau concerné est calculé à partir du planning en direct
(début + durée ajustée par la régie) : « À 15:12 : « X » (15:00–15:45), commencé depuis
12 min, se termine dans 33 min ». Le LLM n'a plus qu'à formuler ces faits. Une formulation
non reconnue ne produit aucun fait : le LLM s'appuie alors sur la liste du jour.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from chatbot_api.planning import PlanningSnapshot, Slot
from chatbot_api.scope import fold

MAX_RANGE_LINES = 20
MAX_TITLE_MATCHES = 3

_FLAGS = re.IGNORECASE
_FR_HOUR = re.compile(r"\b([01]?\d|2[0-3])\s*(?:h|heures?)\s*([0-5]\d)?(?![\w:])", _FLAGS)
_COLON = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_EN_HOUR = re.compile(r"\b(1[0-2]|0?[1-9])(?::([0-5]\d))?\s*(a\.?m\.?|p\.?m\.?)(?!\w)", _FLAGS)
# « midi » seul, pas « après-midi ».
_NOON = re.compile(r"(?<!apr[eè]s[- ])\b(midi|noon)\b", _FLAGS)
# Une durée (« la session dure 2h ») n'est pas un horaire.
_DURATION_BEFORE = re.compile(
    r"\b(pendant|durant|dure|dur[ée]e\s+de|duration|lasts?|for)\s+$", _FLAGS
)

_RELATIVE = re.compile(
    r"\b(?:dans|in)\s+(?:"
    r"(?P<n>\d{1,3})\s*(?P<unit>minutes?|mins?|heures?|hours?|hrs?|h)\b"
    r"|(?P<one>une?|an?)\s+(?P<one_unit>heure|minute|hour|minute)\b"
    r"|(?P<half>une\s+demi[- ]heure|half\s+an\s+hour)"
    r"|(?P<quarter>un\s+quart\s+d'heure|a\s+quarter\s+of\s+an\s+hour)"
    r")",
    _FLAGS,
)

_PERIODS: list[tuple[re.Pattern[str], str, time, time]] = [
    (
        re.compile(r"\b(ce\s+matin|matin[ée]e|this\s+morning|morning)\b", _FLAGS),
        "le matin",
        time(6, 0),
        time(12, 0),
    ),
    (
        re.compile(r"\b(cet\s+)?apr[eè]s[- ]midi\b|\b(this\s+)?afternoon\b", _FLAGS),
        "l'après-midi",
        time(12, 0),
        time(18, 0),
    ),
    (
        re.compile(r"\b(ce\s+soir|soir[ée]e|this\s+evening|evening|tonight)\b", _FLAGS),
        "le soir",
        time(18, 0),
        time(23, 59),
    ),
]

_DAY_SHIFTS = [
    (re.compile(r"\b(apr[eè]s[- ]demain|day\s+after\s+tomorrow)\b", _FLAGS), 2),
    (re.compile(r"\b(demain|tomorrow)\b", _FLAGS), 1),
    (re.compile(r"\b(hier|yesterday)\b", _FLAGS), -1),
]

_STOPWORDS = {
    "avec",
    "dans",
    "pour",
    "quelle",
    "quelles",
    "quel",
    "quels",
    "heure",
    "session",
    "sessions",
    "conference",
    "atelier",
    "about",
    "what",
    "when",
    "where",
    "which",
    "that",
    "this",
    "with",
    "commence",
    "start",
    "starts",
    "termine",
    "ends",
    "est-ce",
    "keynote",
}


@dataclass(frozen=True)
class TimeQuery:
    label: str
    start: datetime
    end: datetime | None = None  # None : instant précis

    @property
    def is_instant(self) -> bool:
        return self.end is None


def _duration(delta: timedelta) -> str:
    minutes = max(int(delta.total_seconds() // 60), 0)
    hours, rest = divmod(minutes, 60)
    if hours:
        return f"{hours} h {rest:02d}" if rest else f"{hours} h"
    return f"{rest} min"


def _day_shift(text: str) -> int:
    for pattern, shift in _DAY_SHIFTS:
        if pattern.search(text):
            return shift
    return 0


def _at(now: datetime, hour: int, minute: int, shift: int) -> datetime:
    return (now + timedelta(days=shift)).replace(hour=hour, minute=minute, second=0, microsecond=0)


def _clock_times(text: str) -> list[tuple[str, int, int]]:
    """Heures explicites trouvées : (texte, heure, minute), sans doublon ni durée."""
    # Une heure incluse dans une expression relative (« dans 1 h ») n'est pas un horaire.
    relative = [m.span() for m in _RELATIVE.finditer(text)]
    found: list[tuple[int, str, int, int]] = []
    for match in _EN_HOUR.finditer(text):
        hour = int(match.group(1)) % 12
        if match.group(3).lower().startswith("p"):
            hour += 12
        found.append((match.start(), match.group(0), hour, int(match.group(2) or 0)))
    for pattern in (_FR_HOUR, _COLON):
        for match in pattern.finditer(text):
            if _DURATION_BEFORE.search(text[: match.start()]):
                continue
            if any(start <= match.start() < end for start, end in relative):
                continue
            if any(start <= match.start() < start + len(label) for start, label, *_ in found):
                continue
            found.append(
                (match.start(), match.group(0), int(match.group(1)), int(match.group(2) or 0))
            )
    for match in _NOON.finditer(text):
        found.append((match.start(), match.group(0), 12, 0))
    found.sort()
    return [(label.strip(), hour, minute) for _, label, hour, minute in found]


def extract_time_queries(text: str, now: datetime) -> list[TimeQuery]:
    shift = _day_shift(text)
    queries = [
        TimeQuery(label, _at(now, hour, minute, shift))
        for label, hour, minute in _clock_times(text)
    ]

    for match in _RELATIVE.finditer(text):
        if match.group("n"):
            amount = int(match.group("n"))
            unit = match.group("unit").lower()
            minutes = amount * 60 if unit.startswith(("h", "heure", "hour", "hr")) else amount
        elif match.group("one"):
            minutes = 60 if match.group("one_unit").lower() in {"heure", "hour"} else 1
        elif match.group("half"):
            minutes = 30
        else:
            minutes = 15
        queries.append(TimeQuery(match.group(0), now + timedelta(minutes=minutes)))

    if not queries:
        for pattern, label, start, end in _PERIODS:
            if pattern.search(text):
                day = now + timedelta(days=shift)
                queries.append(
                    TimeQuery(
                        label,
                        _at(day, start.hour, start.minute, 0),
                        _at(day, end.hour, end.minute, 0),
                    )
                )
    if not queries and shift:
        day = now + timedelta(days=shift)
        queries.append(TimeQuery("la journée demandée", _at(day, 0, 0, 0), _at(day, 23, 59, 0)))
    return queries


def _status(slot: Slot, now: datetime) -> str:
    if slot.status == "CURRENT" or (not slot.status and slot.start <= now < slot.end):
        return f"en cours, se termine dans {_duration(slot.end - now)}"
    if slot.status == "COMPLETED" or (not slot.status and slot.end <= now):
        return "terminé"
    return f"à venir, commence dans {_duration(slot.start - now)}"


def _slot_text(slot: Slot) -> str:
    kind = f" [{slot.type}]" if slot.type else ""
    return f"« {slot.title} »{kind} ({slot.start:%H:%M}–{slot.end:%H:%M})"


def _event_days(slots: list[Slot]) -> str:
    days = sorted({s.start.date() for s in slots})
    return ", ".join(d.strftime("%d/%m/%Y") for d in days)


def _instant_facts(query: TimeQuery, slots: list[Slot]) -> tuple[list[str], list[Slot]]:
    at = query.start
    label = f"{at:%H:%M}" if at.date() == slots[0].start.date() else f"{at:%d/%m %H:%M}"
    day_slots = [s for s in slots if s.start.date() == at.date()]
    if not day_slots:
        return [
            f"Le {at:%d/%m/%Y} : aucun créneau au planning (journées : {_event_days(slots)})."
        ], []

    containing = [s for s in day_slots if s.start <= at < s.end]
    lines: list[str] = []
    if containing:
        for slot in containing:
            lines.append(
                f"À {label} : {_slot_text(slot)} — commencé depuis {_duration(at - slot.start)}, "
                f"se termine dans {_duration(slot.end - at)}."
            )
        after = max(s.end for s in containing)
    else:
        before = [s for s in day_slots if s.end <= at]
        detail = f"après {_slot_text(before[-1])}" if before else "avant le premier créneau"
        lines.append(f"À {label} : aucun créneau en cours ({detail}).")
        after = at
    following = [s for s in day_slots if s.start >= after and s not in containing]
    if following:
        lines.append(f"Créneau suivant : {_slot_text(following[0])}.")
    return lines, [*containing, *following[:1]]


def _range_facts(query: TimeQuery, slots: list[Slot]) -> tuple[list[str], list[Slot]]:
    end = query.end or query.start
    day_slots = [s for s in slots if s.start.date() == query.start.date()]
    if not day_slots:
        day = query.start.strftime("%d/%m/%Y")
        return [f"Le {day} : aucun créneau au planning (journées : {_event_days(slots)})."], []
    overlapping = [s for s in day_slots if s.start < end and s.end > query.start]
    header = f"{query.label.capitalize()} ({query.start:%H:%M}–{end:%H:%M})"
    if not overlapping:
        return [f"{header} : aucun créneau."], []
    lines = [f"{header} : {len(overlapping)} créneau(x) :"]
    lines += [f"  - {_slot_text(s)}" for s in overlapping[:MAX_RANGE_LINES]]
    return lines, overlapping


def _significant_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", fold(text)) if len(w) >= 4} - _STOPWORDS


def match_titles(question: str, slots: list[Slot]) -> list[Slot]:
    """Créneaux dont le titre est cité dans la question (en entier ou par ses mots clés)."""
    folded = fold(question)
    words = _significant_words(question)
    scored: list[tuple[float, Slot]] = []
    for slot in slots:
        title_words = _significant_words(slot.title)
        if fold(slot.title) in folded:
            scored.append((2.0, slot))
        elif len(title_words) >= 1 and words:
            common = len(title_words & words)
            ratio = common / len(title_words)
            if (common >= 2 and ratio >= 0.6) or (len(title_words) == 1 and common == 1):
                scored.append((ratio, slot))
    scored.sort(key=lambda item: -item[0])
    return [slot for _, slot in scored[:MAX_TITLE_MATCHES]]


@dataclass(frozen=True)
class TimeFacts:
    lines: list[str]
    slots: list[Slot]

    @property
    def titles(self) -> list[str]:
        return list(dict.fromkeys(s.title for s in self.slots))

    def as_text(self) -> str:
        return "\n".join(f"- {line}" if not line.startswith("  ") else line for line in self.lines)


def compute_facts(question: str, snapshot: PlanningSnapshot | None) -> TimeFacts:
    if snapshot is None:
        return TimeFacts([], [])
    tz = snapshot.now.tzinfo
    slots = sorted(
        (
            Slot(
                s.title,
                s.start.astimezone(tz),
                s.end.astimezone(tz),
                s.status,
                s.type,
                s.position,
                s.uid,
            )
            for s in snapshot.slots
        ),
        key=lambda s: (s.start, s.position),
    )
    if not slots:
        return TimeFacts([], [])

    lines: list[str] = []
    involved: list[Slot] = []
    for query in extract_time_queries(question, snapshot.now):
        facts, found = (
            _instant_facts(query, slots) if query.is_instant else _range_facts(query, slots)
        )
        lines += facts
        involved += found

    for slot in match_titles(question, slots):
        lines.append(f"{_slot_text(slot)} : {_status(slot, snapshot.now)}.")
        involved.append(slot)
    return TimeFacts(lines, involved)
