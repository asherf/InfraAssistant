import logging

import chainlit as cl
from chainlit.context import context as cl_context
from dotenv import load_dotenv
from langsmith import traceable

from assistant.logic.llm import LLMSession, Stream, new_llm_session

load_dotenv()

_logger = logging.getLogger(__name__)


def get_icon_path(name: str) -> str:
    return f"/icons/{name}.svg"


# @cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="Help with generating PromQL based alerts rules",
            message="I can help you generate PromQL based alerts rules. What do you need help with?",
            icon=get_icon_path("prometheus"),
        ),
        cl.Starter(
            label="Check Alerts",
            message="I look at alerts and help you fix them.",
            icon=get_icon_path("k8s"),
        ),
    ]


DEFINE_AWS_ALB_ALERT_RULE_MACRO = """
using the following metrics: aws_applicationelb_httpcode_target_4_xx_count_sum and aws_applicationelb_request_count_sum 
define an alerting rule for the following that will fire when the rate of 4xx errors is greater than 10% of the total requests.
"""


def get_user_msg(msg: str) -> str:
    # just some macros for me, since I am lazy AF
    if msg == "al1":
        return DEFINE_AWS_ALB_ALERT_RULE_MACRO
    return msg


async def on_message_start(stream: Stream):
    message = cl.Message(content="")
    await message.send()
    async for token in stream:
        await message.stream_token(token)
    await message.update()
    return message


async def on_tag_start(tag_name: str, stream: Stream):
    message = cl.Message(content="")
    await message.send()
    step = cl.Step(name=tag_name, parent_id=message.id)
    await step.send()
    async for token in stream:
        await step.stream_token(token)

    await step.update()
    return step


@traceable
@cl.on_chat_start
def on_chat_start():
    session: LLMSession = new_llm_session(
        session_id=cl_context.session.id,
        on_message_start_cb=on_message_start,
        on_tag_start_cb=on_tag_start,
    )
    cl.user_session.set("llm_session", session)


@cl.on_message
async def on_message(message: str):
    llm_session: LLMSession = cl.user_session.get("llm_session")
    user_msg = get_user_msg(message.content)
    _logger.info(f"Processing message: {user_msg}")
    await llm_session.process_message(incoming_message=user_msg)
