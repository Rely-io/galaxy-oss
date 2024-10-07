from datetime import datetime, timedelta, timezone

from galaxy.core.galaxy import register, Integration
from galaxy.core.models import Config
from galaxy.integrations.pagerduty.client import PagerdutyClient
from galaxy.integrations.pagerduty.utils import get_on_call_info, update_user_on_call_info


class Pagerduty(Integration):
    _methods = []

    def __init__(self, config: Config):
        super().__init__(config)
        self.client = PagerdutyClient(self.config, self.logger)

    @register(_methods, group=1)
    async def teams(self) -> list[dict]:
        # self.on_calls = await self.client.get_on_calls()
        teams = await self.client.get_teams()
        teams_mapped = await self.mapper.process("team", teams, context={})
        self.logger.info(f"Found {len(teams_mapped)} teams")

        return teams_mapped

    @register(_methods, group=2)
    async def users(self) -> list[dict]:
        users = await self.client.get_users()
        # get on calls for next x daysOfHistory (30 by default)
        start_time = datetime.now(timezone.utc)
        end_time = start_time + timedelta(days=int(self.config.integration.properties["daysOfHistory"]))

        for user in users:
            current_oncall, next_oncall = await get_on_call_info(
                self.client, user, start_time.isoformat(), end_time.isoformat()
            )
            update_user_on_call_info(user, current_oncall, next_oncall)

        mapped_users = await self.mapper.process("user", users, context={})
        self.logger.info(f"Found {len(mapped_users)} users")

        return mapped_users

    @register(_methods, group=2)
    async def services(self) -> list[dict]:
        services = await self.client.get_services()
        mapped_services = await self.mapper.process("service", services, context={})
        self.logger.info(f"Found {len(mapped_services)} services")

        return mapped_services

    @register(_methods, group=2)
    async def escalation_policies(self) -> list[dict]:
        escalation_policies = await self.client.get_escalation_policies(params={"include[]": "targets"})
        for policy in escalation_policies:
            escalation_rules = policy.get("escalation_rules", [{}])

            policy["rules"] = (
                [
                    {
                        "escalation_delay_in_minutes": rule.get("escalation_delay_in_minutes"),
                        "targets": [
                            {
                                "type": target.get("type"),
                                "summary": target.get("summary"),
                                "link": target.get("html_url"),
                            }
                            for target in rule.get("targets", [])
                        ],
                    }
                    for rule in escalation_rules
                ]
                if escalation_rules
                else []
            )

        mapped_escalations = await self.mapper.process("escalation_policy", escalation_policies, context={})
        self.logger.info(f"Found {len(mapped_escalations)} escalation policies")

        return mapped_escalations

    @register(_methods, group=3)
    async def incidents(self) -> list[dict]:
        incidents = await self.client.get_incidents()
        mapped_incidents = await self.mapper.process("incident", incidents, context={})
        self.logger.info(f"Found {len(mapped_incidents)} incidents")

        return mapped_incidents
