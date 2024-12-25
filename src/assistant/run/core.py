import chainlit as cl
from dotenv import load_dotenv

from assistant.logic.api import process_message

load_dotenv()


def get_icon_path(name: str) -> str:
    return f"/icons/{name}.svg"


@cl.set_starters
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


# @cl.on_chat_start
# async def chat_start():
#     """Runs at the start of a new chat session"""
#     await cl.Message(
#         content="Hello! I'm ready to chat. How can I help you today?"
#     ).send()


@cl.on_message
async def on_message(message: str):
    """Handles incoming chat messages"""
    response = process_message(message.content)
    await cl.Message(content=response).send()
