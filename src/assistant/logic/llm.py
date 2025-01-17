import json
import logging
from collections.abc import AsyncGenerator
from copy import deepcopy
from pathlib import Path
from typing import Callable

import litellm

from . import prompts
from .helpers import StreamTagExtractor, extract_json_tag_content
from .tools import PrometheusFunctions

_logger = logging.getLogger(__name__)

SYSTEM_ROLE = "system"
USER_ROLE = "user"
ASSISTANT_ROLE = "assistant"

Stream = AsyncGenerator[str, None]
StreamCallback = Callable[[Stream], None]

litellm.success_callback = ["langsmith"]
# litellm.set_verbose=True


DEFAULT_TEMPERATURE = 0.2
MAX_FUNCTION_CALLS_PER_MESSAGE = 30
# Choose one of these model configurations by uncommenting it:

# OpenAI GPT-4
OPEN_AI_MODEL = "openai/gpt-4o"

# Anthropic Claude
CLAUDE_MODEL = "claude-3-5-sonnet-20241022"

# Fireworks Qwen
FIREWORKS_MODEL = "fireworks_ai/accounts/fireworks/models/qwen2p5-coder-32b-instruct"

CURRENT_MODEL = CLAUDE_MODEL  # Change this to the model you want to use
# see: https://docs.anthropic.com/en/api/messages#body-messages
SUPPORT_SYSTEM_MESSAGE = CURRENT_MODEL != CLAUDE_MODEL

Stream = AsyncGenerator[str, None]


def _get_function_defs(name: str, validator: PrometheusFunctions):
    defs_path = Path(__file__).parent / f"{name}-function-defs.json"
    function_defs = json.loads(defs_path.read_text())
    for fn in function_defs:
        validator.validate_function_def(fn)
    return json.dumps(function_defs, indent=2)


def get_promql_alerts_rules_assistant_prompt(pf: PrometheusFunctions):
    function_defs = _get_function_defs("metrics", validator=pf)
    return prompts.PROMQL_ALERTS_RULES_ASSISTANT_PROMPT.format(
        prometheus_functions=function_defs,
        example_function_call=json.dumps(
            {
                "name": "get_metric_labels",
                "arguments": {"metric_name": "aws_applicationelb_httpcode_elb_4_xx_count_sum"},
            },
        ),
        example_function_call_2=json.dumps(
            {
                "name": "query",
                "arguments": {"query": "rate(aws_applicationelb_httpcode_elb_4_xx_count_sum[5m])"},
            },
        ),
    )


def new_llm_session(*, session_id: str, start_from_recent: bool, on_message_start_cb, on_tag_start_cb: StreamCallback):
    _logger.info(f"Creating new LLM session for {session_id}")
    return LLMSession(
        session_id=session_id,
        start_from_recent=start_from_recent,
        on_message_start_cb=on_message_start_cb,
        on_tag_start_cb=on_tag_start_cb,
    )


class LLMSession:
    def __init__(
        self, *, session_id: str, start_from_recent: bool, on_message_start_cb, on_tag_start_cb: StreamCallback
    ) -> None:
        self._session_id = session_id
        self._stream_extractor = StreamTagExtractor(
            on_message_callback=on_message_start_cb,
            on_tag_start_callback=on_tag_start_cb,
        )
        self._prometheus = PrometheusFunctions()
        self._prometheus.validate_prometheus_readiness()
        self._prepare_message_history(start_from_recent)

    def _prepare_message_history(self, start_from_recent: bool):
        mh_path = Path(".message_history")
        mh_path.mkdir(parents=True, exist_ok=True)
        self._message_history_store = mh_path / f"{self._session_id}.json"
        system_prompt = get_promql_alerts_rules_assistant_prompt(self._prometheus)
        self._message_history = []
        self._add_message(SYSTEM_ROLE, system_prompt)
        if start_from_recent:
            self._message_history.extend(self._get_latest_history(mh_path) or [])

    def _get_latest_history(self, mh_path: Path) -> list[dict] | None:
        history_files = sorted(mh_path.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not history_files:
            return
        fn = history_files[0]
        messages = json.loads(fn.read_text())
        _logger.info(f"Loaded {len(messages)} messages from {fn}")
        while messages and messages[-1]["role"] != USER_ROLE:
            messages.pop()
        return messages

    def get_welcome_message(self) -> str:
        return f"""
        PromeQL Alerts Assistant is ready to help you with your alerts rules.
        Prometheus is ready at {self._prometheus.get_url()}
        """

    async def resume_from_recent(self):
        if len(self._message_history) <= 3:
            _logger.info("No recent messages to resume from")
            return
        _logger.info(f"Resuming from recent messages ({len(self._message_history)} messages)")

    async def process_message(self, *, incoming_message: str) -> None:
        await self._process_messages(incoming_message=incoming_message)

    async def _process_messages(self, *, incoming_message: str | None) -> None:
        llm_response_content_buffer = []
        async for token in self._llm_stream_call(message_content=incoming_message):
            await self._stream_extractor.handle_token(token)
            llm_response_content_buffer.append(token)

        llm_response_content = "".join(llm_response_content_buffer)
        remaining_calls = MAX_FUNCTION_CALLS_PER_MESSAGE
        while remaining_calls > 0:
            fcs = extract_json_tag_content(llm_response_content, "function_calls")
            if not fcs:
                _logger.info(f"No function calls found in the response: {llm_response_content}")
                break
            api_responses = self.call_apis(fcs)
            _logger.info(
                f"API {fcs} - {api_responses[:50]}... ({len(api_responses)}) - remaining calls: {remaining_calls}",
            )
            if not api_responses:
                break
            remaining_calls -= 1
            llm_response_content_buffer.clear()
            async for token in self._llm_stream_call(message_content=api_responses):
                await self._stream_extractor.handle_token(token)
                llm_response_content_buffer.append(token)
            llm_response_content = "".join(llm_response_content_buffer)
        if remaining_calls == 0:
            raise Exception("Exceeded maximum function calls per message")

    async def _llm_stream_call(self, message_content: str) -> Stream:
        if message_content:
            _logger.info(f"LLM call: {message_content[:400]}")
            self._add_message(role=USER_ROLE, content=message_content)
        response = await litellm.acompletion(
            model=CURRENT_MODEL,
            supports_system_message=SUPPORT_SYSTEM_MESSAGE,
            messages=deepcopy(self._message_history),  # litellm will modify this list, so we need to pass a copy
            stream=True,
            temperature=DEFAULT_TEMPERATURE,
            max_tokens=1000,
        )
        response_buffer: list[str] = []
        async for chunk in response:
            if token := chunk.choices[0].delta.content or "":
                response_buffer.append(token)
                yield token

        response_content = "".join(response_buffer)
        _logger.debug(f"LLM response: {response_content}")
        self._add_message(role=ASSISTANT_ROLE, content=response_content)

    def call_apis(self, fcs: list[dict]) -> str:
        # TODO: based on the session type (promql/alerts), using the right tool call
        # TODO: all of this needs to be async, probably.
        # TODO: handle errors
        return self._prometheus.call_prometheus_functions(fcs)

    def _add_message(self, role: str, content: str):
        self._message_history.append({"role": role, "content": content})
        # Don't store the system prompt in the message history
        msgs_to_save = self._message_history[1:]
        if msgs_to_save:
            self._message_history_store.write_text(json.dumps(msgs_to_save, indent=2))
