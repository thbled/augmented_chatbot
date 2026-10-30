from __future__ import annotations

from collections.abc import Iterator

from chatbot_api.turn import PreparedTurn


class FakeChatClient:
    def __init__(self, chunks: list[str] | None = None, error: Exception | None = None) -> None:
        self.chunks = chunks if chunks is not None else ["Bonjour", " !"]
        self.error = error
        self.turns: list[PreparedTurn] = []

    def stream_reply(self, turn: PreparedTurn) -> Iterator[object]:
        self.turns.append(turn)
        yield from self.chunks
        if self.error:
            raise self.error
