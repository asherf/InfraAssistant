import httpx


def get_prometheus_client(port: int = 9095):
    return PrometheusClient(base_url=f"http://localhost:{port}")


class PrometheusClient:
    def __init__(self, *, base_url: str) -> None:
        self._client = httpx.Client(base_url=base_url)

    def get_alerts(self) -> list[dict]:
        # https://prometheus.io/docs/prometheus/latest/querying/api/#alerts
        response = self._client.get("/api/v1/alerts")
        response.raise_for_status()
        return response.json()["data"]["alerts"]

    def get_alert_query(self, *, alert: dict) -> list[dict]:
        # https://prometheus.io/docs/prometheus/latest/querying/api/#rules
        alertname = alert["labels"]["alertname"]

        response = self._client.get("/api/v1/rules", params={"type": "alert", "rule_name[]": alertname})
        response.raise_for_status()
        groups = response.json()["data"]["groups"]
        if not groups:
            # TODO: App specific error
            raise ValueError(f"No rules found for alert {alertname}")
        alert_rule = groups[0]["rules"][0]
        return alert_rule["query"]

    def query(self, *, query: str) -> list[dict]:
        response = self._client.get("/api/v1/query", params={"query": query})
        response.raise_for_status()
        return response.json()

    def get_metric_labels(self, *, metric_name: str) -> list[str]:
        # https://prometheus.io/docs/prometheus/latest/querying/api/#getting-label-names
        response = self._client.get("/api/v1/labels", params={"match[]": metric_name})
        response.raise_for_status()
        return response.json()["data"]

    def get_metric_label_values(self, *, metric_name: str, label_name: str) -> list[str]:
        # https://prometheus.io/docs/prometheus/latest/querying/api/#querying-label-values
        response = self._client.get(f"/api/v1/label/{label_name}/values", params={"match[]": metric_name})
        response.raise_for_status()
        return response.json()["data"]

    def get_metric_metadata(self, *, metric_name: str) -> dict:
        # https://prometheus.io/docs/prometheus/latest/querying/api/#querying-metric-metadata
        response = self._client.get("/api/v1/metadata", params={"metric": metric_name})
        response.raise_for_status()
        return response.json()["data"]

    def __str__(self) -> str:
        return f"Prometheus {self._client.base_url}"
