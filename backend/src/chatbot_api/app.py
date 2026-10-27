"""Application Flask : point d'entrée HTTP entre le frontend et le serveur LLM."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request

from chatbot_api.config import Settings
from chatbot_api.llm import ChatClient, LLMError, OpenAICompatibleClient
from chatbot_api.rate_limit import RateLimiter, build_rate_limiter, hash_client_ip
from chatbot_api.validation import ValidationError, parse_chat_request

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 256 * 1024


def sse_event(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def client_ip() -> str:
    # Sur Vercel, `x-real-ip` et `x-forwarded-for` sont renseignés par la plateforme.
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def create_app(
    settings: Settings | None = None,
    chat_client: ChatClient | None = None,
    rate_limiter: RateLimiter | None = None,
) -> Flask:
    load_dotenv()
    settings = settings or Settings.from_env()
    chat_client = chat_client or OpenAICompatibleClient(settings)
    rate_limiter = rate_limiter or build_rate_limiter(settings)

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES

    def error(code: str, status: int, headers: dict[str, str] | None = None) -> Response:
        response = jsonify({"error": code})
        response.status_code = status
        response.headers.update(headers or {})
        return response

    @app.after_request
    def add_headers(response: Response) -> Response:
        response.headers["X-Content-Type-Options"] = "nosniff"
        origin = request.headers.get("Origin")
        if origin and origin in settings.cors_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Vary"] = "Origin"
        return response

    @app.errorhandler(413)
    def too_large(_: Exception) -> Response:
        return error("payload_too_large", 413)

    @app.get("/api/health")
    def health() -> Response:
        return jsonify({"status": "ok"})

    @app.route("/api/chat", methods=["OPTIONS"])
    def chat_preflight() -> Response:
        return Response(status=204)

    @app.post("/api/chat")
    def chat() -> Response:
        payload = request.get_json(silent=True)
        try:
            chat_request = parse_chat_request(payload, settings)
        except ValidationError as exc:
            return error(exc.code, 400)

        limit = rate_limiter.hit(hash_client_ip(client_ip(), settings.ip_hash_salt))
        if not limit.allowed:
            return error("rate_limited", 429, {"Retry-After": str(limit.retry_after_seconds)})

        def generate() -> Iterator[str]:
            try:
                for text in chat_client.stream_reply(chat_request):
                    yield sse_event({"type": "delta", "text": text})
            except LLMError as exc:
                yield sse_event({"type": "error", "code": exc.code})
                return
            except Exception:
                logger.exception("Erreur inattendue pendant la génération")
                yield sse_event({"type": "error", "code": "internal_error"})
                return
            yield sse_event({"type": "done"})

        headers = {
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        }
        if limit.remaining >= 0:
            headers["X-RateLimit-Remaining"] = str(limit.remaining)
        return Response(
            generate(),
            mimetype="text/event-stream",
            headers=headers,
        )

    return app
