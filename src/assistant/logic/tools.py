import json
import logging

from httpx import HTTPError

from assistant.integrations.prometheus import PrometheusClient

_logger = logging.getLogger(__name__)


class PrometheusFunctions:
    def __init__(self, port: int = 9095) -> None:
        self._base_url = f"http://localhost:{port}"
        self._client = PrometheusClient(base_url=self._base_url)

    def get_url(self) -> str:
        return self._base_url

    def validate_function_def(self, function_name: str) -> None:
        # Will raise an error if the function is not found
        getattr(self._client, function_name)

    def call_prometheus_functions(self, function_calls: list[dict]) -> str:
        responses = []
        for function_call in function_calls:
            response = self._call_prometheus_function(function_call)
            responses.append(response)
        return f"<function_results>{json.dumps(responses)}</function_results>"

    def _call_prometheus_function(self, function_call: dict) -> dict | list:
        function_name = function_call["name"]
        arguments = function_call["arguments"]
        func = getattr(self._client, function_name)
        _logger.debug(f"Calling prometheus'{function_name}' w/ {arguments}")
        response = func(**arguments)
        _logger.debug(f"Prometheus function {function_name} returned {response}")
        return response

    def validate_prometheus_readiness(self) -> None:
        try:
            self._client.query(query="up")
            _logger.info(f"Prometheus is ready: {self._client}")
        except HTTPError as err:
            _logger.exception(f"Error validating Prometheus readiness: {err!r}")
            raise ValueError(f"Prometheus is not ready: {err}") from err
