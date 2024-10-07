from types import TracebackType
from typing import Any

from galaxy.core.galaxy import Integration, register
from galaxy.core.models import Config
from galaxy.integrations.sonarqube.client import SonarqubeClient

METRICS = ["bugs", "code_smells", "vulnerabilities", "security_hotspots", "duplicated_files", "coverage"]


class Sonarqube(Integration):
    _methods = []

    def __init__(self, config: Config):
        super().__init__(config)
        self.client = SonarqubeClient(self.config, self.logger)

        self._project_keys = []

    async def __aenter__(self) -> "Sonarqube":
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type: type, exc: Exception, tb: TracebackType) -> None:
        await self.client.__aexit__(exc_type, exc, tb)

    @register(_methods, group=1)
    async def projects(self) -> tuple[Any]:
        project_list = await self.client.list_all_projects()

        project_data = []
        for project in project_list:
            project_dict = {"project": project}

            project_branches = await self.client.list_branches(project["key"])
            main_branch, *_ = [b for b in project_branches if b["isMain"]]
            project_dict["branch"] = main_branch

            # TODO: use comma-separated list instead of iterating
            project_dict["metrics"] = {}
            for metric in METRICS:
                measure, *_ = await self.client.list_measures(project["key"], metric)
                name, value = measure["metric"], measure["value"]
                project_dict["metrics"][name] = value

            project_data.append(project_dict)
            self._project_keys.append(project["key"])

        mapped_projects = await self.mapper.process("project", project_data)
        self.logger.debug("Found %d projects", len(mapped_projects))

        return mapped_projects

    @register(_methods, group=2)
    async def issues(self) -> tuple[Any]:
        issues = []
        for project_key in self._project_keys:
            project_issues = await self.client.list_issues(project_key)
            issues.extend(project_issues)

        mapped_issues = await self.mapper.process("issue", issues)
        self.logger.debug("Found %d issues", len(mapped_issues))

        return mapped_issues
