"""Régénère les sorties de référence du paquet LAYA officiel (test de parité du runtime).

À exécuter dans un environnement **séparé** où le paquet officiel est installé (il exige
PyTorch), jamais dans l'environnement du backend :

    uv venv /tmp/laya-official --python 3.12
    uv pip install --python /tmp/laya-official/bin/python "laya==0.4.17" onnxruntime \\
        "transformers>=4.48,<5" torch --index-url https://download.pytorch.org/whl/cpu \\
        --extra-index-url https://pypi.org/simple
    /tmp/laya-official/bin/python scripts/laya_parity_reference.py \\
        --model-dir models/laya-multilingual-onnx

Puis, dans le backend : `LAYA_TEST_MODEL_DIR=models/laya-multilingual-onnx uv run pytest
tests/test_laya_runtime.py` compare notre runtime (sans PyTorch) à ces références.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

FIXTURE = (
    Path(__file__).resolve().parent.parent
    / "tests"
    / "fixtures"
    / "laya_official_multilingual.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=FIXTURE)
    args = parser.parse_args()

    from laya.onnx_agent import ONNXAgent  # paquet officiel (PyTorch requis)

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    model_dir = args.model_dir.resolve()
    agent = ONNXAgent(str(model_dir), onnx_path=str(model_dir / "model.onnx"))
    for case in fixture["cases"]:
        case["answers"] = agent.system_one(case["state"], fixture["questions"])["answers"]
    fixture["source"] = f"laya ONNXAgent (paquet officiel), modèle {model_dir.name}"
    args.out.write_text(json.dumps(fixture, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(fixture['cases'])} références écrites dans {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
