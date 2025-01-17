import json
import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Callable

import litellm

from . import prompts
from .helpers import StreamTagExtractor, extract_json_tag_content
from .tools import (
    call_prometheus_functions,
    validate_function_def,
    validate_prometheus_readiness,
)

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


def _get_function_defs(name: str):
    defs_path = Path(__file__).parent / f"{name}-function-defs.json"
    function_defs = json.loads(defs_path.read_text())
    for fn in function_defs:
        validate_function_def(fn)
    return json.dumps(function_defs, indent=2)


def get_promql_alerts_rules_assistant_prompt():
    function_defs = _get_function_defs("metrics")
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


def new_llm_session(*, session_id: str, on_message_start_cb, on_tag_start_cb: StreamCallback):
    _logger.info(f"Creating new LLM session for {session_id}")
    return LLMSession(
        session_id=session_id,
        system_prompt=get_promql_alerts_rules_assistant_prompt(),
        on_message_start_cb=on_message_start_cb,
        on_tag_start_cb=on_tag_start_cb,
    )


class LLMSession:
    def __init__(
        self,
        *,
        session_id: str,
        system_prompt: str,
        on_message_start_cb,
        on_tag_start_cb: StreamCallback,
    ) -> None:
        self._session_id = session_id
        mh_path = Path(".message_history")
        mh_path.mkdir(parents=True, exist_ok=True)
        self._message_history_store = mh_path / f"{session_id}.json"
        self._message_history = []
        self._stream_extractor = StreamTagExtractor(
            on_message_callback=on_message_start_cb,
            on_tag_start_callback=on_tag_start_cb,
        )
        self._add_message(SYSTEM_ROLE, system_prompt)
        self.validate_api_readiness()

    async def process_message(self, *, incoming_message: str) -> None:
        llm_response_content_buffer = []
        # def _handle_tag(tag_name: str, tag_content: str):
        #     if tag_name != "function_calls":
        #         return
        #     fcs = extract_json_tag_content(tag_content, tag_name)
        #     if not fcs:
        #         _logger.info(f"No function calls found in the response: {tag_content}")
        #         return
        #     api_responses = self.call_apis(fcs)
        #     _logger.info(f"API {fcs} - {api_responses[:50]}... ({len(api_responses)})")
        #     if not api_responses:
        #         return
        #     self._add_message(USER_ROLE, api_responses)

        async for token in self._llm_stream_call(role=USER_ROLE, message_content=incoming_message):
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
            async for token in self._llm_stream_call(role=USER_ROLE, message_content=incoming_message):
                await self._stream_extractor.handle_token(token)
                llm_response_content_buffer.append(token)
            llm_response_content = "".join(llm_response_content_buffer)
        if remaining_calls == 0:
            raise Exception("Exceeded maximum function calls per message")

    async def _llm_stream_call(self, role: str, message_content: str, temperature=0.2) -> Stream:
        self._add_message(role=role, content=message_content)
        _logger.info(
            f"LLM call: {role} - {message_content[:30]}... ({len(message_content)}) - history: {len(self._message_history)}",
        )
        response = await litellm.acompletion(
            model=CURRENT_MODEL,
            supports_system_message=SUPPORT_SYSTEM_MESSAGE,
            messages=self._message_history,
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
        _logger.debug(f"LLM response: {response_content[:100]}.... ({len(response_content)})")
        self._add_message(role=ASSISTANT_ROLE, content=response_content)

    def validate_api_readiness(self) -> None:
        # TODO: based on the session type (promql/alerts), using the right tool call
        validate_prometheus_readiness()

    def call_apis(self, fcs: list[dict]) -> str:
        # TODO: based on the session type (promql/alerts), using the right tool call
        # TODO: all of this needs to be async, probably.
        # TODO: handle errors
        return call_prometheus_functions(fcs)

    def _add_message(self, role: str, content: str):
        self._message_history.append({"role": role, "content": content})
        # Don't store the system prompt in the message history
        msgs_to_save = self._message_history[1:]
        if msgs_to_save:
            self._message_history_store.write_text(json.dumps(msgs_to_save, indent=2))
