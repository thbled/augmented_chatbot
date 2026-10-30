"""Journalisation du backend et traces de diagnostic par requête (développement).

- `configure_logging()` : format lisible en console, niveau via LOG_LEVEL.
- `TraceWriter` : si TRACE_FILE est défini, écrit une ligne JSON par appel à /api/chat
  (question, décisions des garde-fous, réponse finale, erreurs, durée). Ces traces
  contiennent le texte des questions : à n'activer qu'en développement / recette.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def configure_logging(level: str = "") -> None:
    level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    root = logging.getLogger()
    if not any(getattr(h, "_chatbot", False) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s")
        )
        handler.addFilter(_RequestIdFilter())
        handler._chatbot = True  # type: ignore[attr-defined]
        root.addHandler(handler)
    root.setLevel(level)
    for noisy in ("httpx", "httpcore", "websockets", "werkzeug"):
        logging.getLogger(noisy).setLevel(max(logging.WARNING, root.level))


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            try:
                from flask import g, has_request_context

                record.request_id = g.get("request_id", "-") if has_request_context() else "-"
            except Exception:  # pragma: no cover - flask indisponible
                record.request_id = "-"
        return True


class TraceWriter:
    """Écrit les traces JSONL ; inactif si aucun chemin n'est fourni."""

    def __init__(self, path: str = "") -> None:
        self.path = Path(path) if path else None
        self._lock = threading.Lock()
        if self.path:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
            except OSError:
                logger.warning("Traces désactivées : dossier %s inaccessible", self.path.parent)
                self.path = None

    @property
    def enabled(self) -> bool:
        return self.path is not None

    def write(self, trace: dict[str, Any]) -> None:
        if not self.path:
            return
        trace.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S"))
        line = json.dumps(trace, ensure_ascii=False, default=str)
        try:
            with self._lock, self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            logger.warning("Écriture de trace impossible dans %s", self.path)
