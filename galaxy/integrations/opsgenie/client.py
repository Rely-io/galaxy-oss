import logging
from types import TracebackType
from typing import Any

from galaxy.core.models import Config
from galaxy.utils.requests import ClientSession, RetryPolicy, create_session, make_request

__all__ = ["OpsgenieClient"]


class OpsgenieClient:
    PAGINATION_SIZE: int = 100

    def __init__(self, config: Config, logger: logging.Logger):
        self.logger = logger
        self.config = config
        self.url = f"{config.integration.properties['tenantApiUrl']}"
        self.headers = {
            "Authorization": f"GenieKey {config.integration.properties['secretToken']}",
            "Content-Type": "application/json",
        }

        self.session: ClientSession | None = None
        self._retry_policy = RetryPolicy(logger=self.logger, wait_multiplier=2, wait_min=60, wait_max=120)

    async def __aenter__(self) -> "OpsgenieClient":
        self.session = create_session(headers=self.headers)
        return self

    async def __aexit__(self, exc_type: type, exc: Exception, tb: TracebackType) -> None:
        await self.close()

    async def close(self) -> None:
        if self.session is not None:
            await self.session.close()

    async def _make_request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        return await make_request(self.session, method, url, **kwargs, retry_policy=self._retry_policy)

    async def _fetch_list_data(self, url: str, **kwargs: Any) -> list[dict[str, Any]]:
        params = {**kwargs.pop("params", {}), "offset": 0, "limit": self.PAGINATION_SIZE}
        response = await self._make_request("GET", url, params=params, **kwargs)
        results = response["data"]
        while "paging" in response and len(response["data"]) >= self.PAGINATION_SIZE:
            params["offset"] += self.PAGINATION_SIZE
            response = await self._make_request("GET", url, params=params, **kwargs)
            results.extend(response["data"])
        return results

    async def get_teams(self) -> list[dict[str, Any]]:
        return await self._fetch_list_data(f"{self.url}/v2/teams")

    async def get_team(self, team_id: str) -> dict[str, Any]:
        response = await self._make_request("GET", f"{self.url}/v2/teams/{team_id}")
        return response.get("data") or {}

    async def get_services(self) -> list[dict[str, Any]]:
        return await self._fetch_list_data(f"{self.url}/v1/services")

    async def get_users(self) -> list[dict[str, Any]]:
        return await self._fetch_list_data(f"{self.url}/v2/users")

    async def get_escalations(self) -> list[dict[str, Any]]:
        return await self._fetch_list_data(f"{self.url}/v2/escalations")

    async def get_incidents(self) -> list[dict[str, Any]]:
        return await self._fetch_list_data(f"{self.url}/v1/incidents")

    async def get_schedules(self) -> list[dict[str, Any]]:
        return await self._fetch_list_data(f"{self.url}/v2/schedules")

    async def get_schedule_timeline(self, schedule_id: str) -> dict[str, Any]:
        response = await self._make_request(
            "GET", f"{self.url}/v2/schedules/{schedule_id}/timeline", params={"interval": 3, "intervalUnit": "weeks"}
        )
        return response.get("data") or {}
