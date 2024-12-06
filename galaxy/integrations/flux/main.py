from types import TracebackType
from typing import Any

from galaxy.core.galaxy import register, Integration
from galaxy.core.models import Config
from galaxy.integrations.flux.client import FluxClient
from galaxy.utils.parsers import to_bool


class Flux(Integration):
    _methods = []

    def __init__(self, config: Config):
        super().__init__(config)
        self.client = FluxClient(self.config, self.logger)

        self.exclude_system_namespaces = to_bool(config.integration.properties["excludeSystemNamespaces"])

        self._cluster_id = None
        self._namespace_ids = {}
        self._source_ids = {}

    async def __aenter__(self) -> "Flux":
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type: type, exc: Exception, tb: TracebackType) -> None:
        await self.client.__aexit__(exc_type, exc, tb)

    @register(_methods, group=1)
    async def kubernetes_cluster(self) -> tuple[Any]:
        raw_cluster = await self.client.get_cluster()

        self._cluster_id = raw_cluster["metadata"]["uid"]

        mapped_cluster = await self.mapper.process("kubernetes_cluster", [raw_cluster])
        return mapped_cluster

    @register(_methods, group=2)
    async def kubernetes_namespaces(self) -> tuple[Any]:
        raw_namespaces = await self.client.get_namespaces(exclude_system=self.exclude_system_namespaces)

        for ns in raw_namespaces:
            id_, name = ns["metadata"]["uid"], ns["metadata"]["name"]
            self._namespace_ids[name] = id_

        mapped_namespaces = await self.mapper.process(
            "kubernetes_namespace", raw_namespaces, context={"cluster_id": self._cluster_id}
        )
        return mapped_namespaces

    @register(_methods, group=3)
    async def sources(self) -> tuple[Any]:
        raw_sources = await self.client.get_sources()

        for source in raw_sources:
            id_ = source["metadata"]["uid"]
            namespace, kind, name = source["metadata"]["namespace"], source["kind"], source["metadata"]["name"]
            self._source_ids[f"{namespace}-{kind}-{name}"] = id_

        mapped_sources = await self.mapper.process("source", raw_sources, context={"namespaces": self._namespace_ids})
        return mapped_sources

    @register(_methods, group=4)
    async def applications(self) -> tuple[Any]:
        raw_applications = await self.client.get_applications()
        mapped_applications = await self.mapper.process(
            "application", raw_applications, context={"namespaces": self._namespace_ids, "sources": self._source_ids}
        )
        return mapped_applications
