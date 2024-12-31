import chainlit as cl
from chainlit.context import context as cl_context
from dotenv import load_dotenv
from langsmith import traceable

from assistant.logic.llm import new_llm_session

load_dotenv()


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


@traceable
@cl.on_chat_start
def on_chat_start():
    session = new_llm_session(cl_context.session.id)
    cl.user_session.set("llm_session", session)


DEFINE_AWS_ALB_ALERT_RULE_MACRO = """
using the following metrics: aws_applicationelb_httpcode_target_4_xx_count_sum and aws_applicationelb_request_count_sum 
define an alerting rule for the following that will fire when the rate of 4xx errors is greater than 10% of the total requests.
"""


def get_user_msg(msg: str) -> str:
    # just some macros for me, since I am lazy AF
    if msg == "al1":
        return DEFINE_AWS_ALB_ALERT_RULE_MACRO
    return msg


@cl.on_message
async def on_message(message: str):
    session = cl.user_session.get("llm_session")
    response_message = cl.Message(content="")
    user_msg = get_user_msg(message.content)
    await session.process_message(
        incoming_message=user_msg, response_msg=response_message
    )
    await response_message.send()
