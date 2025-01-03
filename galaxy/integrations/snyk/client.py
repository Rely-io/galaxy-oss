__all__ = ["SnykClient"]

from logging import Logger
from types import TracebackType
from typing import Any
from datetime import datetime

from galaxy.core.models import Config
from galaxy.utils.requests import ClientSession, create_session, make_request


REGION_MAPPING = {
    "SNYK-US-01": "https://api.snyk.io",
    "SNYK-US-02": "https://api.us.snyk.io",
    "SNYK-EU-01": "https://api.eu.snyk.io",
    "SNYK-AU-02": "https://api.au.snyk.io",
}


class SnykClient:
    PAGE_SIZE: int = 100
    API_VERSION: str = "2024-10-15"

    def __init__(self, config: Config, logger: Logger):
        self.config = config
        self.logger = logger

        self._session: ClientSession | None = None
        self._headers = {
            "Authorization": f"token {config.integration.properties['apiToken']}",
            "Content-Type": "application/vnd.api+json",
        }

        region = self.config.integration.properties["region"]
        try:
            self._session_kwargs = dict(base_url=REGION_MAPPING[region])
        except KeyError:
            raise ValueError(f"Invalid Snyk hosting region: {region}")

    async def __aenter__(self) -> "SnykClient":
        self._session = create_session(timeout=60, headers=self._headers, **self._session_kwargs)
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

    async def _fetch_list_data(self, endpoint: str, **kwargs: Any) -> list[dict]:
        params = kwargs.pop("params", {}) | {"limit": self.PAGE_SIZE, "version": self.API_VERSION}

        response = await make_request(self.session, "GET", endpoint, params=params, **kwargs)
        results = response["data"]

        while (full_path := response["links"].get("next")) is not None:
            response = await make_request(self.session, "GET", full_path)
            results.extend(response["data"])

        return results

    async def get_orgs(self) -> list[dict]:
        return await self._fetch_list_data("/rest/orgs")

    async def get_targets(self, org_id: str) -> list[dict]:
        return await self._fetch_list_data(f"/rest/orgs/{org_id}/targets")

    async def get_projects(self, org_id: str, target_id: str) -> list[dict]:
        return await self._fetch_list_data(
            f"/rest/orgs/{org_id}/projects", params={"target_id": [target_id], "meta.latest_issue_counts": "true"}
        )

    async def get_issues(self, org_id: str, project_id: str, history_start_date: datetime | None = None) -> list[dict]:
        params = {"scan_item.type": "project", "scan_item.id": project_id}
        if history_start_date is not None:
            params["created_after"] = history_start_date.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        return await self._fetch_list_data(f"/rest/orgs/{org_id}/issues", params=params)
