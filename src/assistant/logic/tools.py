import json
import logging

from assistant.integrations.prometheus import get_prometheus_client

_logger = logging.getLogger(__name__)


def validate_function_def(function_name: str):
    # Will raise an error if the function is not found
    # TODO: use reflection to also validate the arguments
    client = get_prometheus_client()
    getattr(client, function_name)


def call_prometheus_function(function_call: dict):
    function_name = function_call["name"]
    arguments = function_call["arguments"]
    client = get_prometheus_client()
    func = getattr(client, function_name)
    _logger.info(f"Calling promethus'{function_name}' w/ {arguments}")
    response = func(**arguments)
    _logger.debug(f"Prometheus function {function_name} returned {response}")
    return f"<function_result>{json.dumps(response)}</function_result>"
