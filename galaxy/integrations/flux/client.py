import datetime
import functools
import itertools
from types import TracebackType
from typing import Any

from kubernetes import client as k8s_client, config as k8s_config
from kubernetes.client import ApiClient
from kubernetes.config.config_exception import ConfigException

__all__ = ["FluxClient"]


def encode_dt(obj):
    """Workaround while mapper can't handle datetime values."""
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: encode_dt(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [encode_dt(v) for v in obj]
    else:
        return obj


class FluxClient:
    PAGE_SIZE: int = 100

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

        self._client: ApiClient | None = None
        self._configure_client()

    async def __aenter__(self) -> "FluxClient":
        self._client = ApiClient()
        return self

    async def __aexit__(self, exc_type: type, exc: Exception, tb: TracebackType) -> None:
        await self.close()

    async def close(self) -> None:
        if self._client is not None:
            self._client.close()

    @property
    def client(self) -> ApiClient:
        if self._client is None:
            raise ValueError("Kubernetes client has not been created")

        return self._client

    def _configure_client(self) -> None:
        attempts = [(k8s_config.load_incluster_config, "in-cluster"), (k8s_config.load_kube_config, "local kube")]
        for load_config_func, name in attempts:
            try:
                load_config_func()
                self.logger.debug("Successfully loaded %s configuration", name)
                return
            except ConfigException:
                continue

        raise RuntimeError("Unable to load kubernetes client configuration")

    async def _fetch_list_data(
        self, api_instance: k8s_client.CoreV1Api | k8s_client.CustomObjectsApi, method: str, *args: Any, **kwargs: Any
    ) -> list[dict]:
        kwargs = {"limit": self.PAGE_SIZE} | kwargs
        func = functools.partial(getattr(api_instance, method), *args, **kwargs)

        items, _continue = [], None
        while True:
            response = func() if not _continue else func(_continue=_continue)

            if isinstance(response, dict):
                _continue = response["metadata"]["continue"]
            else:
                _continue = response._metadata._continue
                response = encode_dt(response.to_dict())

            items.extend(response["items"])

            if not _continue:
                break

        return items

    async def get_cluster(self) -> dict:
        api_instance = k8s_client.CoreV1Api(self.client)
        response = api_instance.read_namespace("kube-system")
        return encode_dt(response.to_dict())

    async def get_namespaces(self, exclude_system: bool) -> list[dict]:
        api_instance = k8s_client.CoreV1Api(self.client)
        items = await self._fetch_list_data(api_instance, "list_namespace")

        if not exclude_system:
            return items

        to_exclude = {"kube-node-lease", "kube-public", "kube-system"}
        filtered_namespaces = [ns for ns in items if ns["metadata"]["name"] not in to_exclude]
        return filtered_namespaces

    async def get_sources(self) -> list[dict]:
        api_instance = k8s_client.CustomObjectsApi(self.client)
        crds = [
            ("source.toolkit.fluxcd.io", "v1beta2", "buckets"),
            ("source.toolkit.fluxcd.io", "v1beta2", "gitrepositories"),
            ("source.toolkit.fluxcd.io", "v1beta2", "helmcharts"),
            ("source.toolkit.fluxcd.io", "v1beta2", "helmrepositories"),
            ("source.toolkit.fluxcd.io", "v1beta2", "ocirepositories"),
        ]

        items = itertools.chain.from_iterable(
            [await self._fetch_list_data(api_instance, "list_cluster_custom_object", *crd) for crd in crds]
        )
        return list(items)

    async def get_applications(self) -> list[dict]:
        api_instance = k8s_client.CustomObjectsApi(self.client)
        crds = [
            ("kustomize.toolkit.fluxcd.io", "v1beta2", "kustomizations"),
            ("helm.toolkit.fluxcd.io", "v2beta2", "helmreleases"),
        ]

        items = itertools.chain.from_iterable(
            [await self._fetch_list_data(api_instance, "list_cluster_custom_object", *crd) for crd in crds]
        )
        return list(items)
