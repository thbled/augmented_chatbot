"""Limitation du nombre de requêtes par adresse IP.

Deux implémentations :
- `RedisRateLimiter` : compteur partagé via l'API REST d'Upstash Redis (recommandé sur Vercel,
  où chaque instance serverless a sa propre mémoire) ;
- `MemoryRateLimiter` : fenêtre glissante en mémoire, suffisante en local ou en secours.

Les adresses IP ne sont jamais stockées en clair : seule une empreinte salée est conservée.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Protocol

import httpx

from chatbot_api.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int = 0


class RateLimiter(Protocol):
    def hit(self, client_id: str) -> RateLimitResult: ...


class NoopRateLimiter:
    def hit(self, client_id: str) -> RateLimitResult:
        return RateLimitResult(allowed=True, remaining=-1)


class MemoryRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int, clock=time.monotonic) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, client_id: str) -> RateLimitResult:
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault(client_id, deque())
            while hits and hits[0] <= now - self._window:
                hits.popleft()
            if len(hits) >= self._max:
                retry_after = int(hits[0] + self._window - now) + 1
                return RateLimitResult(allowed=False, remaining=0, retry_after_seconds=retry_after)
            hits.append(now)
            return RateLimitResult(allowed=True, remaining=self._max - len(hits))


class RedisRateLimiter:
    """Fenêtre fixe démarrant à la première requête (INCR + EXPIRE NX)."""

    def __init__(
        self,
        url: str,
        token: str,
        max_requests: int,
        window_seconds: int,
        client: httpx.Client | None = None,
        fallback: RateLimiter | None = None,
    ) -> None:
        self._url = url.rstrip("/")
        self._max = max_requests
        self._window = window_seconds
        self._client = client or httpx.Client(
            timeout=3.0, headers={"Authorization": f"Bearer {token}"}
        )
        self._fallback = fallback or MemoryRateLimiter(max_requests, window_seconds)

    def hit(self, client_id: str) -> RateLimitResult:
        key = f"chatbot:ratelimit:{client_id}"
        commands = [
            ["INCR", key],
            ["EXPIRE", key, str(self._window), "NX"],
            ["TTL", key],
        ]
        try:
            response = self._client.post(f"{self._url}/pipeline", json=commands)
            response.raise_for_status()
            results = response.json()
            count = int(results[0]["result"])
            ttl = int(results[2]["result"])
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
            logger.warning("Redis indisponible pour la limitation de débit, repli en mémoire")
            return self._fallback.hit(client_id)

        if count > self._max:
            return RateLimitResult(allowed=False, remaining=0, retry_after_seconds=max(ttl, 1))
        return RateLimitResult(allowed=True, remaining=self._max - count)


def hash_client_ip(ip: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()[:32]


def build_rate_limiter(settings: Settings) -> RateLimiter:
    if not settings.rate_limit_enabled:
        return NoopRateLimiter()
    if settings.redis_rest_url and settings.redis_rest_token:
        return RedisRateLimiter(
            settings.redis_rest_url,
            settings.redis_rest_token,
            settings.rate_limit_max_requests,
            settings.rate_limit_window_seconds,
        )
    return MemoryRateLimiter(settings.rate_limit_max_requests, settings.rate_limit_window_seconds)
