import json
import logging

from httpx import HTTPError

from assistant.integrations.prometheus import get_prometheus_client

_logger = logging.getLogger(__name__)


def validate_function_def(function_name: str) -> None:
    # Will raise an error if the function is not found
    # TODO: use reflection to also validate the arguments
    client = get_prometheus_client()
    getattr(client, function_name)


def call_prometheus_functions(function_calls: list[dict]) -> str:
    responses = []
    for function_call in function_calls:
        response = _call_prometheus_function(function_call)
        responses.append(response)
    return f"<function_results>{json.dumps(responses)}</function_results>"


def _call_prometheus_function(function_call: dict) -> dict | list:
    function_name = function_call["name"]
    arguments = function_call["arguments"]
    client = get_prometheus_client()
    func = getattr(client, function_name)
    _logger.debug(f"Calling prometheus'{function_name}' w/ {arguments}")
    response = func(**arguments)
    _logger.debug(f"Prometheus function {function_name} returned {response}")
    return response


def validate_prometheus_readiness() -> None:
    client = get_prometheus_client()
    try:
        client.query(query="up")
        _logger.info(f"Prometheus is ready: {client}")
    except HTTPError as err:
        _logger.exception(f"Error validating Prometheus readiness: {err!r}")
        raise ValueError(f"Prometheus is not ready: {err}") from err
