"""Point d'entrée de la fonction Python Vercel : expose l'application Flask (`app`)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend" / "src"))

from chatbot_api import create_app  # noqa: E402

app = create_app()
