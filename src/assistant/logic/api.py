import logging

_logger = logging.getLogger(__name__)


def process_message(message: str):
    return f"You said: {message}"
