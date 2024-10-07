import logging
from types import TracebackType

from galaxy.core.models import Config
from galaxy.utils.requests import ClientSession, RetryPolicy, create_session, make_request

__all__ = ["OpsgenieClient"]


class OpsgenieClient:
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

    async def get_teams(self) -> list[dict]:
        # No support for pagination: https://docs.opsgenie.com/docs/team-api#list-teams
        response = await make_request(self.session, "GET", f"{self.url}/v2/teams", retry_policy=self._retry_policy)
        teams = response.get("data", [])
        return teams

    async def get_team(self, team_id: int) -> list[dict]:
        response = await make_request(
            self.session, "GET", f"{self.url}/v2/teams/{team_id}", retry_policy=self._retry_policy
        )
        team = response.get("data", [])
        return team

    async def get_services(self) -> list[dict]:
        response = await make_request(self.session, "GET", f"{self.url}/v1/services", retry_policy=self._retry_policy)
        services = response.get("data", [])
        return services

    async def get_users(self) -> list[dict]:
        response = await make_request(self.session, "GET", f"{self.url}/v2/users", retry_policy=self._retry_policy)
        users = response.get("data", [])
        return users

    async def get_escalations(self) -> list[dict]:
        response = await make_request(
            self.session, "GET", f"{self.url}/v2/escalations", retry_policy=self._retry_policy
        )
        escalations = response.get("data", [])
        return escalations

    async def get_incidents(self) -> list[dict]:
        response = await make_request(self.session, "GET", f"{self.url}/v1/incidents", retry_policy=self._retry_policy)
        incidents = response.get("data", [])
        return incidents

    async def get_schedules(self) -> list[dict]:
        response = await make_request(self.session, "GET", f"{self.url}/v2/schedules", retry_policy=self._retry_policy)
        schedules = response.get("data", [])
        return schedules

    async def get_schedule_timeline(self, schedule_id) -> list[dict]:
        response = await make_request(
            self.session,
            "GET",
            f"{self.url}/v2/schedules/{schedule_id}/timeline",
            params={"interval": 3, "intervalUnit": "weeks"},
            retry_policy=self._retry_policy,
        )
        schedules = response.get("data", [])
        return schedules
