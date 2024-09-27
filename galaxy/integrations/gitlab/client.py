import logging
from datetime import datetime, timedelta

import aiohttp
from aiohttp import ClientResponseError

from galaxy.core.models import Config
from galaxy.core.utils import make_request
from galaxy.integrations.gitlab.queries import Queries

__all__ = ["GitlabClient"]


class GitlabClient:
    def __init__(self, config: Config, logger: logging.Logger):
        self.logger = logger
        self.queries = Queries()
        self.config = config
        self.url_graphql = f"{config.integration.properties['url']}/graphql"
        self.headers = {
            "Authorization": f"Bearer {config.integration.properties['secretToken']}",
            "Content-Type": "application/json",
        }

    async def get_repos(self) -> list[dict]:
        all_repos = []
        cursor = None
        time_delta = datetime.now() - timedelta(days=int(self.config.integration.properties["daysOfHistory"]))
        while True:
            query = self.queries.get_repos(after=cursor)
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                data = await make_request(session, "POST", self.url_graphql, headers=self.headers, json=query)
            for repo in data["data"]["projects"]["nodes"]:
                if repo["archived"] is True or datetime.strptime(repo["updatedAt"], "%Y-%m-%dT%H:%M:%SZ") < time_delta:
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
        time_delta = datetime.now() - timedelta(days=int(self.config.integration.properties["daysOfHistory"]))
        while True:
            query = self.queries.get_group_repos(group, after=cursor)
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                data = await make_request(session, "POST", self.url_graphql, headers=self.headers, json=query)
            for repo in data["data"]["group"]["projects"]["nodes"]:
                if repo["archived"] is True or datetime.strptime(repo["updatedAt"], "%Y-%m-%dT%H:%M:%SZ") < time_delta:
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
            query = self.queries.get_issues(repository, after=cursor, history_days=history_days)
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                data = await make_request(session, "POST", self.url_graphql, headers=self.headers, json=query)

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
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                data = await make_request(session, "POST", self.url_graphql, headers=self.headers, json=query)
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
            query = self.queries.get_pipelines(repository, after=cursor, history_days=history_days)
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                data = await make_request(session, "POST", self.url_graphql, headers=self.headers, json=query)
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
            query = self.queries.get_environments(repository, after=cursor)
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                data = await make_request(session, "POST", self.url_graphql, headers=self.headers, json=query)

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
        # TODO: We should stop pagination once we hit deployments older than:
        # history_days_timestamp = (datetime.now() - timedelta(days=history_days))

        all_deployments = []
        cursor = None
        while True:
            query = self.queries.get_deployments(repository, environment, after=cursor)
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                data = await make_request(session, "POST", self.url_graphql, headers=self.headers, json=query)

            if "errors" in data:
                raise Exception(f"Failed to fetch deployments: {data['errors']}")

            deployments = data.get("data", {}).get("project", {}).get("environment", {}).get("deployments", {})
            if not deployments.get("edges"):
                return all_deployments

            edges = deployments["edges"]
            page_info = deployments["pageInfo"]
            all_deployments.extend(edges)
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]
        return all_deployments

    async def get_group(self, group) -> dict:
        cursor = None
        query = self.queries.get_group(group, after=cursor)
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            data = await make_request(session, "POST", self.url_graphql, headers=self.headers, json=query)
        return data

    async def get_users(self, group_id):
        all_users = []
        cursor = None
        group_id = f"gid://gitlab/Group/{group_id}"
        while True:
            query = self.queries.get_users(group_id, after=cursor)
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                data = await make_request(session, "POST", self.url_graphql, headers=self.headers, json=query)
                all_users.extend(data["data"]["users"]["nodes"])
            page_info = data["data"]["users"]["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]
        return all_users

    async def get_groups(self) -> list[dict]:
        all_groups = []
        page = 1
        while True:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                try:
                    async with session.request(
                        "GET",
                        f"{self.config.integration.properties['url']}/v4/groups?page={page}&per_page=100",
                        headers=self.headers,
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
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            data = await make_request(session, "POST", self.url_graphql, headers=self.headers, json=query)

        return data["data"]["currentUser"]

    async def get_user_by_username(self, username: str) -> dict:
        query = self.queries.get_user_by_username(username)
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            data = await make_request(session, "POST", self.url_graphql, headers=self.headers, json=query)

        return data["data"]["user"]
