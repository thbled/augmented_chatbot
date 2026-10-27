from __future__ import annotations

from collections.abc import Iterator

from chatbot_api.validation import ChatRequest


class FakeChatClient:
    def __init__(self, chunks: list[str] | None = None, error: Exception | None = None) -> None:
        self.chunks = chunks if chunks is not None else ["Bonjour", " !"]
        self.error = error
        self.requests: list[ChatRequest] = []

    def stream_reply(self, request: ChatRequest) -> Iterator[str]:
        self.requests.append(request)
        yield from self.chunks
        if self.error:
            raise self.error
