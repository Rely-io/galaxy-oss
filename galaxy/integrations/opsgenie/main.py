from types import TracebackType

from galaxy.core.galaxy import Integration, register
from galaxy.core.models import Config
from galaxy.integrations.opsgenie.client import OpsgenieClient
from galaxy.integrations.opsgenie.utils import (
    flatten_team_timeline,
    get_user_next_on_call_shift,
    get_user_on_call_teams,
    map_users_to_teams,
)

__all__ = ["Opsgenie"]


class Opsgenie(Integration):
    _methods = []

    def __init__(self, config: Config):
        super().__init__(config)
        self.client = OpsgenieClient(self.config, self.logger)
        self.teams = []
        self.services = []
        self.users = []
        self.escalations = []
        self.incidents = []

    async def __aenter__(self) -> "Opsgenie":
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type: type, exc: Exception, tb: TracebackType) -> None:
        await self.client.__aexit__(exc_type, exc, tb)

    @register(_methods, group=1)
    async def team(self) -> list[dict]:
        teams = {}
        # Fetch  reference to all teams
        teams_metadata = await self.client.get_teams()

        #  Fetch extra team details (e.g. members information)
        for team in teams_metadata:
            teams[team["id"]] = await self.client.get_team(team["id"])

            # Initialize other custom team information
            teams[team["id"]]["schedules"] = []
            teams[team["id"]]["timeline"] = []

        # Link on-call schedules to teams (teams may have multiple or none)
        schedules = await self.client.get_schedules()
        for schedule in schedules:
            schedule["timeline"] = await self.client.get_schedule_timeline(schedule["id"])
            if schedule["ownerTeam"]["id"] not in teams:
                continue
            teams[schedule["ownerTeam"]["id"]]["schedules"].append(schedule)

        for team in teams.values():
            team["timeline"] = flatten_team_timeline(team["schedules"])

        self.teams = list(teams.values())
        teams_mapped = await self.mapper.process("team", self.teams, context={})
        self.logger.info(f"Found {len(teams_mapped)} teams")
        return teams_mapped

    @register(_methods, group=2)
    async def service(self) -> list[dict]:
        self.services = await self.client.get_services()
        services_mapped = await self.mapper.process(
            "service", self.services, context={"baseUrl": self.config.integration.properties["appBaseUrl"]}
        )
        self.logger.info(f"Found {len(services_mapped)} services")
        return services_mapped

    @register(_methods, group=3)
    async def user(self) -> list[dict]:
        self.users = await self.client.get_users()
        teams_per_user = map_users_to_teams(self.teams)
        for user in self.users:
            user["teams"] = teams_per_user.get(user["id"]) or []
            user["teamsOnCall"] = get_user_on_call_teams(user)
            user["nextOnCallShift"] = get_user_next_on_call_shift(user, self.logger)

        users_mapped = await self.mapper.process(
            "user", self.users, context={"baseUrl": self.config.integration.properties["appBaseUrl"]}
        )
        self.logger.info(f"Found {len(users_mapped)} users")
        return users_mapped

    @register(_methods, group=3)
    async def escalation(self) -> list[dict]:
        self.escalations = await self.client.get_escalations()
        escalations_mapped = await self.mapper.process("escalation", self.escalations, context={})
        self.logger.info(f"Found {len(escalations_mapped)} escalations")
        return escalations_mapped

    @register(_methods, group=4)
    async def incidents(self) -> list[dict]:
        self.incidents = await self.client.get_incidents()
        incidents_mapped = await self.mapper.process(
            "incident", self.incidents, context={"baseUrl": self.config.integration.properties["appBaseUrl"]}
        )
        self.logger.info(f"Found {len(incidents_mapped)} incidents")
        return incidents_mapped
