import base64
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Union

import aiohttp
from github import Auth, Github
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_random_exponential

from galaxy.core.utils import make_request
from galaxy.integrations.github.queries import QueryType, build_graphql_query

__all__ = ["GithubClient"]


class GithubClient:
    def __init__(self, config, logger, token):
        self.config = config
        self.logger = logger
        self.headers = {
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Accept": "application/vnd.github+json",
        }

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

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_random_exponential(min=1, max=60),
        before_sleep=before_sleep_log(logging.getLogger("galaxy"), logging.WARNING),
        reraise=True,
    )
    async def _fetch_data(self, query) -> dict:
        url = f"{self.config.integration.properties['url']}/graphql"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            response = await make_request(session, "POST", url, headers=self.headers, json=query)
        return response

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_random_exponential(min=1, max=60),
        before_sleep=before_sleep_log(logging.getLogger("galaxy"), logging.WARNING),
        reraise=True,
    )
    async def list_repositories_with_access_token(
        self, *, limit: int | None = None, include_archived: bool = False, include_old: bool = False
    ) -> list:
        url = f"{self.config.integration.properties['url']}/installation/repositories"
        page = 1
        repos_list = []
        while True:
            params = {"page": page, "per_page": 100}
            time_delta = datetime.now() - timedelta(days=self.config.integration.properties["daysOfHistory"])

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                response = await make_request(session, "GET", url, headers=self.headers, params=params)
                repos = response["repositories"]
            if not repos:
                break
            page += 1
            for repo in repos:
                if (include_archived or repo["archived"] is False) and (
                    include_old or datetime.strptime(repo["pushed_at"], "%Y-%m-%dT%H:%M:%SZ") >= time_delta
                ):
                    repos_list.append(repo)

                    if limit and len(repos_list) >= limit:
                        return repos_list

        return repos_list

    async def get_repo(self, organization: str, repo: str) -> Dict[str, Union[str, int]]:
        query = build_graphql_query(query_type=QueryType.REPOSITORY, repo_id=f"{organization}/{repo}")
        response = await self._fetch_data(query)
        return response["data"]["repository"]

    async def get_all_requests(
        self, organization: str, repo: str, states: List[str]
    ) -> List[Dict[str, Union[str, int]]]:
        all_pull_requests = []
        cursor = None
        while True:
            query = build_graphql_query(
                query_type=QueryType.PULL_REQUESTS, repo_id=f"{organization}/{repo}", states=states, after=cursor
            )
            response = await self._fetch_data(query)
            edges = response["data"]["repository"]["pullRequests"]["edges"]
            page_info = response["data"]["repository"]["pullRequests"]["pageInfo"]
            all_pull_requests.extend(edge["node"] for edge in edges)
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]

        return all_pull_requests

    # TODO: Not using "daysOfHistory" to fetch only recent requests
    async def get_all_issues(self, organization: str, repo: str, state: str) -> List[Dict[str, Union[str, int]]]:
        all_issues = []
        cursor = None

        while True:
            query = build_graphql_query(
                query_type=QueryType.ISSUES, repo_id=f"{organization}/{repo}", after=cursor, state=state
            )
            response = await self._fetch_data(query)
            edges = response["data"]["search"]["edges"]
            page_info = response["data"]["search"]["pageInfo"]
            all_issues.extend(edge["node"] for edge in edges)
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]

        return all_issues

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_random_exponential(min=1, max=60),
        before_sleep=before_sleep_log(logging.getLogger("galaxy"), logging.WARNING),
        reraise=True,
    )
    async def get_all_workflows(self, organization: str, repo: str) -> List[Dict[str, Union[str, int]]]:
        all_workflows = []
        page = 1
        while True:
            url = f"{self.config.integration.properties['url']}/repos/{organization}/{repo}/actions/workflows"
            params = {"page": page, "per_page": 100}
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                workflows_data = await make_request(session, "GET", url, headers=self.headers, params=params)

            workflows = workflows_data.get("workflows", [])
            if not workflows:
                break
            all_workflows.extend(workflows)
            page += 1

        return all_workflows

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_random_exponential(min=1, max=60),
        before_sleep=before_sleep_log(logging.getLogger("galaxy"), logging.WARNING),
        reraise=True,
    )
    async def get_all_workflow_runs(
        self, organization: str, repo: str, workflow_id: str
    ) -> List[Dict[str, Union[str, int]]]:
        all_workflow_runs = []
        page = 1
        history_days_timestamp = (
            datetime.now() - timedelta(days=int(self.config.integration.properties["daysOfHistory"]))
        ).isoformat()
        while True:
            url = f"{self.config.integration.properties['url']}/repos/{organization}/{repo}/actions/workflows/{workflow_id}/runs"
            params = {"page": page, "per_page": 100, "created": f">{history_days_timestamp}"}
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                workflow_runs_data = await make_request(session, "GET", url, headers=self.headers, params=params)
            workflow_runs = workflow_runs_data.get("workflow_runs", [])
            if not workflow_runs:
                break
            all_workflow_runs.extend(workflow_runs)
            page += 1

        return all_workflow_runs

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_random_exponential(min=1, max=60),
        before_sleep=before_sleep_log(logging.getLogger("galaxy"), logging.WARNING),
        reraise=True,
    )
    async def get_all_workflow_jobs(self, organization: str, repo: str, run_id: str) -> list:
        all_jobs = []
        page = 1
        while True:
            url = f"{self.config.integration.properties['url']}/repos/{organization}/{repo}/actions/runs/{run_id}/jobs"
            params = {"page": page, "per_page": 100}  # Pagination parameters
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                workflow_jobs_data = await make_request(session, "GET", url, headers=self.headers, params=params)
            workflow_jobs = workflow_jobs_data.get("jobs", [])
            if not workflow_jobs:
                break
            page += 1
            all_jobs.extend(workflow_jobs)

        return all_jobs

    # TODO: No support for pagination
    async def get_all_members(self, organization: str) -> List[Dict[str, Union[str, int]]]:
        all_members = []
        cursor = None
        query = build_graphql_query(query_type=QueryType.MEMBERS, owner=organization, after=cursor)
        response = await self._fetch_data(query)
        try:
            edges = response["data"]["organization"]["membersWithRole"]["edges"]
        except TypeError:
            print(f"Error: {response}")
            edges = []
        all_members.extend(edges)

        return all_members

    # TODO: No support for pagination
    async def get_all_teams(self, organization: str) -> List[dict]:
        cursor = None
        query = build_graphql_query(query_type=QueryType.TEAMS, owner=organization, after=cursor)
        response = await self._fetch_data(query)
        try:
            teams = response["data"]["organization"]["teams"]["nodes"]
        except TypeError:
            print(f"Error: {response}")
            teams = []

        return teams
