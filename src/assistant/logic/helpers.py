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


class StreamHandler:
    def __init__(self, on_message_callback: Callable[..., None], on_tag_start_callback: Callable[..., None]):
        self._on_message_callback = on_message_callback
        self._message_queue = None
        self._on_tag_start_callback = on_tag_start_callback
        self._tag_queue = None
        self._active_tasks: set[asyncio.Task] = set()

    def _get_stream_handler(self, queue):
        async def stream_handler() -> AsyncGenerator[str, None]:
            while True:
                chunk = await queue.get()
                if chunk is None:  # None signals end of stream
                    break
                yield chunk

        return stream_handler

    def _add_task(self, coro):
        task = asyncio.create_task(coro)
        self._active_tasks.add(task)
        task.add_done_callback(self._active_tasks.discard)

    async def _create_message_stream(self) -> asyncio.Queue:
        queue = asyncio.Queue()
        sh = self._get_stream_handler(queue)
        self._add_task(self._on_message_callback(sh()))
        return queue

    async def _create_tag_stream(self, tag_name: str) -> asyncio.Queue:
        queue = asyncio.Queue()
        sh = self._get_stream_handler(queue)
        self._add_task(self._on_tag_start_callback(tag_name, sh()))
        return queue

    async def start_tag_stream(self, tag_name: str, tag_content: str):
        assert self._tag_queue is None
        self._tag_queue = await self._create_tag_stream(tag_name)
        await self._tag_queue.put(tag_content)

    async def stream_tag(self, tag_content: str):
        await self._tag_queue.put(tag_content)

    async def end_tag_stream(self):
        await self._tag_queue.put(None)
        self._tag_queue = None

    async def maybe_send_message(self, message_buffer: list[str], is_final: bool):
        if not message_buffer:
            if is_final and self._message_queue:
                await self._message_queue.put(None)
                self._message_queue = None
            return
        if not self._message_queue:
            self._message_queue = await self._create_message_stream()
        mb = "".join(message_buffer)
        await self._message_queue.put(mb)
        if is_final:
            await self._message_queue.put(None)
            self._message_queue = None

    async def wait_for_tasks(self):
        if not self._active_tasks:
            return
        await asyncio.gather(*self._active_tasks)


class StreamMode(Enum):
    NORMAL = "normal"
    COLLECTING_TAG = "collecting_tag"
    IN_TAG = "in_tag"


class StreamTagExtractor:
    def __init__(
        self, *, on_message_callback: Callable[..., None], on_tag_callback, on_tag_start_callback: Callable[..., None]
    ):
        self._mode = StreamMode.NORMAL
        self._current_tag_name = None
        self._tag_chunk_buffer = []
        self._message_buffer = []
        self._on_tag_callback = on_tag_callback
        self._stream_helper = StreamHandler(on_message_callback, on_tag_start_callback)

    def reset_tags_tracker(self):
        self._current_tag_name = None
        self._tag_chunk_buffer.clear()
        self._tag_chunk_buffer.append("<")

    async def _maybe_send_message(self, is_final: bool):
        await self._stream_helper.maybe_send_message(self._message_buffer, is_final)
        self._message_buffer.clear()

    async def _start_tag(self):
        self._mode = StreamMode.COLLECTING_TAG
        self.reset_tags_tracker()
        await self._maybe_send_message(is_final=False)

    async def _end_tag(self):
        tag_buffer = "".join(self._tag_chunk_buffer)
        self._current_tag_name = tag_buffer[1:-1]
        self._mode = StreamMode.IN_TAG
        await self._stream_helper.start_tag_stream(self._current_tag_name, tag_buffer)

    async def _in_tag_content(self, char):
        self._tag_chunk_buffer.append(char)
        assert self._current_tag_name is not None
        tag_chunk = "".join(self._tag_chunk_buffer)
        await self._stream_helper.stream_tag(char)
        if not tag_chunk.endswith(f"</{self._current_tag_name}>"):
            return
        self._mode = StreamMode.NORMAL
        await self._stream_helper.end_tag_stream()
        self._on_tag_callback(self._current_tag_name, tag_chunk)

    async def handle_token(self, token: str) -> None:
        for char in token:
            if self._mode == StreamMode.NORMAL:
                if char == "<":
                    await self._start_tag()
                else:
                    self._message_buffer.append(char)
            elif self._mode == StreamMode.COLLECTING_TAG:
                self._tag_chunk_buffer.append(char)
                if char == ">":
                    await self._end_tag()
            elif self._mode == StreamMode.IN_TAG:
                await self._in_tag_content(char)
        await self._maybe_send_message(is_final=True)

    async def wait_for_tasks(self):
        await self._stream_helper.wait_for_tasks()
