from datetime import datetime, timedelta, timezone

from pdpyras import APISession, PDHTTPError, PDClientError

__all__ = ["PagerdutyClient"]


class PagerdutyClient:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

        self.url = config.integration.properties["url"]
        self.api_key = config.integration.properties["apiKey"]

        self.session = APISession(api_key=self.api_key)
        if self.url:
            self.session.url = self.url

        now = datetime.now(timezone.utc)
        start_date = now - timedelta(days=int(config.integration.properties["daysOfHistory"]))
        self.start_date = start_date.isoformat()

    async def get_teams(self) -> list[dict]:
        try:
            teams_iter = self.session.iter_all("teams")

            return list(teams_iter)
        except PDHTTPError as e:
            if e.response.status_code == 404:
                self.logger.error("No pagerduty teams found")
            else:
                raise e
        except PDClientError as e:
            self.logger.error(f"Non-transient network or client error: {e.msg}")

        return []

    async def get_users(self) -> list[dict]:
        try:
            users_iter = self.session.iter_all("users")

            return list(users_iter)
        except PDHTTPError as e:
            if e.response.status_code == 404:
                self.logger.error("No pagerduty users found")
            else:
                raise e
        except PDClientError as e:
            self.logger.error(f"Non-transient network or client error: {e.msg}")

        return []

    async def get_services(self) -> list[dict]:
        try:
            services_iter = self.session.iter_all("services")

            return list(services_iter)
        except PDHTTPError as e:
            if e.response.status_code == 404:
                self.logger.error("No pagerduty services found")
            else:
                raise e
        except PDClientError as e:
            self.logger.error(f"Non-transient network or client error: {e.msg}")

        return []

    async def get_on_calls(self, params: dict = None) -> list[dict]:
        try:
            if params is None:
                params = {"since": self.start_date}

            on_calls_iter = self.session.iter_all("oncalls", params)

            return list(on_calls_iter)
        except PDHTTPError as e:
            if e.response.status_code == 404:
                self.logger.error("No pagerduty onCalls found")
            else:
                raise e
        except PDClientError as e:
            self.logger.error(f"Non-transient network or client error: {e.msg}")

        return []

    async def get_incidents(self, params: dict = None) -> list[dict]:
        if params is None:
            params = {"since": self.start_date}

        try:
            incidents_iter = self.session.iter_all("incidents", params)

            return list(incidents_iter)
        except PDHTTPError as e:
            if e.response.status_code == 404:
                self.logger.error("No pagerduty incidents found")
            else:
                raise

        except PDClientError as e:
            self.logger.error(f"Non-transient network or client error: {e.msg}")

        return []

    async def get_schedules(self, params: dict = None) -> list[dict]:
        try:
            schedules_iter = self.session.iter_all("schedules", params)

            return list(schedules_iter)
        except PDHTTPError as e:
            if e.response.status_code == 404:
                self.logger.error("No pagerduty incidents found")
            else:
                raise e
        except PDClientError as e:
            self.logger.error(f"Non-transient network or client error: {e.msg}")

        return []

    async def get_escalation_policies(self, params: dict = None) -> list[dict]:
        try:
            policies_iter = self.session.iter_all("escalation_policies", params)

            return list(policies_iter)
        except PDHTTPError as e:
            if e.response.status_code == 404:
                self.logger.error("No pagerduty incidents found")
            else:
                raise e
        except PDClientError as e:
            self.logger.error(f"Non-transient network or client error: {e.msg}")

        return []
