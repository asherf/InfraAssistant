import httpx


def get_prometheus_client():
    return PrometheusClient(base_url="http://localhost:9095")


class PrometheusClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.Client(base_url=base_url)

    def get_alerts(self) -> list[dict]:
        # https://prometheus.io/docs/prometheus/latest/querying/api/#alerts
        response = self._client.get("/api/v1/alerts")
        response.raise_for_status()
        return response.json()["data"]["alerts"]

    def get_alert_query(self, alert: dict) -> list[dict]:
        # https://prometheus.io/docs/prometheus/latest/querying/api/#rules
        alertname = alert["labels"]["alertname"]

        response = self._client.get(
            "/api/v1/rules", params={"type": "alert", "rule_name[]": alertname}
        )
        response.raise_for_status()
        groups = response.json()["data"]["groups"]
        if not groups:
            # TODO: App specific error
            raise ValueError(f"No rules found for alert {alertname}")
        alert_rule = groups[0]["rules"][0]
        return alert_rule["query"]
