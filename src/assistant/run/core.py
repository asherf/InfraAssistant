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


@cl.on_message
async def on_message(message: str):
    session = cl.user_session.get("llm_session")
    response = await session.process_message(message.content)
    await cl.Message(content=response).send()
