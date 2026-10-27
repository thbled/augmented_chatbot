from __future__ import annotations

import pytest

from chatbot_api.app import create_app
from chatbot_api.config import Settings
from chatbot_api.rate_limit import NoopRateLimiter
from fakes import FakeChatClient


@pytest.fixture
def settings() -> Settings:
    return Settings(
        llm_base_url="http://llm.test/v1",
        llm_api_key="test-key",
        llm_model="test-model",
        event_name="Conf Test",
        max_history_messages=4,
        max_user_message_chars=50,
        rate_limit_enabled=False,
    )


@pytest.fixture
def fake_client() -> FakeChatClient:
    return FakeChatClient()


@pytest.fixture
def make_client(settings):
    def factory(chat_client=None, rate_limiter=None, app_settings=None):
        app = create_app(
            settings=app_settings or settings,
            chat_client=chat_client or FakeChatClient(),
            rate_limiter=rate_limiter or NoopRateLimiter(),
        )
        return app.test_client()

    return factory


@pytest.fixture
def client(make_client, fake_client):
    return make_client(chat_client=fake_client)
