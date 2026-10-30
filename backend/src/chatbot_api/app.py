"""Application Flask : point d'entrée HTTP entre le frontend et le serveur LLM."""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Iterator
from typing import Any
from urllib.parse import quote

from dotenv import load_dotenv
from flask import Flask, Response, g, jsonify, request

from chatbot_api import guard
from chatbot_api.clock import EventClock
from chatbot_api.config import Settings
from chatbot_api.laya_guard import LayaGuard
from chatbot_api.llm import ChatClient, LLMError, OpenAICompatibleClient, ReplaceText
from chatbot_api.logging_setup import TraceWriter, configure_logging
from chatbot_api.output_guard import OutputChecker, new_canary
from chatbot_api.planning import PlanningClient
from chatbot_api.rate_limit import RateLimiter, build_rate_limiter, hash_client_ip
from chatbot_api.router import Router
from chatbot_api.scope import load_scope
from chatbot_api.turn import TurnBuilder
from chatbot_api.validation import ValidationError, parse_chat_request
from chatbot_api.ws_client import WebSocketRagClient

logger = logging.getLogger(__name__)

# Toute la conversation est envoyée à chaque question (le backend applique ensuite son
# plafond de taille) : la limite du corps de requête est donc large.
MAX_BODY_BYTES = 2 * 1024 * 1024


def build_chat_client(settings: Settings) -> ChatClient:
    if settings.ws_workspace_id:  # RAG via WebSocket
        return WebSocketRagClient(settings)
    return OpenAICompatibleClient(settings)  # API HTTP compatible OpenAI


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
    clock: EventClock | None = None,
    planning: PlanningClient | None = None,
) -> Flask:
    load_dotenv()
    configure_logging()
    settings = settings or Settings.from_env()
    tracer = TraceWriter(settings.trace_file)
    if tracer.enabled:
        logger.info("Traces de diagnostic activées : %s", settings.trace_file)
    chat_client = chat_client or build_chat_client(settings)
    rate_limiter = rate_limiter or build_rate_limiter(settings)
    clock = clock or EventClock(settings)
    if planning is None and settings.planning_url:
        planning = PlanningClient(settings.planning_url, clock, settings.planning_ttl_seconds)
    # Jeton secret placé dans le prompt système : sa présence dans une réponse trahit une fuite.
    canary = new_canary()
    turns = TurnBuilder(settings, clock, planning, canary)
    router = Router(settings, chat_client) if settings.router_model else None
    laya = (
        LayaGuard(settings.laya_model_dir, settings.laya_threshold, settings.laya_threads)
        if settings.laya_model_dir
        else None
    )
    if laya:
        laya.warm_up()

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES

    def error(code: str, status: int, headers: dict[str, str] | None = None) -> Response:
        response = jsonify({"error": code})
        response.status_code = status
        response.headers.update(headers or {})
        return response

    @app.before_request
    def start_request() -> None:
        # Identifiant fourni par le client (scripts de test) ou généré : relie console et traces.
        rid = request.headers.get("X-Request-Id", "")[:64].strip()
        g.request_id = rid or uuid.uuid4().hex[:12]
        g.started = time.perf_counter()

    @app.after_request
    def add_headers(response: Response) -> Response:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Request-Id"] = g.get("request_id", "")
        origin = request.headers.get("Origin")
        if origin and origin in settings.cors_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Request-Id"
            response.headers["Access-Control-Expose-Headers"] = "X-Request-Id"
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

        locale = chat_request.locale
        question = chat_request.messages[-1].content
        # En-têtes de diagnostic (développement) : décisions des garde-fous.
        debug: dict[str, str] = {}
        # Trace complète (TRACE_FILE) : écrite à la fin de la diffusion.
        trace: dict[str, Any] = {
            "request_id": g.get("request_id"),
            "locale": locale,
            "question": question,
            "history": len(chat_request.messages) - 1,
            "stage": "llm",
        }

        if settings.guard_enabled:
            verdict = guard.inspect(guard.normalize(question))
            debug["X-Guard"] = verdict.category or "allow"
            trace["guard"] = verdict.category or "allow"
            if not verdict.allowed:
                # Journal technique anonyme : la catégorie seulement, jamais le texte.
                logger.info("Question bloquée par le filtre (catégorie : %s)", verdict.category)
                refusal = guard.refusal_message(locale)
                trace["stage"] = "guard"
                return stream(iter([refusal]), limit.remaining, debug, locale, trace=trace)

        if laya is not None:
            laya_verdict = laya.check(guard.normalize(question))
            if laya_verdict:
                debug["X-Laya"] = laya_verdict.header
                trace["laya"] = {"score": laya_verdict.score, "flagged": laya_verdict.flagged}
                if laya_verdict.flagged:
                    logger.info("Question bloquée par LAYA (score : %.2f)", laya_verdict.score)
                    refusal = guard.refusal_message(locale)
                    trace["stage"] = "laya"
                    return stream(iter([refusal]), limit.remaining, debug, locale, trace=trace)

        standalone = None
        if router is not None:
            decision = router.decide(chat_request, turns.planning_titles())
            debug["X-Router-Verdict"] = decision.verdict
            debug["X-Router-Source"] = decision.source
            debug["X-Router-Question"] = quote(decision.question)
            trace["router"] = {
                "verdict": decision.verdict,
                "source": decision.source,
                "question": decision.question,
                "allowed": decision.allowed,
            }
            if not decision.allowed:
                logger.info("Question refusée par le routeur (verdict : %s)", decision.verdict)
                refusal = guard.refusal_message(locale, decision.verdict)
                trace["stage"] = "router"
                return stream(iter([refusal]), limit.remaining, debug, locale, trace=trace)
            standalone = decision.question

        turn = turns.build(chat_request, standalone)
        checker = OutputChecker(
            canary,
            load_scope(settings.scope_file),
            turn.reference_times,
            turn.planning_titles,
        )
        debug["X-Facts"] = str(len(turn.facts))
        trace["facts"] = len(turn.facts)
        return stream(
            chat_client.stream_reply(turn), limit.remaining, debug, locale, checker, trace
        )

    def stream(
        chunks: Iterator[str | ReplaceText],
        remaining: int,
        debug: dict[str, str],
        locale: str,
        checker: OutputChecker | None = None,
        trace: dict[str, Any] | None = None,
    ) -> Response:
        trace = trace if trace is not None else {}
        started = g.get("started", time.perf_counter())

        def generate() -> Iterator[str]:
            try:
                yield from produce()
            finally:
                if tracer.enabled:
                    trace["duration_ms"] = round((time.perf_counter() - started) * 1000)
                    tracer.write(trace)

        def produce() -> Iterator[str]:
            text = ""  # texte affiché côté client à cet instant
            try:
                for chunk in chunks:
                    if isinstance(chunk, ReplaceText):
                        text = chunk.text
                        yield sse_event({"type": "replace", "text": text})
                    else:
                        text += chunk
                        yield sse_event({"type": "delta", "text": chunk})
                    if checker and checker.leaked(text):
                        # Fuite du prompt : diffusion coupée immédiatement.
                        logger.warning("Réponse interrompue : fuite du prompt détectée")
                        trace.update(stage="output_leak", raw=text)
                        trace["answer"] = guard.refusal_message(locale)
                        yield sse_event({"type": "replace", "text": trace["answer"]})
                        yield sse_event({"type": "done"})
                        return
            except LLMError as exc:
                trace.update(error=exc.code, raw=text)
                yield sse_event({"type": "error", "code": exc.code})
                return
            except Exception as exc:
                logger.exception("Erreur inattendue pendant la génération")
                trace.update(error="internal_error", exception=repr(exc), raw=text)
                yield sse_event({"type": "error", "code": "internal_error"})
                return

            final = text
            if checker:
                result = checker.check(text)
                trace["output"] = result.as_debug()
                if result.blocked:
                    logger.warning(
                        "Réponse remplacée par le contrôle de sortie (%s)", result.blocked
                    )
                    final = guard.refusal_message(locale)
                    trace["stage"] = "output_blocked"
                else:
                    final = result.text
                    if result.removed_cards or result.masked_contacts:
                        logger.info(
                            "Réponse corrigée (cartes retirées : %d, coordonnées masquées : %d)",
                            len(result.removed_cards),
                            result.masked_contacts,
                        )
                    if result.unverified_times:
                        logger.info(
                            "Horaires non vérifiés : %s", ", ".join(result.unverified_times)
                        )
                if final != text:
                    trace["raw"] = text
                    yield sse_event({"type": "replace", "text": final})
                if settings.debug_headers:
                    yield sse_event({"type": "debug", "output": result.as_debug()})
            trace["answer"] = final
            yield sse_event({"type": "done"})

        headers = {
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        }
        if remaining >= 0:
            headers["X-RateLimit-Remaining"] = str(remaining)
        if settings.debug_headers:
            headers.update(debug)
        return Response(
            generate(),
            mimetype="text/event-stream",
            headers=headers,
        )

    return app
