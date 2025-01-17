import asyncio
import logging
import random
from collections.abc import AsyncGenerator
from typing import Callable

from .helpers import StreamTagExtractor

_logger = logging.getLogger(__name__)

Stream = AsyncGenerator[str, None]
StreamCallback = Callable[[Stream], None]


def new_fake_llm_session(session_id: str, on_message_start_cb, on_tag_start_cb: StreamCallback):
    _logger.info(f"Creating new Fake LLM session for {session_id}")
    return FakeLLMSession(
        session_id=session_id,
        on_message_start_cb=on_message_start_cb,
        on_tag_start_cb=on_tag_start_cb,
    )


class FakeLLMSession:
    def __init__(self, *, session_id: str, on_message_start_cb, on_tag_start_cb: StreamCallback) -> None:
        self._session_id = session_id
        self._stream_extractor = StreamTagExtractor(
            on_message_callback=on_message_start_cb,
            on_tag_start_callback=on_tag_start_cb,
        )

    async def process_message(self, *, incoming_message: str) -> None:
        fake_response = f"""
            User Sent a message length of {len(incoming_message)}
            <user>{incoming_message}</user>
            <llm>These pretzels are making me thirsty!"</llm>
            The sea was angry that day, my friends.
            You double-dipped the chip.
            <llm>It's gold, Jerry! Gold!</llm>
            They're real, and they're spectacular!
        """

        async for chunk in self._tokenize_response(fake_response, parts=4, delay=0.8):
            await self._stream_extractor.handle_token(chunk)

    async def _tokenize_response(self, response: str, parts: int, delay: float) -> Stream:
        indices = sorted(random.sample(range(1, len(response)), parts))
        start = 0
        for idx in indices:
            await asyncio.sleep(delay)
            yield response[start:idx]
            start = idx
