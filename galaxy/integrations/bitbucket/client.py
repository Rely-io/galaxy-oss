import logging

import aiohttp
from aiohttp import ClientResponseError

from galaxy.core.models import Config
from galaxy.core.utils import make_request
from datetime import datetime, timedelta
import base64

__all__ = ["BitbucketClient"]


class BitbucketClient:
    def __init__(self, config: Config, logger: logging.Logger):
        self.logger = logger
        self.config = config
        self.url = "https://api.bitbucket.org/2.0"
        self.auth_token = None
        self.headers = None

    async def init_credentials(self):
        self.auth_token = await self.get_auth_token(self.config.integration.properties["refreshToken"])
        self.headers = {"Authorization": f"Bearer {self.auth_token}", "Content-Type": "application/json"}

    async def get_auth_token(self, refresh_token: str) -> str:
        client_id = self.config.integration.properties["clientId"]
        client_secret = self.config.integration.properties["clientSecret"]

        if not client_id or not client_secret:
            raise Exception("Missing Bitbucket APP OAuth credentials")

        encoded_credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode("utf-8")

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            try:
                response = await make_request(
                    session,
                    "POST",
                    "https://bitbucket.org/site/oauth2/access_token",
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Authorization": f"Basic {encoded_credentials}",
                    },
                    data={"grant_type": "refresh_token", "refresh_token": refresh_token},
                )
            except ClientResponseError as e:
                raise Exception(f"Client server integration API error: {e.status} {e.message}")

        # Assuming the response has the JSON structure with access token like {"access_token": "your_token", ...}
        access_token = response.get("access_token")
        if not access_token:
            raise Exception("Failed to retrieve access token from response.")

        return access_token

    async def get_workspace(self, workspace_slug: str) -> list[dict]:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            try:
                response = await make_request(
                    session, "GET", f"{self.url}/workspaces/{workspace_slug}", headers=self.headers
                )
            except ClientResponseError as e:
                raise Exception(f"Client server integration API error: {e.status} {e.message}")

        return response

    async def get_projects(self, workspace_slug: str) -> list[dict]:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            try:
                response = await make_request(
                    session, "GET", f"{self.url}/workspaces/{workspace_slug}/projects", headers=self.headers
                )
                projects = response["values"]
            except ClientResponseError as e:
                raise Exception(f"Client server integration API error: {e.status} {e.message}")
        return projects

    async def get_users(self, workspace_slug: str) -> list[dict]:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            try:
                response = await make_request(
                    session, "GET", f"{self.url}/workspaces/{workspace_slug}/permissions", headers=self.headers
                )
                users = response["values"]
            except ClientResponseError as e:
                raise Exception(f"Client server integration API error: {e.status} {e.message}")
        return users

    async def get_repositories(self, workspace_slug: str) -> list[dict]:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            try:
                response = await make_request(
                    session, "GET", f"{self.url}/repositories/{workspace_slug}", headers=self.headers
                )
                repositories = response["values"]
            except ClientResponseError as e:
                raise Exception(f"Client server integration API error: {e.status} {e.message}")
        return repositories

    async def get_readme(self, workspace_slug: str, repo_slug: str, branch: str) -> list[dict]:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            try:
                response = await make_request(
                    session,
                    "GET",
                    f"{self.url}/repositories/{workspace_slug}/{repo_slug}/src/{branch}/README.md",
                    headers={"Authorization": f"Bearer {self.auth_token}", "Content-Type": "text/plain"},
                )
            except ClientResponseError as e:
                raise Exception(f"Client server integration API error: {e.status} {e.message}")
        return response

    async def get_pull_requests(self, workspace_slug: str, repo_slug: str) -> list[dict]:
        start_date = (
            datetime.utcnow() - timedelta(days=int(self.config.integration.properties["daysOfHistory"]))
        ).isoformat()
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            try:
                response = await make_request(
                    session,
                    "GET",
                    f"{self.url}/repositories/{workspace_slug}/{repo_slug}/pullrequests",
                    headers=self.headers,
                    params=[("state", state) for state in ("OPEN", "MERGED", "DECLINED", "SUPERSEDED")]
                    + [("q", f"created_on>={start_date}Z")],
                )
                pull_requests = response["values"]
            except ClientResponseError as e:
                raise Exception(f"Client server integration API error: {e.status} {e.message}")
        return pull_requests

    async def get_pipelines(self, workspace_slug: str, repo_slug: str) -> list[dict]:
        start_date = (
            datetime.utcnow() - timedelta(days=int(self.config.integration.properties["daysOfHistory"]))
        ).isoformat()
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            try:
                response = await make_request(
                    session,
                    "GET",
                    f"{self.url}/repositories/{workspace_slug}/{repo_slug}/pipelines",
                    headers=self.headers,
                    params=[("q", f"created_on>={start_date}Z")],
                )
                pipelines = response["values"]
            except ClientResponseError as e:
                raise Exception(f"Client server integration API error: {e.status} {e.message}")
        return pipelines

    async def get_environments(self, workspace_slug: str, repo_slug: str) -> list[dict]:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            try:
                response = await make_request(
                    session,
                    "GET",
                    f"{self.url}/repositories/{workspace_slug}/{repo_slug}/environments",
                    headers=self.headers,
                )
                environments = response["values"]
            except ClientResponseError as e:
                raise Exception(f"Client server integration API error: {e.status} {e.message}")
        return environments

    async def get_deployments(self, workspace_slug: str, repo_slug: str) -> list[dict]:
        start_date = (
            datetime.utcnow() - timedelta(days=int(self.config.integration.properties["daysOfHistory"]))
        ).isoformat()
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            try:
                response = await make_request(
                    session,
                    "GET",
                    f"{self.url}/repositories/{workspace_slug}/{repo_slug}/deployments",
                    headers=self.headers,
                    params=[("q", f"created_on>={start_date}Z")],
                )
                deployments = response["values"]
            except ClientResponseError as e:
                raise Exception(f"Client server integration API error: {e.status} {e.message}")
        return deployments
