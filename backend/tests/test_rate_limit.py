from __future__ import annotations

from dataclasses import replace

import httpx

from chatbot_api.rate_limit import (
    MemoryRateLimiter,
    NoopRateLimiter,
    RedisRateLimiter,
    build_rate_limiter,
    hash_client_ip,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_memory_limiter_sliding_window():
    clock = FakeClock()
    limiter = MemoryRateLimiter(max_requests=2, window_seconds=10, clock=clock)
    assert limiter.hit("a").remaining == 1
    assert limiter.hit("a").remaining == 0
    blocked = limiter.hit("a")
    assert not blocked.allowed
    assert 0 < blocked.retry_after_seconds <= 11

    clock.now += 10.5
    assert limiter.hit("a").allowed


def test_redis_limiter_uses_pipeline_results():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        count = len(calls)
        return httpx.Response(200, json=[{"result": count}, {"result": 1}, {"result": 42}])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    limiter = RedisRateLimiter("https://redis.test/", "t", 2, 60, client=client)

    assert limiter.hit("abc").remaining == 1
    assert limiter.hit("abc").remaining == 0
    blocked = limiter.hit("abc")
    assert not blocked.allowed
    assert blocked.retry_after_seconds == 42
    assert str(calls[0].url) == "https://redis.test/pipeline"


def test_redis_limiter_falls_back_to_memory_on_error():
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(500)))
    limiter = RedisRateLimiter("https://redis.test", "t", 1, 60, client=client)
    assert limiter.hit("abc").allowed
    assert not limiter.hit("abc").allowed


def test_hash_client_ip_is_salted_and_stable():
    assert hash_client_ip("1.2.3.4", "s") == hash_client_ip("1.2.3.4", "s")
    assert hash_client_ip("1.2.3.4", "s") != hash_client_ip("1.2.3.4", "t")
    assert "1.2.3.4" not in hash_client_ip("1.2.3.4", "s")


def test_build_rate_limiter(settings):
    assert isinstance(build_rate_limiter(settings), NoopRateLimiter)
    enabled = replace(settings, rate_limit_enabled=True)
    assert isinstance(build_rate_limiter(enabled), MemoryRateLimiter)
    with_redis = replace(enabled, redis_rest_url="https://r.test", redis_rest_token="t")
    assert isinstance(build_rate_limiter(with_redis), RedisRateLimiter)
