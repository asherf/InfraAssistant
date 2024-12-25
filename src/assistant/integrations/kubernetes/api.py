from kubernetes import config, client


def get_kubernetes_clusters() -> tuple[str, ...]:
    avaliable_contexts, _ = config.list_kube_config_contexts()
    return tuple(ctx["name"] for ctx in avaliable_contexts)


def get_kubernetes_version(cluster_name: str) -> str:
    config.load_kube_config(context=cluster_name)
    vi = client.VersionApi().get_code()
    return f"{vi.major}.{vi.minor}"
