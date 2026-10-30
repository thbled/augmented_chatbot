from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
tokenizers = pytest.importorskip("tokenizers")
pytest.importorskip("onnxruntime")

from chatbot_api.laya_runtime import (  # noqa: E402
    LayaOnnx,
    clamp_temperature,
    option_keys,
    render_options,
    temp_bucket,
)

FIXTURE = Path(__file__).parent / "fixtures" / "laya_official_multilingual.json"


def test_pure_helpers():
    assert clamp_temperature(0.1) == 0.5
    assert clamp_temperature(9) == 5.0
    assert clamp_temperature(True) == 1.0
    assert clamp_temperature("x") == 1.0
    assert temp_bucket(0, 2) == "choice:2"
    assert temp_bucket(2, 2) == "noul:2"
    assert temp_bucket(1, 4) == "score:3-5"
    assert render_options({"type": "choice", "criteria": {"a": "desc", "b": None}}) == [
        "a: desc",
        "b",
    ]
    assert render_options({"type": "choice", "criteria": ["x", "y"]}) == ["x", "y"]
    assert render_options({"type": "score", "criteria": ["low", "high"]}) == [
        "level 0: low",
        "level 1: high",
    ]
    assert render_options({"type": "noul"}) == [
        "false: no, the statement does not hold",
        "true: yes, the statement holds",
    ]
    assert option_keys({"type": "noul"}) == ["false", "true"]
    assert option_keys({"type": "score", "criteria": ["a", "b", "c"]}) == ["0", "1", "2"]


def tiny_model() -> LayaOnnx:
    """Modèle factice : petit tokenizer réel et session ONNX simulée."""
    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace

    words = [
        "[PAD]",
        "[UNK]",
        "[CLS]",
        "[SEP]",
        "[MASK]",
        "choice",
        "noul",
        "question",
        ":",
        "is",
        "it",
        "spam",
        "a",
        "b",
        "yes",
        "no",
    ]
    tok = Tokenizer(WordLevel({w: i for i, w in enumerate(words)}, unk_token="[UNK]"))
    tok.pre_tokenizer = Whitespace()

    model = LayaOnnx.__new__(LayaOnnx)
    model._np = np
    model.tok = tok
    model._lock = __import__("threading").Lock()
    model.mask_token, model.mask_id = "[MASK]", tok.token_to_id("[MASK]")
    model.cls_id, model.sep_id, model.pad_id = (
        tok.token_to_id(t) for t in ("[CLS]", "[SEP]", "[PAD]")
    )
    model.max_len, model.head_max_len = 64, 32
    model.temperature = [1.0, 1.0, 2.0]
    model.temperature_by_options = {}
    return model


class FakeSession:
    def __init__(self, logits):
        self.logits = np.array(logits, dtype=np.float32)
        self.inputs = None

    def run(self, names, inputs):
        self.inputs = inputs
        n = inputs["input_ids"].shape[0]
        return [self.logits[:n], np.zeros((n, 2), dtype=np.float32)]


def test_sequence_layout():
    model = tiny_model()
    ids, markers = model._build_head(
        {"type": "choice", "instructions": "is it spam", "criteria": ["a", "b"]}
    )
    tok = model.tok
    assert ids[0] == model.cls_id and ids[-1] == model.sep_id
    assert [ids[m] for m in markers] == [model.mask_id, model.mask_id]
    assert tok.id_to_token(ids[markers[0] + 1]) == "a"

    seq, _ = model._build_sequence({"type": "noul", "instructions": "spam"}, [5] * 100, False)
    assert len(seq) == model.max_len and seq[-1] == model.sep_id


def test_predict_decodes_all_question_types():
    model = tiny_model()
    model.session = FakeSession([[2.0, 0.0, 0.0], [0.0, 1.0, 3.0], [0.0, 2.0, 0.0]])
    answers = model.predict(
        "is it spam",
        {
            "c": {"type": "choice", "instructions": "spam", "criteria": {"a": None, "b": None}},
            "s": {"type": "score", "instructions": "spam", "criteria": ["no", "a", "yes"]},
            "n": {"type": "noul", "instructions": "spam"},
        },
    )
    assert answers["c"]["choice"] == "a"
    assert answers["c"]["probabilities"]["a"] == pytest.approx(0.8808, abs=1e-4)
    assert answers["s"]["score"] > 1.5
    # noul : température 2 → p(true) = sigmoïde(2/2)
    assert answers["n"]["noul"] == pytest.approx(0.7311, abs=1e-4)
    assert answers["n"]["confidence"] == answers["n"]["noul"]
    assert model.session.inputs["marker_mask"].shape[1] == 3


def test_unknown_question_type_is_rejected():
    model = tiny_model()
    with pytest.raises(ValueError):
        model.predict("x", {"q": {"type": "rank", "instructions": "?"}})


@pytest.mark.skipif(
    not os.getenv("LAYA_TEST_MODEL_DIR"),
    reason="LAYA_TEST_MODEL_DIR non défini (modèle multilingue téléchargé requis)",
)
def test_parity_with_official_runtime():
    """Mêmes sorties que le paquet officiel (avec PyTorch) sur le vrai modèle multilingue."""
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    model = LayaOnnx(os.environ["LAYA_TEST_MODEL_DIR"])
    for case in fixture["cases"]:
        ours = model.predict(case["state"], fixture["questions"])
        for qid, expected in case["answers"].items():
            got = ours[qid]
            for field in ("confidence", "answer_confidence"):
                assert got[field] == pytest.approx(expected[field], abs=1e-4)
            if "probabilities" in expected:
                for key, value in expected["probabilities"].items():
                    assert got["probabilities"][key] == pytest.approx(value, abs=1e-4)
            else:
                assert got["noul"] == pytest.approx(expected["noul"], abs=1e-4)
