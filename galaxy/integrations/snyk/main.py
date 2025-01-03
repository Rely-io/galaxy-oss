from datetime import datetime, timedelta
from types import TracebackType
from typing import Any

from galaxy.core.galaxy import Integration, register
from galaxy.core.models import Config
from galaxy.integrations.snyk.client import SnykClient


class Snyk(Integration):
    _methods = []

    def __init__(self, config: Config):
        super().__init__(config)
        self.client = SnykClient(self.config, self.logger)

        self._organizations = {}
        self._all_projects = []

    async def __aenter__(self) -> "Snyk":
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type: type, exc: Exception, tb: TracebackType) -> None:
        await self.client.__aexit__(exc_type, exc, tb)

    @register(_methods, group=1)
    async def organizations(self) -> tuple[Any]:
        raw_organizations = await self.client.get_orgs()
        self._organizations = {item["id"]: item["attributes"]["slug"] for item in raw_organizations}

        mapped_organizations = await self.mapper.process("organization", raw_organizations)
        self.logger.debug("Found %d organizations", len(mapped_organizations))

        return mapped_organizations

    @register(_methods, group=2)
    async def targets(self) -> tuple[Any]:
        all_targets = []

        for org_id, org_slug in self._organizations.items():
            raw_targets = await self.client.get_targets(org_id)

            targets = {item["id"]: item for item in raw_targets}
            for target_id in targets:
                raw_projects = [
                    item | {"__organization_slug": org_slug}
                    for item in await self.client.get_projects(org_id, target_id)
                ]

                targets[target_id]["__projects"] = raw_projects
                self._all_projects.extend(raw_projects)

            all_targets.extend(targets.values())

        mapped_targets = await self.mapper.process("target", all_targets)
        self.logger.debug("Found %d targets", len(mapped_targets))

        return mapped_targets

    @register(_methods, group=3)
    async def projects(self) -> tuple[Any]:
        mapped_projects = await self.mapper.process("project", self._all_projects)
        self.logger.debug("Found %d projects", len(mapped_projects))

        return mapped_projects

    @register(_methods, group=3)
    async def issues(self) -> list[Any]:
        organization_target_project_triples = [
            (
                item["relationships"]["organization"]["data"]["id"],
                item["relationships"]["target"]["data"]["id"],
                item["id"],
            )
            for item in self._all_projects
        ]

        history_start_date = datetime.now() - timedelta(days=int(self.config.integration.properties["daysOfHistory"]))

        mapped_issues = []
        for org_id, target_id, project_id in organization_target_project_triples:
            raw_issues = await self.client.get_issues(org_id, project_id, history_start_date)
            project_issues = await self.mapper.process(
                "issue", raw_issues, context={"target_id": target_id, "organization_slug": self._organizations[org_id]}
            )
            mapped_issues.extend(project_issues)

        self.logger.debug(
            "Found %d issues from the last %s days",
            (len(mapped_issues), self.config.integration.properties["daysOfHistory"]),
        )

        return mapped_issues
