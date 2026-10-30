"""Interface en ligne de commande : `uv run conference-tools <commande>`."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

from conference_tools.kb import build_knowledge_base, write_scope
from conference_tools.linkedin import import_linkedin_profiles, llm_extractor
from conference_tools.planning_check import compare, fetch_live_slots
from conference_tools.safety import scan_data
from conference_tools.workbook import ReadReport, WorkbookError, create_template, read_workbook

TOOLS_DIR = Path(__file__).resolve().parents[2]
DEFAULT_STATIC_DIR = TOOLS_DIR / "kb_static"
DEFAULT_PHOTOS_DIR = TOOLS_DIR.parent / "frontend" / "public" / "images" / "speakers"
DEFAULT_SCOPE_OUT = TOOLS_DIR.parent / "backend" / "src" / "chatbot_api" / "data" / "scope.json"


def _print_report(report: ReadReport) -> None:
    for warning in report.warnings:
        print(f"  ⚠ {warning}")
    for error in report.errors:
        print(f"  ✗ {error}", file=sys.stderr)


def cmd_template(args: argparse.Namespace) -> int:
    path = Path(args.output)
    if path.exists() and not args.force:
        print(f"{path} existe déjà (utiliser --force pour l'écraser).", file=sys.stderr)
        return 1
    create_template(path, with_examples=not args.empty)
    print(f"Modèle créé : {path}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        data, report = read_workbook(Path(args.workbook))
    except WorkbookError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    _print_report(report)
    published = sum(1 for s in data.speakers if s.consent)
    print(
        f"{len(data.sessions)} sessions, {published}/{len(data.speakers)} speakers publiés, "
        f"{len(data.partners)} partenaires, {len(data.practical)} infos pratiques."
    )
    return 0 if report.ok else 1


def cmd_build_kb(args: argparse.Namespace) -> int:
    try:
        data, report = read_workbook(Path(args.workbook))
    except WorkbookError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    _print_report(report)
    if not report.ok and not args.allow_errors:
        print("Corrigez les erreurs ou relancez avec --allow-errors.", file=sys.stderr)
        return 1
    static_dir = None if args.no_static else Path(args.static_dir)
    findings = scan_data(data, static_dir)
    for finding in findings:
        print(f"  ⚠ Contenu suspect ({finding.where}) : « {finding.excerpt} »")
    if findings and args.strict:
        print("Contenus suspects : génération annulée (--strict).", file=sys.stderr)
        return 1
    files = build_knowledge_base(data, Path(args.out), static_dir)
    print(f"{len(files)} documents générés dans {args.out}")
    if not args.no_scope:
        scope = write_scope(data, Path(args.scope_out))
        print(f"Fiche de périmètre du routeur : {scope}")
    return 0


def cmd_linkedin_import(args: argparse.Namespace) -> int:
    load_dotenv()
    extractor = None
    if args.pdf_dir:
        missing = [n for n in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL") if not os.getenv(n)]
        if missing:
            print(f"Variables manquantes (.env) : {', '.join(missing)}", file=sys.stderr)
            return 1
        extractor = llm_extractor(
            os.environ["LLM_BASE_URL"], os.environ["LLM_API_KEY"], os.environ["LLM_MODEL"]
        )
    report = import_linkedin_profiles(
        Path(args.workbook),
        Path(args.pdf_dir) if args.pdf_dir else None,
        extractor,
        photos_dir=Path(args.photos_dir) if args.photos_dir else None,
        photos_base_url=args.photos_base_url,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )
    for name in report.updated:
        print(f"  ✓ {name}")
    for name in report.photos:
        print(f"  🖼 photo : {name}")
    for reason in report.skipped:
        print(f"  – {reason}")
    if args.dry_run:
        print("Simulation : classeur non modifié.")
    return 0


def cmd_check_planning(args: argparse.Namespace) -> int:
    load_dotenv()
    url = args.planning_url or os.getenv("PLANNING_URL", "")
    if not url:
        print("URL du planning manquante (--planning-url ou PLANNING_URL).", file=sys.stderr)
        return 1
    try:
        data, _ = read_workbook(Path(args.workbook))
        live = fetch_live_slots(url, args.timezone)
    except (WorkbookError, httpx.HTTPError, ValueError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    report = compare(data.sessions, live, args.tolerance)
    print(f"{len(report.matched)} session(s) rapprochée(s) entre le classeur et le planning.")
    for line in report.time_mismatches:
        print(f"  ✗ Horaires différents : {line}")
    for session in report.only_workbook:
        print(f"  ✗ Absente du planning en direct : « {session.title} » ({session.start_label})")
    for slot in report.only_live:
        print(f"  – Uniquement dans le planning : « {slot.title} » ({slot.start:%H:%M})")
    print("Cohérent." if report.ok else "Écarts à corriger (classeur ou régie).")
    return 0 if report.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="conference-tools", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    template = sub.add_parser("template", help="Créer le modèle Excel de saisie")
    template.add_argument("output", nargs="?", default="data/conference.xlsx")
    template.add_argument("--empty", action="store_true", help="Sans lignes d'exemple")
    template.add_argument("--force", action="store_true", help="Écraser le fichier existant")
    template.set_defaults(func=cmd_template)

    validate = sub.add_parser("validate", help="Vérifier le classeur")
    validate.add_argument("workbook", nargs="?", default="data/conference.xlsx")
    validate.set_defaults(func=cmd_validate)

    build = sub.add_parser("build-kb", help="Générer la base de connaissances")
    build.add_argument("workbook", nargs="?", default="data/conference.xlsx")
    build.add_argument("--out", default="kb", help="Dossier de sortie (vidé au préalable)")
    build.add_argument(
        "--static-dir",
        default=str(DEFAULT_STATIC_DIR),
        help="Documents rédigés à ajouter (Markdown)",
    )
    build.add_argument("--no-static", action="store_true")
    build.add_argument(
        "--scope-out",
        default=str(DEFAULT_SCOPE_OUT),
        help="Fiche de périmètre (noms, thématiques) lue par le routeur du backend",
    )
    build.add_argument("--no-scope", action="store_true")
    build.add_argument(
        "--strict",
        action="store_true",
        help="Annuler la génération si des contenus suspects (injection) sont détectés",
    )
    build.add_argument(
        "--allow-errors", action="store_true", help="Générer malgré les lignes en erreur (ignorées)"
    )
    build.set_defaults(func=cmd_build_kb)

    check = sub.add_parser(
        "check-planning", help="Comparer le planning en direct (REST) et le programme du classeur"
    )
    check.add_argument("workbook", nargs="?", default="data/conference.xlsx")
    check.add_argument("--planning-url", default="", help="Par défaut : variable PLANNING_URL")
    check.add_argument("--timezone", default="Europe/Paris")
    check.add_argument("--tolerance", type=int, default=5, help="Écart toléré, en minutes")
    check.set_defaults(func=cmd_check_planning)

    linkedin = sub.add_parser(
        "linkedin-import", help="Pré-remplir les speakers depuis les exports PDF LinkedIn"
    )
    linkedin.add_argument("workbook", nargs="?", default="data/conference.xlsx")
    linkedin.add_argument("--pdf-dir", help="Dossier des PDF (nommés prenom-nom.pdf)")
    linkedin.add_argument(
        "--photos-dir",
        default=str(DEFAULT_PHOTOS_DIR),
        help="Dossier des photos (nommées prenom-nom.jpg)",
    )
    linkedin.add_argument("--photos-base-url", default="/images/speakers")
    linkedin.add_argument(
        "--overwrite", action="store_true", help="Remplacer les valeurs déjà saisies"
    )
    linkedin.add_argument("--dry-run", action="store_true")
    linkedin.set_defaults(func=cmd_linkedin_import)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
