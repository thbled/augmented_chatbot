"""Serveur de développement : `uv run python -m chatbot_api`."""

import os

from chatbot_api.app import create_app

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    create_app().run(host="127.0.0.1", port=port, debug=True, threaded=True)
