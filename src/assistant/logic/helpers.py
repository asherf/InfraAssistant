import json
import re
from enum import Enum


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

    def reset_tags_tracker(self):
        self._tag_name_buffer.clear()
        self._current_tag_name = None
        self._tag_chunk_buffer.clear()
        self._tag_chunk_buffer.append("<")

    def _start_tag(self):
        self._mode = StreamMode.COLLECTING_TAG
        self.reset_tags_tracker()

    def _end_tag(self):
        self._current_tag_name = "".join(self._current_tag_name)
        self._mode = StreamMode.IN_TAG
        # if tag_queue is not None:
        # await tag_queue.put(None)
        # tag_queue = await self._create_stream(current_tag_name, on_tag_start)
        # await tag_queue.put(tag_chunk_buffer)

    def _in_tag_content(self, char):
        self._tag_chunk_buffer.append(char)
        assert self._current_tag_name is not None
        tag_chunk = "".join(self._tag_chunk_buffer)
        if not tag_chunk.endswith(f"</{self._current_tag_name}>"):
            return
        self._mode = StreamMode.NORMAL
        self._on_tag_callback(self._current_tag_name, tag_chunk)

    def handle_token(self, token: str) -> None:
        for char in token:
            if self._mode == StreamMode.NORMAL:
                if char == "<":
                    self._start_tag()
                else:
                    self._message_buffer.append(char)
            elif self._mode == StreamMode.COLLECTING_TAG:
                self._tag_name_buffer.append(char)
                self._tag_chunk_buffer.append(char)
                if char == ">":
                    self._end_tag()
            elif self._mode == StreamMode.IN_TAG:
                self._in_tag_content(char)
            if self._message_buffer and self._mode == StreamMode.NORMAL:
                self._on_message_callback("".join(self._message_buffer))
                self._message_buffer.clear()
