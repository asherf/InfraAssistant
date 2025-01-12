import json
import logging
from pathlib import Path

import litellm
from chainlit.message import MessageBase

from . import prompts
from .helpers import extract_json_tag_content
from .tools import (
    call_prometheus_functions,
    validate_function_def,
    validate_prometheus_readiness,
)

_logger = logging.getLogger(__name__)

SYSTEM_ROLE = "system"
USER_ROLE = "user"
ASSISTANT_ROLE = "assistant"

litellm.success_callback = ["langsmith"]
# litellm.set_verbose=True


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
            }
        ),
        example_function_call_2=json.dumps(
            {
                "name": "query",
                "arguments": {"query": "rate(aws_applicationelb_httpcode_elb_4_xx_count_sum[5m])"},
            }
        ),
    )


def new_llm_session(session_id: str):
    _logger.info(f"Creating new LLM session for {session_id}")
    return LLMSession(session_id=session_id, system_prompt=get_promql_alerts_rules_assistant_prompt())


class LLMSession:
    def __init__(self, *, session_id: str, system_prompt: str) -> None:
        self._session_id = session_id
        mh_path = Path(".message_history")
        mh_path.mkdir(parents=True, exist_ok=True)
        self._message_history_store = mh_path / f"{session_id}.json"
        self._message_history = []
        self._add_message(SYSTEM_ROLE, system_prompt)
        self.validate_api_readiness()
        self.validate_api_readiness()

    async def process_message(self, *, incoming_message: str, response_msg: MessageBase):
        llm_response_content = await self.llm_stream_call(
            response_msg=response_msg, role=USER_ROLE, message_content=incoming_message
        )

        remaining_calls = MAX_FUNCTION_CALLS_PER_MESSAGE
        while remaining_calls > 0:
            fcs = extract_json_tag_content(llm_response_content, "function_calls")
            if not fcs:
                _logger.info(f"No function calls found in the response: {llm_response_content}")
                break
            api_responses = self.call_apis(fcs)
            _logger.info(
                f"API {fcs} - {api_responses[:50]}... ({len(api_responses)}) - remaining calls: {remaining_calls}"
            )
            if not api_responses:
                break
            remaining_calls -= 1
            llm_response_content = await self.llm_stream_call(
                response_msg=response_msg, role=USER_ROLE, message_content=api_responses
            )
        if remaining_calls == 0:
            raise Exception("Exceeded maximum function calls per message")

    async def llm_stream_call(
        self,
        response_msg: MessageBase,
        role: str,
        message_content: str,
        temperature=0.2,
    ) -> str:
        self._add_message(role=role, content=message_content)
        _logger.info(
            f"LLM call: {role} - {message_content[:30]}... ({len(message_content)}) - history: {len(self._message_history)}"
        )
        response_msg.content = ""
        response = litellm.completion(
            model=CURRENT_MODEL,
            supports_system_message=SUPPORT_SYSTEM_MESSAGE,
            messages=self._message_history,
            stream=True,
            temperature=temperature,
            max_tokens=1000,
        )

        for part in response:
            if token := part.choices[0].delta.content or "":
                await response_msg.stream_token(token)
        await response_msg.update()
        response_content = response_msg.content
        _logger.debug(f"LLM response: {response_msg.content[:30]}.... ({len(response_content)})")
        self._add_message(role=ASSISTANT_ROLE, content=response_content)
        return response_content

    def validate_api_readiness(self):
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
