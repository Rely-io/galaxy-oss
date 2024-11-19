import logging
from datetime import UTC, datetime, timedelta
from itertools import count
from types import TracebackType

from aiohttp import ClientResponseError, ClientSession

from galaxy.core.models import Config
from galaxy.integrations.gitlab.queries import Queries
from galaxy.utils.parsers import to_bool
from galaxy.utils.requests import RetryPolicy, create_session, make_request

__all__ = ["GitlabClient"]


class GitlabClient:
    def __init__(self, config: Config, logger: logging.Logger):
        self.logger = logger
        self.queries = Queries()
        self.config = config
        self.url_graphql = f"{config.integration.properties['url']}/graphql"

        token = config.integration.properties.get("secretToken")
        if not token:
            raise ValueError("No secret token provided")

        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        self.page_size = int(config.integration.properties.get("pageSize", 50))
        if self.page_size < 1 or self.page_size > 100:
            self.logger.warning("Invalid page size, using default value 50")
            self.page_size = 50

        self.days_of_history = int(config.integration.properties.get("daysOfHistory", 30))
        if self.days_of_history < 1:
            self.logger.warning("Invalid days of history, using default value 30")
            self.days_of_history = 30

        self.timeout = int(config.integration.properties.get("timeout", 60))
        if self.timeout < 1:
            self.logger.warning("Invalid timeout, using default value 60")
            self.timeout = 60

        self.ignore_archived_repos = to_bool(config.integration.properties.get("ignoreArchived", True))
        self.history_limit_timestamp = datetime.now(tz=UTC) - timedelta(days=self.days_of_history)

        self.session: ClientSession | None = None
        self.retry_policy = RetryPolicy(logger=self.logger, wait_multiplier=2, wait_min=60, wait_max=120)

    async def __aenter__(self) -> "GitlabClient":
        self.session = create_session(timeout=self.timeout, headers=self.headers)
        return self

    async def __aexit__(self, exc_type: type, exc: Exception, tb: TracebackType) -> None:
        await self.close()

    async def close(self) -> None:
        if self.session is not None:
            await self.session.close()

    async def get_repos(self) -> list[dict]:
        all_repos = []
        cursor = None
        time_delta = datetime.now() - timedelta(days=self.days_of_history)
        while True:
            query = self.queries.get_repos(after=cursor, page_size=self.page_size)

            data = await make_request(
                self.session, "POST", self.url_graphql, json=query, retry_policy=self.retry_policy
            )

            for repo in data["data"]["projects"]["nodes"]:
                if (repo["archived"] is True and self.ignore_archived_repos) or datetime.strptime(
                    repo["updatedAt"], "%Y-%m-%dT%H:%M:%SZ"
                ) < time_delta:
                    try:
                        data["data"]["projects"]["nodes"].remove(repo)
                    except ValueError:
                        self.logger.info("Item not found in list")
            all_repos.extend(data["data"]["projects"]["nodes"])
            page_info = data["data"]["projects"]["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]
        return all_repos

    async def get_group_repos(self, group: dict) -> list[dict]:
        all_repos = []
        cursor = None
        time_delta = datetime.now() - timedelta(days=self.days_of_history)
        while True:
            query = self.queries.get_group_repos(group, after=cursor, page_size=self.page_size)

            data = await make_request(
                self.session, "POST", self.url_graphql, json=query, retry_policy=self.retry_policy
            )

            for repo in data["data"]["group"]["projects"]["nodes"]:
                if (repo["archived"] is True and self.ignore_archived_repos) or datetime.strptime(
                    repo["updatedAt"], "%Y-%m-%dT%H:%M:%SZ"
                ) < time_delta:
                    try:
                        data["data"]["group"]["projects"]["nodes"].remove(repo)
                    except ValueError:
                        self.logger.info("Item not found in list")
            all_repos.extend(data["data"]["group"]["projects"]["nodes"])
            page_info = data["data"]["group"]["projects"]["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]
        return all_repos

    async def get_issues(self, repository: dict, history_days: int) -> list[dict]:
        all_issues = []
        cursor = None
        while True:
            query = self.queries.get_issues(
                repository, after=cursor, history_days=history_days, page_size=self.page_size
            )

            data = await make_request(
                self.session, "POST", self.url_graphql, json=query, retry_policy=self.retry_policy
            )

            raw_issues = data.get("data", {}).get("project", {}).get("issues", [])
            all_issues.extend(raw_issues.get("edges", []))

            page_info = raw_issues["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]
        return all_issues

    async def get_merge_requests(self, repository: dict, history_days: int) -> list[dict]:
        all_merge_requests = []
        cursor = None
        while True:
            query = self.queries.get_merge_requests(repository, after=cursor, history_days=history_days)

            data = await make_request(
                self.session, "POST", self.url_graphql, json=query, retry_policy=self.retry_policy
            )

            all_merge_requests.extend(data["data"]["project"]["mergeRequests"]["edges"])
            page_info = data["data"]["project"]["mergeRequests"]["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]
        return all_merge_requests

    async def get_pipelines(self, repository: dict, history_days: int) -> list[dict]:
        all_pipelines = []
        cursor = None
        while True:
            query = self.queries.get_pipelines(
                repository, after=cursor, history_days=history_days, page_size=self.page_size
            )

            data = await make_request(
                self.session, "POST", self.url_graphql, json=query, retry_policy=self.retry_policy
            )

            edges = data["data"]["project"]["pipelines"]["edges"]
            page_info = data["data"]["project"]["pipelines"]["pageInfo"]
            all_pipelines.extend(edges)
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]
        return all_pipelines

    async def get_environments(self, repository: dict) -> list[dict]:
        all_environments = []
        cursor = None
        while True:
            query = self.queries.get_environments(repository, after=cursor, page_size=self.page_size)

            data = await make_request(
                self.session, "POST", self.url_graphql, json=query, retry_policy=self.retry_policy
            )

            environments = data["data"]["project"]["environments"]
            if not environments:
                return all_environments

            edges = environments["edges"]
            page_info = environments["pageInfo"]
            all_environments.extend(edges)
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]
        return all_environments

    async def get_deployments(self, repository: dict, environment: str, history_days: int) -> list[dict]:
        history_days_timestamp = datetime.now() - timedelta(days=history_days)

        all_deployments = []
        cursor = None
        while True:
            query = self.queries.get_deployments(repository, environment, after=cursor, page_size=self.page_size)

            data = await make_request(
                self.session, "POST", self.url_graphql, json=query, retry_policy=self.retry_policy
            )

            if "errors" in data:
                raise Exception(f"Failed to fetch deployments: {data['errors']}")

            deployments = data.get("data", {}).get("project", {}).get("environment", {}).get("deployments", {})
            if not deployments.get("edges"):
                return all_deployments

            edges = deployments["edges"]

            # Filter deployments that are older than history_days
            recent_deployments = [
                edge
                for edge in edges
                if datetime.strptime(edge["node"]["createdAt"], "%Y-%m-%dT%H:%M:%SZ") >= history_days_timestamp
            ]

            page_info = deployments["pageInfo"]
            all_deployments.extend(recent_deployments)
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]
        return all_deployments

    async def get_group(self, group) -> dict:
        cursor = None
        query = self.queries.get_group(group, after=cursor, page_size=self.page_size)

        data = await make_request(self.session, "POST", self.url_graphql, json=query, retry_policy=self.retry_policy)

        return data

    async def get_users(self, group_id):
        all_users = []
        cursor = None
        group_id = f"gid://gitlab/Group/{group_id}"
        while True:
            query = self.queries.get_users(group_id, after=cursor, page_size=self.page_size)

            data = await make_request(
                self.session, "POST", self.url_graphql, json=query, retry_policy=self.retry_policy
            )

            if "errors" in data:
                raise Exception(f"Failed to fetch users: {data['errors']}")

            users = data.get("data", {}).get("users", {})
            if not users.get("nodes"):
                return all_users

            nodes = users["nodes"]
            all_users.extend(nodes)

            page_info = users["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]
        return all_users

    async def get_groups(self) -> list[dict]:
        all_groups = []
        page = 1
        while True:
            try:
                async with self.session.request(
                    "GET",
                    f"{self.config.integration.properties['url']}/v4/groups?page={page}&per_page={self.page_size}",
                ) as response:
                    if response.status // 100 == 2:
                        data = await response.json()
                    response.raise_for_status()
            except ClientResponseError as e:
                raise Exception(f"Client server integration API error: {e.status} {e.message}")

            all_groups.extend(data)
            page = response.headers.get("x-next-page", "")
            if page == "":
                break

        return all_groups

    async def get_user(self) -> dict:
        query = self.queries.get_user()

        data = await make_request(self.session, "POST", self.url_graphql, json=query, retry_policy=self.retry_policy)

        return data["data"]["currentUser"]

    async def get_user_by_username(self, username: str) -> dict:
        query = self.queries.get_user_by_username(username)

        data = await make_request(self.session, "POST", self.url_graphql, json=query, retry_policy=self.retry_policy)

        return data["data"]["user"]

    async def get_file(self, repository_path: str, file_path: str) -> dict:
        query = self.queries.get_file(repository_path, file_path)

        data = await make_request(self.session, "POST", self.url_graphql, json=query, retry_policy=self.retry_policy)

        if "errors" in data:
            self.logger.warning(f"Failed to fetch file {file_path}: {data['errors']}")
            return None

        file_data = data.get("data", {}).get("project", {}).get("repository", {}).get("blobs", {}).get("nodes", [])
        if not file_data:
            self.logger.debug(f"File {file_path} not found")
            return None

        return file_data[0]

    async def get_commits(
        self, project_id: str | int, branch: str, *, exclude_merge_commits: bool = True
    ) -> list[dict[str, str | int]]:
        all_commits = []

        url = f"{self.config.integration.properties['url']}/v4/projects/{project_id}/repository/commits"
        for page_num in count(start=1):
            # TODO: add reusable "make_request" logic like it is done in the github client
            try:
                async with self.session.request(
                    "GET",
                    url,
                    params={
                        "page": page_num,
                        "per_page": self.page_size,
                        "pagination": "keyset",
                        "ref_name": branch,
                        "since": self.history_limit_timestamp.isoformat(),
                    },
                ) as response:
                    if response.status // 100 == 2:
                        data = await response.json()
                    response.raise_for_status()
            except ClientResponseError as e:
                if e.status == 404:
                    self.logger.warning("Unable to fetch commits for project %s: project not found", project_id)
                    break
                raise Exception(f"Client server integration API error: {e.status} {e.message}")

            if not data:
                break

            all_commits.extend(
                [commit for commit in data if not exclude_merge_commits or not self._is_merge_commit(commit)]
            )

        return all_commits

    def _is_merge_commit(self, commit: dict) -> bool:
        return len(commit.get("parent_ids") or []) > 1
