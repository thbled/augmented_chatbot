"""Runtime minimal de LAYA en ONNX, sans PyTorch (onnxruntime + tokenizers + numpy).

Le paquet officiel `laya` (0.4.17) importe PyTorch même pour son moteur ONNX (`ONNXAgent`
dépend de `laya.common` et `laya.agent`, qui importent `torch`), ce qui dépasse les limites
d'une fonction Vercel. Ce module reproduit uniquement le chemin d'inférence ONNX : encodage
des questions typées (`choice`, `score`, `noul`), exécution du graphe, décodage des réponses
avec mise à l'échelle par température.

Adapté de laya 0.4.17 (`laya/common.py`, `laya/onnx_agent.py`), Copyright Convai Innovations,
licence Apache 2.0 — voir THIRD_PARTY_NOTICES.md. Simplifications : pas de réordonnancement des
options (`option_order`), pas d'étiquettes `noul` personnalisées, pas de calibration par
histogramme ni de températures par langue, un seul état par appel.
"""

from __future__ import annotations

import json
import math
import threading
from pathlib import Path
from typing import Any

QTYPES = {"choice": 0, "score": 1, "noul": 2}
QTYPE_NAMES = {v: k for k, v in QTYPES.items()}
TEMP_MIN, TEMP_MAX = 0.5, 5.0
OPTION_MAX_TOKENS = 48


def clamp_temperature(value: Any) -> float:
    if isinstance(value, bool):
        return 1.0
    try:
        t = float(value)
    except (TypeError, ValueError):
        return 1.0
    if math.isnan(t) or math.isinf(t):
        return 1.0
    return min(TEMP_MAX, max(TEMP_MIN, t))


def temp_bucket(qtype: int, k: int) -> str:
    size = "2" if k <= 2 else "3-5" if k <= 5 else "6-10" if k <= 10 else "11+"
    return f"{QTYPE_NAMES[qtype]}:{size}"


def render_criterion(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(", ", ": "), default=str)


def serialize_state(state: str | dict | list) -> str:
    return state if isinstance(state, str) else json.dumps(state, ensure_ascii=False)


def render_options(question: dict[str, Any]) -> list[str]:
    """Texte des options, dans l'ordre des étiquettes (noul : toujours [false, true])."""
    kind, crit = question["type"], question.get("criteria")
    if kind == "choice":
        if isinstance(crit, list):
            crit = {c: None for c in crit}
        return [
            str(k) if v is None or v == "" else f"{k}: {render_criterion(v)}"
            for k, v in crit.items()
        ]
    if kind == "score":
        return [f"level {i}: {render_criterion(c)}" for i, c in enumerate(crit)]
    crit = {str(k).lower(): v for k, v in (crit or {}).items()}
    false_text = crit.get("false") or "no, the statement does not hold"
    true_text = crit.get("true") or "yes, the statement holds"
    return [f"false: {render_criterion(false_text)}", f"true: {render_criterion(true_text)}"]


def option_keys(question: dict[str, Any]) -> list[str]:
    crit = question.get("criteria")
    if question["type"] == "choice":
        return list(crit) if isinstance(crit, list) else list(crit.keys())
    if question["type"] == "score":
        return [str(i) for i in range(len(crit))]
    return ["false", "true"]


class LayaOnnx:
    """Modèle LAYA chargé depuis un dossier : model.onnx, rl_agent_config.json, tokenizer/."""

    def __init__(
        self, model_dir: str | Path, onnx_file: str = "model.onnx", threads: int | None = None
    ) -> None:
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self._np = np
        model_dir = Path(model_dir)
        self.cfg = json.loads((model_dir / "rl_agent_config.json").read_text(encoding="utf-8"))
        if self.cfg.get("option_layout", "sequential") != "sequential":
            raise ValueError("Seule la disposition d'options « sequential » est prise en charge")

        tok_dir = model_dir / "tokenizer"
        tok_cfg = json.loads((tok_dir / "tokenizer_config.json").read_text(encoding="utf-8"))
        self.tok = Tokenizer.from_file(str(tok_dir / "tokenizer.json"))
        self.tok.no_truncation()
        self.tok.no_padding()
        self._lock = threading.Lock()  # un tokenizer partagé n'est pas réentrant

        def special(name: str) -> tuple[str, int]:
            token = tok_cfg[name]
            token = token["content"] if isinstance(token, dict) else token
            token_id = self.tok.token_to_id(token)
            if token_id is None:
                raise ValueError(f"Jeton spécial introuvable dans le tokenizer : {token!r}")
            return token, token_id

        self.mask_token, self.mask_id = special("mask_token")
        _, self.cls_id = special("cls_token")
        _, self.sep_id = special("sep_token")
        _, self.pad_id = special("pad_token")

        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        if threads:
            options.intra_op_num_threads = threads
        self.session = ort.InferenceSession(
            str(model_dir / onnx_file), sess_options=options, providers=["CPUExecutionProvider"]
        )
        self.temperature = [clamp_temperature(t) for t in self.cfg.get("temperature", [1, 1, 1])]
        self.temperature_by_options = {
            k: clamp_temperature(v) for k, v in self.cfg.get("temperature_by_options", {}).items()
        }
        self.max_len = int(self.cfg.get("max_len", 512))
        self.head_max_len = int(self.cfg.get("head_max_len", 192))

    # -- encodage ------------------------------------------------------------------------

    def _encode(self, text: str, max_tokens: int | None = None) -> list[int]:
        with self._lock:
            ids = self.tok.encode(text, add_special_tokens=False).ids
        return ids[:max_tokens] if max_tokens else ids

    def _build_head(self, question: dict[str, Any]) -> tuple[list[int], list[int]]:
        """`[CLS] <type> question: instructions [SEP] [MASK] opt0 [MASK] opt1 … [SEP]`."""
        instructions = question["instructions"]
        if not isinstance(instructions, str):
            instructions = json.dumps(instructions, ensure_ascii=False)
        kind = question["type"]
        clean = instructions.replace(self.mask_token, " ")
        head_ids = self._encode(f"{kind} question: {clean}")
        option_ids = [
            [
                self.mask_id,
                *self._encode(" " + opt.replace(self.mask_token, " "), OPTION_MAX_TOKENS),
            ]
            for opt in render_options(question)
        ]
        budget = self.head_max_len - sum(len(o) for o in option_ids)
        if budget < 16:
            per = max(4, (self.head_max_len - 16) // max(1, len(option_ids)))
            option_ids = [o[:per] for o in option_ids]
            budget = self.head_max_len - sum(len(o) for o in option_ids)
        ids = [self.cls_id, *head_ids[: max(8, budget)], self.sep_id]
        markers = []
        for option in option_ids:
            markers.append(len(ids))
            ids.extend(option)
        ids.append(self.sep_id)
        return ids, markers

    def _build_sequence(
        self, question: dict[str, Any], state_ids: list[int], truncate_left: bool
    ) -> tuple[list[int], list[int]]:
        ids, markers = self._build_head(question)
        room = max(0, self.max_len - len(ids) - 1)
        state = state_ids[max(0, len(state_ids) - room) :] if truncate_left else state_ids[:room]
        ids = [*ids, *state, self.sep_id][: self.max_len]
        return ids, [m for m in markers if m < self.max_len]

    # -- inférence -----------------------------------------------------------------------

    def predict(self, state: str | dict | list, questions: dict[str, dict[str, Any]]) -> dict:
        """Répond aux questions typées sur l'état ; même format de réponse que LAYA."""
        np = self._np
        if not questions:
            return {}
        state_ids = self._encode(serialize_state(state).replace(self.mask_token, " "))
        rows = []
        for qid, question in questions.items():
            if question.get("type") not in QTYPES:
                raise ValueError(f"Question {qid!r} : type inconnu {question.get('type')!r}")
            ids, markers = self._build_sequence(question, state_ids, isinstance(state, list))
            if len(markers) != len(render_options(question)):
                raise ValueError(f"Question {qid!r} : options tronquées (trop longues)")
            rows.append((qid, question, ids, markers))

        n = len(rows)
        length = max(len(r[2]) for r in rows)
        k_cols = max(2, max(len(r[3]) for r in rows))
        input_ids = np.full((n, length), self.pad_id, dtype=np.int64)
        attention = np.zeros((n, length), dtype=np.int64)
        marker_pos = np.zeros((n, k_cols), dtype=np.int64)
        marker_mask = np.zeros((n, k_cols), dtype=bool)
        qtype = np.zeros((n,), dtype=np.int64)
        for i, (_, question, ids, markers) in enumerate(rows):
            input_ids[i, : len(ids)] = ids
            attention[i, : len(ids)] = 1
            marker_pos[i, : len(markers)] = markers
            marker_mask[i, : len(markers)] = True
            qtype[i] = QTYPES[question["type"]]

        logits, act_logits = self.session.run(
            ["logits", "act_logits"],
            {
                "input_ids": input_ids,
                "attention_mask": attention,
                "marker_pos": marker_pos,
                "marker_mask": marker_mask,
                "qtype": qtype,
            },
        )
        act = np.exp(act_logits - act_logits.max(axis=-1, keepdims=True))
        act /= act.sum(axis=-1, keepdims=True)

        answers = {}
        for i, (qid, question, _, markers) in enumerate(rows):
            k = len(markers)
            qt = QTYPES[question["type"]]
            t = self.temperature_by_options.get(temp_bucket(qt, k), self.temperature[qt])
            z = logits[i, :k] / t
            p = np.exp(z - z.max())
            p /= p.sum()
            answers[qid] = self._decode(question, p, k, float(act[i, 0]))
        return answers

    def _decode(self, question: dict[str, Any], p, k: int, act_probability: float) -> dict:
        np = self._np
        top = float(p.max())
        if k >= 2:
            entropy = -float((p * np.log(np.clip(p, 1e-12, 1.0))).sum())
            confidence = min(1.0, max(0.0, 1.0 - entropy / math.log(k)))
        else:
            confidence = 1.0
        common = {
            "confidence": round(confidence, 4),
            "answer_confidence": round(min(1.0, max(0.0, top)), 4),
            "action": {"act_probability": round(act_probability, 4)},
        }
        keys = option_keys(question)
        kind = question["type"]
        if kind == "choice":
            return {
                "type": "choice",
                "choice": keys[int(p.argmax())],
                "probabilities": {key: round(float(v), 4) for key, v in zip(keys, p, strict=False)},
                **common,
            }
        if kind == "score":
            return {
                "type": "score",
                "score": round(float((np.arange(k) * p).sum()), 4),
                "probabilities": {key: round(float(v), 4) for key, v in zip(keys, p, strict=False)},
                **common,
            }
        true = float(p[1])
        return {
            "type": "noul",
            "noul": round(true, 4),
            **common,
            "confidence": round(max(true, 1.0 - true), 4),
        }
