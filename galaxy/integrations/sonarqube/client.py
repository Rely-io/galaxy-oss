__all__ = ["SonarqubeClient"]

import math
from types import TracebackType

from galaxy.core.models import Config
from galaxy.utils.requests import ClientSession, create_session, make_request


class SonarqubeClient:
    def __init__(self, config: Config, logger):
        self.config = config
        self.logger = logger

        self._session: ClientSession | None = None
        self._headers = {
            "Authorization": f"Bearer {config.integration.properties['apiToken']}",
            "Content-Type": "application/json",
        }
        self._session_kwargs = dict(base_url=config.integration.properties["serverUrl"])

    async def __aenter__(self) -> "SonarqubeClient":
        self._session = create_session(headers=self._headers, **self._session_kwargs)
        return self

    async def __aexit__(self, exc_type: type, exc: Exception, tb: TracebackType) -> None:
        await self.close()

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()

    @property
    def session(self) -> ClientSession:
        """Underlying HTTP client session; ensures methods access an instantiated session."""
        if self._session is None:
            raise ValueError("HTTP client session has not been created")

        return self._session

    async def list_all_projects(self, page_size: int = 500) -> list[dict]:
        response = await make_request(self.session, "GET", f"/api/projects/search?ps={page_size}")
        components = response["components"]

        page_count = max(math.ceil(response["paging"]["total"] / page_size), 1)
        for page in range(2, page_count + 1):
            response = await make_request(self.session, "GET", f"/api/projects/search?ps={page_size}&p={page}")
            components.extend(response["components"])

        return components

    async def list_measures(self, component_key: str, metric_keys: str) -> list[dict]:
        response = await make_request(
            self.session, "GET", f"/api/measures/component?component={component_key}&metricKeys={metric_keys}"
        )
        return response["component"]["measures"]

    async def list_branches(self, project_key: str) -> list[dict]:
        response = await make_request(self.session, "GET", f"/api/project_branches/list?project={project_key}")
        return response["branches"]

    async def list_issues(self, components: str, page_size: int = 500) -> list[dict]:
        response = await make_request(self.session, "GET", f"/api/issues/search?components={components}&ps={page_size}")
        issues = response["issues"]

        page_count = max(math.ceil(response["paging"]["total"] / page_size), 1)
        for page in range(2, page_count + 1):
            response = await make_request(
                self.session, "GET", f"/api/issues/search?components={components}&ps={page_size}&p={page}"
            )
            issues.extend(response["issues"])

        return issues
