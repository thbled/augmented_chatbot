"""Tests réels de l'API /api/chat (serveur lancé) : garde-fous, langue, format de sortie.

    uv run python scripts/api_probe.py
    uv run python scripts/api_probe.py --only hors-scope-heure,speakers
    uv run python scripts/api_probe.py --url https://mon-app.vercel.app/api/chat

Chaque cas de `probe_cases.json` :
    {"id": "...", "question": "...", "locale": "fr",            # locale optionnelle
     "history": [{"role": "user"|"assistant", "content": "..."}],  # optionnel
     "expect_refusal": true|false, "must_contain": ["..."], "must_not_contain": ["..."]}

Contrôles : statut HTTP, flux SSE bien formé (terminé par `done`, pas d'`error`), réponse non
vide, langue, refus attendu ou non, blocs ```json des cartes valides (affichage du front).
Résultats : logs/probe-<date>.jsonl ; le `request_id` relie chaque cas aux traces serveur
(TRACE_FILE).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from pathlib import Path

import httpx

HERE = Path(__file__).parent
BACKEND = HERE.parent
sys.path.insert(0, str(BACKEND / "src"))

from chatbot_api.guard import OFF_TOPIC, REFUSALS  # noqa: E402

EN_WORDS = {"the", "is", "are", "and", "of", "can", "however", "with", "you", "that", "this"}
FR_WORDS = {"le", "la", "les", "est", "et", "des", "du", "vous", "pour", "une", "sur", "avec"}
CARD_BLOCK = re.compile(r"```(speaker|session|partner|suggestions)[ \t]*\n(.*?)\n?```", re.S)
ANY_FENCE = re.compile(r"```(\w*)")
# Champ obligatoire par type de carte, sinon le front ignore la carte
# (frontend/src/lib/parseMessage.ts).
CARD_REQUIRED = {"speaker": ("firstName", "name"), "session": ("title",), "partner": ("name",)}


def refusal_texts() -> list[str]:
    return [t[:60] for table in (REFUSALS, OFF_TOPIC) for t in table.values()]


def detect_lang(text: str) -> str:
    words = re.findall(r"[a-zàâçéèêëîïôûùüÿœ']+", text.lower())
    en = sum(w in EN_WORDS for w in words)
    fr = sum(w in FR_WORDS for w in words)
    if en == fr == 0:
        return "?"
    return "fr" if fr >= en else "en"


def read_sse(response: httpx.Response) -> tuple[list[dict], list[str]]:
    events: list[dict] = []
    issues: list[str] = []
    for line in response.iter_lines():
        if not line.startswith("data:"):
            continue
        try:
            events.append(json.loads(line[5:].strip()))
        except json.JSONDecodeError:
            issues.append("sse:invalid_json")
    return events, issues


def check_cards(text: str) -> tuple[list[str], dict[str, int]]:
    """Blocs ```speaker / session / partner / suggestions tels que les lit le front."""
    issues: list[str] = []
    counts: dict[str, int] = {}
    for kind, body in CARD_BLOCK.findall(text):
        if kind == "suggestions":
            counts[kind] = counts.get(kind, 0) + 1
            continue  # le front accepte JSON ou liste à puces
        try:
            value = json.loads(body.strip())
        except json.JSONDecodeError as exc:
            issues.append(f"cards:{kind}:invalid_json:{exc.msg}")
            continue
        items = value if isinstance(value, list) else [value]
        for item in items:
            if not isinstance(item, dict) or not any(
                isinstance(item.get(k), str) and item[k].strip() for k in CARD_REQUIRED[kind]
            ):
                issues.append(f"cards:{kind}:dropped_by_front")
            else:
                counts[kind] = counts.get(kind, 0) + 1
    known = {"speaker", "session", "partner", "suggestions"}
    suspicious = {"json", "card", "cards", "speakers", "sessions", "partners"}
    for lang in ANY_FENCE.findall(text):
        if lang and lang not in known and lang.lower() in suspicious:
            issues.append(f"cards:unknown_block:{lang}")
    if text.count("```") % 2:
        issues.append("cards:unclosed_fence")
    return issues, counts


def run_case(client: httpx.Client, url: str, case: dict, refusals: list[str]) -> dict:
    rid = f"probe-{case['id']}-{uuid.uuid4().hex[:6]}"
    messages = [*case.get("history", []), {"role": "user", "content": case["question"]}]
    payload = {"locale": case.get("locale", "fr"), "messages": messages}
    issues: list[str] = []
    events: list[dict] = []
    status = None
    headers: dict[str, str] = {}
    t0 = time.perf_counter()
    first_ms = None
    try:
        with client.stream(
            "POST", url, json=payload,
            headers={"X-Request-Id": rid, "Accept": "text/event-stream"},
        ) as r:
            status = r.status_code
            headers = {k: v for k, v in r.headers.items() if k.lower().startswith("x-")}
            if status != 200:
                r.read()
                issues.append(f"http:{status}:{r.text[:80]}")
            else:
                if "text/event-stream" not in r.headers.get("content-type", ""):
                    issues.append("sse:wrong_content_type")
                first_ms = round((time.perf_counter() - t0) * 1000)
                events, sse_issues = read_sse(r)
                issues += sse_issues
    except httpx.HTTPError as exc:
        issues.append(f"transport:{type(exc).__name__}")
    ms = round((time.perf_counter() - t0) * 1000)

    text = ""
    for ev in events:
        kind = ev.get("type")
        if kind == "delta":
            text += ev.get("text", "")
        elif kind == "replace":
            text = ev.get("text", "")
        elif kind == "error":
            issues.append(f"llm:{ev.get('code')}")
        elif kind not in ("done", "debug"):
            issues.append(f"sse:unknown_type:{kind}")
    if status == 200:
        if not events or events[-1].get("type") not in ("done", "error"):
            issues.append("sse:no_done")
        if not text.strip() and not any(e.get("type") == "error" for e in events):
            issues.append("content:empty")

    card_issues, cards = check_cards(text)
    issues += card_issues
    # Détection de langue sur le texte hors blocs (les cartes JSON faussent le comptage).
    lang = detect_lang(CARD_BLOCK.sub(" ", text))
    expected_lang = case.get("locale", "fr")
    if text and lang not in ("?", expected_lang):
        issues.append(f"lang:{lang}")
    refused = any(r in text for r in refusals)
    if "expect_refusal" in case and status == 200 and refused != case["expect_refusal"]:
        issues.append(
            "guardrail:missed_refusal" if case["expect_refusal"] else "guardrail:false_refusal"
        )
    low = text.lower()
    issues += [f"content:missing:{s}" for s in case.get("must_contain", []) if s.lower() not in low]
    issues += [
        f"content:forbidden:{s}" for s in case.get("must_not_contain", []) if s.lower() in low
    ]
    for kind in case.get("expect_cards", []):
        if not cards.get(kind):
            issues.append(f"cards:missing:{kind}")

    return {
        "id": case["id"], "request_id": rid, "question": case["question"], "status": status,
        "duration_ms": ms, "first_byte_ms": first_ms, "lang": lang, "refused": refused,
        "cards": cards, "issues": issues, "headers": headers, "text": text, "events": len(events),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:5000/api/chat")
    ap.add_argument("--cases", default=str(HERE / "probe_cases.json"))
    ap.add_argument("--only", default="", help="ids de cas, séparés par des virgules")
    ap.add_argument("--timeout", type=float, default=90)
    ap.add_argument("--slow-ms", type=int, default=20000)
    args = ap.parse_args()

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8-sig"))
    if args.only:
        keep = set(args.only.split(","))
        cases = [c for c in cases if c["id"] in keep]
    refusals = refusal_texts()

    out_dir = BACKEND / "logs"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"probe-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"

    failures = 0
    with httpx.Client(timeout=args.timeout) as client, out.open("w", encoding="utf-8") as f:
        for case in cases:
            res = run_case(client, args.url, case, refusals)
            if res["duration_ms"] > args.slow_ms:
                res["issues"].append(f"perf:slow:{res['duration_ms']}ms")
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
            ok = not res["issues"]
            failures += not ok
            mark = "OK  " if ok else "FAIL"
            print(
                f"{mark} {res['id']:<22} {res['status']} {res['duration_ms']:>6}ms "
                f"{res['lang']:<2} {'refus' if res['refused'] else '     '} "
                f"{', '.join(res['issues'])}"
            )
            if not ok:
                print(f"     -> {res['text'][:220]!r}")

    print(f"\n{len(cases) - failures}/{len(cases)} OK — détail : {out}")
    print("Traces serveur : chercher le request_id dans le fichier TRACE_FILE.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
