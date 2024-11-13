import base64
from collections.abc import Iterable
from datetime import datetime, timedelta
from itertools import count
from types import TracebackType
from typing import Any

from github import Auth, Github

from galaxy.integrations.github.queries import QueryType, build_graphql_query
from galaxy.utils.parsers import to_bool
from galaxy.utils.requests import ClientSession, RequestError, RetryPolicy, create_session, make_request

__all__ = ["GithubClient"]


class GithubClient:
    @staticmethod
    def get_access_token(
        app_id: str, app_private_key: str, app_installation_id: str = "", app_auth: bool = False
    ) -> str:
        """Gets an access token for the Github API.

        Args:
            app_id (str): The Github app ID.
            app_installation_id (str): The Github app installation ID.
            app_private_key (str): The Github app private key.
            app_auth (bool): Whether to return and application token or installation token

        Returns:
            str: The access token.
        """
        # This is a temporary implementation to get the integration working.
        # There is no need to have this package dependency
        auth = Auth.AppAuth(app_id=app_id, private_key=base64.b64decode(app_private_key).decode("utf-8"))
        if app_auth:
            return auth.create_jwt()
        else:
            gh = Github(auth=auth.get_installation_auth(int(app_installation_id)))
            return gh._Github__requester.auth.token

    def __init__(self, config, logger, token):
        self.config = config
        self.logger = logger
        self.history_limit_timestamp = datetime.now() - timedelta(days=self.days_of_history)
        self.repo_activity_limit_timestamp = datetime.now() - timedelta(days=self.days_of_history * 3)

        self._headers = {
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Accept": "application/vnd.github+json",
        }
        self._session: ClientSession | None = None
        self._retry_policy = RetryPolicy(logger=self.logger)

    async def __aenter__(self) -> "GithubClient":
        self._session = create_session(timeout=self.timeout, headers=self._headers)
        return self

    async def __aexit__(self, exc_type: type, exc: Exception, tb: TracebackType) -> None:
        await self.close()

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()

    @property
    def days_of_history(self) -> int:
        days = int(self.config.integration.properties["daysOfHistory"])
        if days < 1:
            self.logger.warning("Invalid days of history, using default value 30")
            return 30

        return days

    @property
    def base_url(self) -> str:
        return self.config.integration.properties["url"]

    @property
    def timeout(self) -> int:
        timeout = int(self.config.integration.properties["timeout"])
        if timeout < 1:
            self.logger.warning("Invalid timeout, using default value 60")
            return 60

        return timeout

    @property
    def ignore_archived_repos(self) -> bool:
        return to_bool(self.config.integration.properties.get("ignoreArchived", True))

    @property
    def page_size(self) -> int:
        page_size = int(self.config.integration.properties.get("pageSize", 50))
        if page_size < 1 or page_size > 100:
            self.logger.warning("Invalid page size, using default value 50")
            return 50

        return page_size

    @property
    def ignore_old_repos(self) -> bool:
        return to_bool(self.config.integration.properties.get("ignoreOld", True))

    def build_repo_id(self, organization: str, repo: str) -> str:
        return f"{organization}/{repo}"

    async def _make_request(
        self,
        method: str,
        url: str,
        *,
        retry: bool = True,
        raise_on_error: bool = False,
        none_on_404: bool = True,
        **kwargs: Any,
    ) -> Any:
        try:
            return await make_request(
                self._session,
                method,
                url,
                **kwargs,
                logger=self.logger,
                retry_policy=self._retry_policy,
                retry=retry,
                none_on_404=none_on_404,
            )
        except RequestError as e:
            if raise_on_error:
                raise
            self.logger.error(f"Error while making request, defaulting to empty response. ({e})")
            return None

    async def _make_graphql_request(self, query: dict[str, Any]) -> Any:
        response = await self._make_request("POST", f"{self.base_url}/graphql", json=query, raise_on_error=True)
        if response.get("errors"):
            self.logger.warning("GraphQL error: %r", response["errors"])
        return response

    def _parse_datetime(self, datetime_str: str) -> datetime:
        return datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%SZ")

    async def get_repos(
        self, *, limit: int | None = None, ignore_archived: bool = True, ignore_old: bool = True, page_size: int = 50
    ) -> list:
        repos_list = []

        url = f"{self.base_url}/installation/repositories"
        for page_num in count(start=1):
            response = await self._make_request("GET", url, params={"page": page_num, "per_page": page_size})
            if response is None:
                break

            repos = response["repositories"]
            if not repos:
                break

            for repo in repos:
                if ignore_archived and repo["archived"]:
                    continue
                if ignore_old and self._parse_datetime(repo["pushed_at"]) < self.repo_activity_limit_timestamp:
                    continue

                repos_list.append(repo)
                if limit and len(repos_list) >= limit:
                    return repos_list

        return repos_list

    async def get_repo(self, organization: str, repo: str) -> dict[str, str | int]:
        query = build_graphql_query(query_type=QueryType.REPOSITORY, repo_id=self.build_repo_id(organization, repo))
        response = await self._make_graphql_request(query)
        return response["data"]["repository"]

    async def get_pull_requests(self, organization: str, repo: str, states: list[str]) -> list[dict[str, str | int]]:
        all_pull_requests = []

        cursor = None
        while True:
            query = build_graphql_query(
                query_type=QueryType.PULL_REQUESTS,
                repo_id=self.build_repo_id(organization, repo),
                states=states,
                after=cursor,
                page_size=self.page_size,
            )
            response = await self._make_graphql_request(query)

            edges = response["data"]["repository"]["pullRequests"]["edges"]
            if not edges:
                break
            all_pull_requests.extend(edge["node"] for edge in edges)

            page_info = response["data"]["repository"]["pullRequests"]["pageInfo"]
            if (
                not page_info["hasNextPage"]
                or self._parse_datetime(edges[-1]["node"]["createdAt"]) < self.history_limit_timestamp
            ):
                break

            cursor = page_info["endCursor"]

        return all_pull_requests

    async def get_issues(self, organization: str, repo: str, state: str) -> list[dict[str, str | int]]:
        all_issues = []

        cursor = None
        while True:
            query = build_graphql_query(
                query_type=QueryType.ISSUES,
                repo_id=self.build_repo_id(organization, repo),
                after=cursor,
                state=state,
                page_size=self.page_size,
            )
            response = await self._make_graphql_request(query)

            edges = response["data"]["search"]["edges"]
            if not edges:
                break
            all_issues.extend(edge["node"] for edge in edges)

            page_info = response["data"]["search"]["pageInfo"]
            if (
                not page_info["hasNextPage"]
                or self._parse_datetime(edges[-1]["node"]["createdAt"]) < self.history_limit_timestamp
            ):
                break
            cursor = page_info["endCursor"]

        return all_issues

    async def get_workflows(self, organization: str, repo: str) -> list[dict[str, str | int]]:
        all_workflows = []

        url = f"{self.base_url}/repos/{organization}/{repo}/actions/workflows"
        for page_num in count(start=1):
            response = await self._make_request("GET", url, params={"page": page_num, "per_page": self.page_size})
            if response is None:
                break

            workflows = response.get("workflows")
            if not workflows:
                break
            all_workflows.extend(workflows)

        return all_workflows

    async def get_workflow_runs(self, organization: str, repo: str, workflow_id: str) -> list[dict[str, str | int]]:
        all_workflow_runs = []

        url = f"{self.base_url}/repos/{organization}/{repo}/actions/workflows/{workflow_id}/runs"
        for page_num in count(start=1):
            response = await self._make_request(
                "GET",
                url,
                params={
                    "page": page_num,
                    "per_page": self.page_size,
                    "created": f">{self.history_limit_timestamp.isoformat()}",
                },
            )
            if response is None:
                break

            workflow_runs = response.get("workflow_runs", [])
            if not workflow_runs:
                break
            all_workflow_runs.extend(workflow_runs)

        return all_workflow_runs

    async def get_workflow_run_jobs(self, organization: str, repo: str, run_id: str) -> list[Any]:
        all_jobs = []

        url = f"{self.base_url}/repos/{organization}/{repo}/actions/runs/{run_id}/jobs"
        for page_num in count(start=1):
            response = await self._make_request("GET", url, params={"page": page_num, "per_page": self.page_size})
            if response is None:
                break

            workflow_jobs = response.get("jobs", [])
            if not workflow_jobs:
                break
            all_jobs.extend(workflow_jobs)

        return all_jobs

    async def get_members(self, organization: str) -> list[dict[str, str | int]]:
        all_members = []
        cursor = None
        while True:
            query = build_graphql_query(
                query_type=QueryType.MEMBERS, owner=organization, after=cursor, page_size=self.page_size
            )
            response = await self._make_graphql_request(query)

            edges = response["data"]["organization"]["membersWithRole"]["edges"]
            if not edges:
                break
            all_members.extend(edges)

            page_info = response["data"]["organization"]["membersWithRole"]["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]

        return all_members

    async def get_teams(self, organization: str) -> list[dict]:
        all_teams = []
        cursor = None
        while True:
            query = build_graphql_query(
                query_type=QueryType.TEAMS, owner=organization, after=cursor, page_size=self.page_size
            )
            response = await self._make_graphql_request(query)
            teams = response.get("data", {}).get("organization", {}).get("teams", {}).get("nodes", [])
            if not teams:
                break

            for team in teams:
                name = team["name"]
                team["members"] = {"nodes": []}
                team["members"]["nodes"] = await self.get_team_members(organization, name)
                team["repositories"] = {"nodes": []}
                team["repositories"]["nodes"] = await self.get_team_repositories(organization, name)

            all_teams.extend(teams)

            page_info = response["data"]["organization"]["teams"]["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]

        return all_teams

    async def get_team_members(self, organization: str, team_id: str) -> list[dict]:
        all_members = []
        cursor = None
        while True:
            query = build_graphql_query(
                query_type=QueryType.TEAM_MEMBERS,
                owner=organization,
                team=team_id,
                after=cursor,
                page_size=self.page_size,
            )
            response = await self._make_graphql_request(query)

            team = response["data"]["organization"]["team"]
            if not team:
                break

            all_members.extend(team.get("members", {}).get("nodes", []))

            page_info = team["members"]["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]

        return all_members

    async def get_team_repositories(self, organization: str, team_id: str) -> list[dict]:
        all_repositories = []
        cursor = None
        while True:
            query = build_graphql_query(
                query_type=QueryType.TEAM_REPOS,
                owner=organization,
                team=team_id,
                after=cursor,
                page_size=self.page_size,
            )
            response = await self._make_graphql_request(query)

            team = response["data"]["organization"]["team"]
            if not team:
                break

            all_repositories.extend(team.get("repositories", {}).get("nodes", []))

            page_info = team["repositories"]["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]

        return all_repositories

    async def get_environments(self, organization: str, repo: str) -> list[dict[str, str | int]]:
        all_environments = []

        url = f"{self.config.integration.properties['url']}/repos/{organization}/{repo}/environments"
        for page_num in count(start=1):
            response = await self._make_request("GET", url, params={"page": page_num, "per_page": self.page_size})
            if response is None:
                break

            environments = response.get("environments", [])
            if not environments:
                break
            all_environments.extend(environments)

        return all_environments

    async def get_deployments(
        self, organization: str, repo: str, environments: Iterable[str] | None = None
    ) -> list[dict[str, str | int]]:
        all_deployments = []
        cursor = None
        while True:
            query = build_graphql_query(
                query_type=QueryType.DEPLOYMENTS,
                repo_id=self.build_repo_id(organization, repo),
                environments=environments,
                after=cursor,
                page_size=self.page_size,
            )
            response = await self._make_graphql_request(query)

            edges = response["data"]["repository"]["deployments"]["edges"]
            if not edges:
                break
            all_deployments.extend(edge["node"] for edge in edges)

            page_info = response["data"]["repository"]["deployments"]["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]

        return all_deployments
