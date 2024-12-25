import json
import logging
from pathlib import Path

import litellm
from chainlit import MessageBase

from . import prompts
from .tools import validate_function_def

_logger = logging.getLogger(__name__)


litellm.success_callback = ["langsmith"]
# litellm.set_verbose=True


MAX_FUNCTION_CALLS_PER_MESSAGE = 4
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
        prometheus_functions=function_defs
    )


class LLMSession:
    def __init__(self, session_id: str) -> None:
        self._session_id = session_id
        self._message_history = []  # TODO: init w/ system prompt

    async def llm_stream_call(
        self,
        rresponse_msg: MessageBase,
        role: str,
        message_content: str,
        temperature=0.2,
    ) -> str:
        self._message_history.append({"role": role, "content": message_content})
        _logger.debug(
            f"LLM call: {role} - {message_content[:30]}... ({len(message_content)}) - history: {len(self._message_history)}"
        )

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
                await rresponse_msg.stream_token(token)
        await rresponse_msg.update()
        response_content = rresponse_msg.content
        _logger.debug(
            f"LLM response: {rresponse_msg.content[:30]}.... ({len(response_content)})"
        )
        self._message_history.append({"role": "assistant", "content": response_content})
        return response_content
