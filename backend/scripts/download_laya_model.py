"""Télécharge un modèle LAYA au format ONNX (int8) pour le garde-fou local.

Usage (depuis backend/) :
    uv run python scripts/download_laya_model.py                      # multilingue
    uv run python scripts/download_laya_model.py --variant english
    uv run python scripts/download_laya_model.py --out /chemin

Variantes (toutes sous licence Apache 2.0, dérivées du modèle LAYA de Convai Innovations) :
- multilingual : export communautaire « soyelmismo/laya-multilingual-onnx » (325 Mo, int8
  sélectif) → models/laya-multilingual-onnx ;
- english : graphe int8 « mnjkshrm/sentrygate-laya » (443 Mo) avec la configuration et le
  tokenizer du dépôt officiel « convaiinnovations/laya » → models/laya-english-onnx.

Chaque fichier vient d'une révision épinglée ; l'empreinte SHA-256 des fichiers volumineux est
vérifiée. Aucun code n'est téléchargé : uniquement des données (graphe ONNX, tokenizer,
configuration de calibration).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

MULTILINGUAL = ("soyelmismo/laya-multilingual-onnx", "0966c4fa58da6878b39e7e14cb5e93313b82d828")
ENGLISH_GRAPH = ("mnjkshrm/sentrygate-laya", "ce2fd4b60dae5aa9cad504df552e54a1803ce058")
ENGLISH_BASE = ("convaiinnovations/laya", "7b928d828b7b0e022f929d9bd2e44165aa270148")
SMALL_FILES = [
    "rl_agent_config.json",
    "tokenizer/tokenizer.json",
    "tokenizer/tokenizer_config.json",
]

# variante → [(dépôt, révision, chemin distant, chemin local)]
VARIANTS: dict[str, list[tuple[str, str, str, str]]] = {
    "multilingual": [
        (*MULTILINGUAL, "model.onnx", "model.onnx"),
        *[(*MULTILINGUAL, path, path) for path in SMALL_FILES],
    ],
    "english": [
        (*ENGLISH_GRAPH, "laya.onnx", "model.onnx"),
        *[(*ENGLISH_BASE, path, path) for path in SMALL_FILES],
    ],
}
DEFAULT_DIRS = {"multilingual": "laya-multilingual-onnx", "english": "laya-english-onnx"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _lfs_digests(repo: str, revision: str) -> dict[str, str]:
    """Empreintes SHA-256 publiées par Hugging Face pour les gros fichiers d'une révision."""
    url = f"https://huggingface.co/api/models/{repo}/tree/{revision}?recursive=1"
    with urllib.request.urlopen(url, timeout=30) as response:
        tree = json.load(response)
    return {f["path"]: f["lfs"]["oid"] for f in tree if f.get("lfs")}


def download(variant: str, out: Path) -> None:
    digests: dict[tuple[str, str], dict[str, str]] = {}
    for repo, revision, remote, local in VARIANTS[variant]:
        if (repo, revision) not in digests:
            digests[repo, revision] = _lfs_digests(repo, revision)
        expected = digests[repo, revision].get(remote)
        target = out / local
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and (expected is None or _sha256(target) == expected):
            print(f"  ✓ {local} (déjà présent)")
            continue
        print(f"  ↓ {local} ({repo}) …", flush=True)
        partial = target.with_suffix(target.suffix + ".part")
        url = f"https://huggingface.co/{repo}/resolve/{revision}/{remote}"
        urllib.request.urlretrieve(url, partial)
        if expected and _sha256(partial) != expected:
            partial.unlink()
            raise SystemExit(f"Empreinte SHA-256 inattendue pour {remote} : téléchargement refusé")
        partial.replace(target)
    print(f"Modèle prêt dans {out}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--variant", choices=sorted(VARIANTS), default="multilingual")
    parser.add_argument("--out", type=Path, help="Dossier de destination")
    args = parser.parse_args()
    download(args.variant, args.out or MODELS_DIR / DEFAULT_DIRS[args.variant])
    return 0


if __name__ == "__main__":
    sys.exit(main())
