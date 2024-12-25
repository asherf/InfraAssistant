import logging
import threading
import time

from kubernetes import client, config
from kubernetes.stream import portforward

_logger = logging.getLogger(__name__)


def run_pf():
    logging.basicConfig(level=logging.INFO)
    kfp = KubernetesServicePortForwarder(
        service_name="kps-prometheus",
        namespace="observability",
        context="debug-us-west-2",
        service_port=9090,
    )
    kfp._execute_port_forward()
    return kfp


class KubernetesServicePortForwarder:
    def __init__(self, *, service_name, service_port, namespace, context):
        config.load_kube_config(context=context)
        self._service_name = service_name
        self._service_port = service_port
        self._namespace = namespace

        self._process = None
        self._thread = None
        self._local_port = None
        self._corev1_api = client.CoreV1Api(client.ApiClient())

    def _get_pod(self):
        service = self._corev1_api.read_namespaced_service(
            name=self._service_name, namespace=self._namespace
        )
        selector = service.spec.selector
        if not selector:
            _logger.error(
                f"Service {self._service_name} has no selector. Cannot determine pods."
            )
            return

        label_selector = ",".join([f"{k}={v}" for k, v in selector.items()])

        pod_list = self._corev1_api.list_namespaced_pod(
            namespace=self._namespace, label_selector=label_selector
        )

        if not pod_list.items:
            _logger.error(
                f"No pods found for service {self._service_name} in namespace {self._namespace} with selector {selector}"
            )
            return

        return pod_list.items[0]

    def _execute_port_forward(self):
        pod = self._get_pod()
        if not pod:
            return

        pod_name = pod.metadata.name
        _logger.info(f"Forwarding port to pod: {pod_name}")
        import pdb

        pdb.set_trace()
        resp = portforward(
            self._corev1_api.connect_get_namespaced_pod_portforward,
            name=pod_name,
            namespace=self._namespace,
            ports=str(self._service_port),
            async_req=True,
        )
        self._process = resp
        self._local_port = resp.ports[0]["localPort"]
        _logger.info(f"Port-forwarding established on local port: {self.local_port}")

        while self._process.is_open():
            time.sleep(1)

        _logger.info("Port-forwarding process finished.")

    # ... (start, stop, get_local_port methods remain the same)

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            _logger.warning("Port-forwarding is already running.")
            return

        self._thread = threading.Thread(target=self._execute_port_forward)
        self._thread.daemon = True
        self._thread.start()

    def stop(self):
        if self._process and self._process.is_open():
            self._process.close()
            self._process = None
            self._local_port = None
            _logger.info("Port-forwarding stopped.")
        else:
            _logger.info("Port-forwarding is not running.")

    def get_local_port(self):
        return self.local_port
