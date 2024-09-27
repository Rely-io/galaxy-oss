import logging

import aiohttp
from aiohttp import ClientResponseError

from galaxy.core.models import Config
from galaxy.core.utils import make_request

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

    async def get_teams(self) -> list[dict]:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            try:
                # No support for pagination: https://docs.opsgenie.com/docs/team-api#list-teams
                response = await make_request(session, "GET", f"{self.url}/v2/teams", headers=self.headers)
                teams = response.get("data", [])
            except ClientResponseError as e:
                raise Exception(f"Client server integration API error: {e.status} {e.message}")

        return teams

    async def get_team(self, team_id: int) -> list[dict]:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            try:
                response = await make_request(session, "GET", f"{self.url}/v2/teams/{team_id}", headers=self.headers)
                team = response.get("data", [])
            except ClientResponseError as e:
                raise Exception(f"Client server integration API error: {e.status} {e.message}")

        return team

    async def get_services(self) -> list[dict]:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            try:
                response = await make_request(session, "GET", f"{self.url}/v1/services", headers=self.headers)
                services = response.get("data", [])
            except ClientResponseError as e:
                raise Exception(f"Client server integration API error: {e.status} {e.message}")

        return services

    async def get_users(self) -> list[dict]:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            try:
                response = await make_request(session, "GET", f"{self.url}/v2/users", headers=self.headers)
                users = response.get("data", [])
            except ClientResponseError as e:
                raise Exception(f"Client server integration API error: {e.status} {e.message}")

        return users

    async def get_escalations(self) -> list[dict]:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            try:
                response = await make_request(session, "GET", f"{self.url}/v2/escalations", headers=self.headers)
                escalations = response.get("data", [])
            except ClientResponseError as e:
                raise Exception(f"Client server integration API error: {e.status} {e.message}")

        return escalations

    async def get_incidents(self) -> list[dict]:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            try:
                response = await make_request(session, "GET", f"{self.url}/v1/incidents", headers=self.headers)
                incidents = response.get("data", [])
            except ClientResponseError as e:
                raise Exception(f"Client server integration API error: {e.status} {e.message}")

        return incidents

    async def get_schedules(self) -> list[dict]:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            try:
                response = await make_request(session, "GET", f"{self.url}/v2/schedules", headers=self.headers)
                schedules = response.get("data", [])
            except ClientResponseError as e:
                raise Exception(f"Client server integration API error: {e.status} {e.message}")

        return schedules

    async def get_schedule_timeline(self, schedule_id) -> list[dict]:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            try:
                response = await make_request(
                    session,
                    "GET",
                    f"{self.url}/v2/schedules/{schedule_id}/timeline",
                    headers=self.headers,
                    params={"interval": 3, "intervalUnit": "weeks"},
                )
                schedules = response.get("data", [])
            except ClientResponseError as e:
                raise Exception(f"Client server integration API error: {e.status} {e.message}")

        return schedules
