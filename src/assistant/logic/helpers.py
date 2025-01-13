import asyncio
import json
import re
from enum import Enum
from typing import AsyncGenerator, Callable


def extract_tag_content(text: str, tag_name: str) -> str | None:
    pattern = f"<{tag_name}>(.*?)</{tag_name}>"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1) if match else None


def extract_json_tag_content(text: str, tag_name: str) -> dict | list | None:
    content = extract_tag_content(text, tag_name)
    return json.loads(content) if content else None


class StreamMode(Enum):
    NORMAL = "normal"
    COLLECTING_TAG = "collecting_tag"
    IN_TAG = "in_tag"


class StreamTagExtractor:
    def __init__(self, on_message_callback, on_tag_callback):
        self._mode = StreamMode.NORMAL
        self._tag_name_buffer = []
        self._current_tag_name = None
        self._tag_chunk_buffer = []
        self._message_buffer = []
        self._on_message_callback = on_message_callback
        self._on_tag_callback = on_tag_callback
        self._message_queue = None
        self._active_tasks = set()

    def reset_tags_tracker(self):
        self._tag_name_buffer.clear()
        self._current_tag_name = None
        self._tag_chunk_buffer.clear()
        self._tag_chunk_buffer.append("<")

    async def _maybe_send_message(self, is_final: bool):
        if not self._message_buffer:
            if is_final and self._message_queue:
                await self._message_queue.put(None)
                self._message_queue = None
            return
        if not self._message_queue:
            self._message_queue = await self._create_message_stream(self._on_message_callback)
        mb = "".join(self._message_buffer)
        self._message_buffer.clear()
        await self._message_queue.put(mb)
        if is_final:
            await self._message_queue.put(None)
            self._message_queue = None

    async def _start_tag(self):
        self._mode = StreamMode.COLLECTING_TAG
        self.reset_tags_tracker()
        await self._maybe_send_message(is_final=False)

    def _end_tag(self):
        self._current_tag_name = "".join(self._tag_chunk_buffer)[1:-1]
        self._mode = StreamMode.IN_TAG

    def _in_tag_content(self, char):
        self._tag_chunk_buffer.append(char)
        assert self._current_tag_name is not None
        tag_chunk = "".join(self._tag_chunk_buffer)
        if not tag_chunk.endswith(f"</{self._current_tag_name}>"):
            return
        self._mode = StreamMode.NORMAL
        self._on_tag_callback(self._current_tag_name, tag_chunk)

    async def _create_message_stream(self, on_stream_start: Callable[..., None]) -> asyncio.Queue:
        queue = asyncio.Queue()

        async def stream() -> AsyncGenerator[str, None]:
            while True:
                chunk = await queue.get()
                if chunk is None:  # None signals end of stream
                    break
                yield chunk

        task = asyncio.create_task(on_stream_start(stream()))
        self._active_tasks.add(task)
        task.add_done_callback(self._active_tasks.discard)
        return queue

    async def handle_token(self, token: str) -> None:
        for char in token:
            if self._mode == StreamMode.NORMAL:
                if char == "<":
                    await self._start_tag()
                else:
                    self._message_buffer.append(char)
            elif self._mode == StreamMode.COLLECTING_TAG:
                self._tag_name_buffer.append(char)
                self._tag_chunk_buffer.append(char)
                if char == ">":
                    self._end_tag()
            elif self._mode == StreamMode.IN_TAG:
                self._in_tag_content(char)
        await self._maybe_send_message(is_final=True)

    async def wait_for_tasks(self):
        if not self._active_tasks:
            return
        await asyncio.gather(*self._active_tasks)
