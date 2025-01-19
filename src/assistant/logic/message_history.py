import json
import logging
from copy import deepcopy
from pathlib import Path

from .constants import USER_ROLE

_logger = logging.getLogger(__name__)


class MessageHistory:
    def __init__(self, *, system_prompt: str) -> None:
        self._mh_path = Path(".message_history")
        self._mh_path.mkdir(parents=True, exist_ok=True)
        self._message_history_store = self._mh_path / f"{self._session_id}.json"
        self._message_history = []
        self.add_message(role="system", content=system_prompt)

    def load_recent_session_messages(self) -> None:
        history_files = sorted(self._mh_path.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not history_files:
            return
        fn = history_files[0]
        messages = json.loads(fn.read_text())
        _logger.info(f"Loaded {len(messages)} messages from {fn}")
        while messages and messages[-1]["role"] != USER_ROLE:
            messages.pop()
        if len(messages) <= 3:
            return
        self._message_history.extend(messages)

    def can_resume_from_recent(self) -> bool:
        return self.message_count > 3

    def message_count(self) -> int:
        return len(self._message_history)

    def add_message(self, role: str, content: str):
        self._message_history.append({"role": role, "content": content})
        # Don't store the system prompt in the message history
        msgs_to_save = self._message_history[1:]
        if msgs_to_save:
            self._message_history_store.write_text(json.dumps(msgs_to_save, indent=2))

    def get_messages_history(self) -> list[dict]:
        # litellm will modify this list, so we need to pass a copy
        return deepcopy(self._message_history)
