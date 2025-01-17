from types import TracebackType

from galaxy.core.galaxy import Integration, register
from galaxy.core.models import Config
from galaxy.integrations.github.client import GithubClient
from galaxy.integrations.github.utils import (
    extract_repositories_from_team,
    extract_team_members_from_team,
    get_inactive_usernames_from_deployments,
    get_inactive_usernames_from_pull_requests,
    get_inactive_usernames_from_workflow_runs,
    map_users_to_teams,
)

__all__ = ["Github"]


DEFAULT_BRANCH_NAME: str = "main"


class Github(Integration):
    _methods = []

    PULL_REQUEST_STATUS_TO_FETCH = ["OPEN", "CLOSED", "MERGED"]
    ISSUE_STATUS_TO_FETCH = ["open", "closed"]

    # Default Group for previous members of the organization
    template_inactive_members_team = {
        "databaseId": "former-github-members",
        "name": "Former Organization Members",
        "description": "Group for all previous members of the organization.",
        "url": "",
        "repositories": {"nodes": []},
        "members": {"nodes": []},
    }

    def __init__(self, config: Config):
        super().__init__(config)
        self.client = GithubClient(
            self.config,
            self.logger,
            GithubClient.get_access_token(
                config.integration.properties["appId"],
                config.integration.properties["appPrivateKey"],
                config.integration.properties["installationId"],
            ),
        )
        self._owner = None
        self._owner_type: str | None = None

        self.users = {}
        self.teams = {}
        self.repositories = {}

        self.team_to_repos = {}
        self.team_to_users = {}

        self.repository_to_pull_requests = {}
        self.repository_to_issues = {}
        self.repository_to_workflows = {}
        self.repository_to_environments = {}
        self.repository_to_deployments = {}

        self.workflows_to_runs = {}

    async def __aenter__(self) -> "Github":
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type: type, exc: Exception, tb: TracebackType) -> None:
        await self.client.__aexit__(exc_type, exc, tb)

    @property
    def is_organization_owner(self) -> bool:
        return self._owner_type == "Organization"

    @register(_methods, group=0)
    async def owner(self) -> None:
        repo = await self.client.get_repos(limit=1, ignore_archived=False, ignore_old=False)
        if len(repo) > 0:
            self._owner = repo[0]["owner"]["login"].lower()
            self._owner_type = repo[0]["owner"]["type"]

            self.logger.info(f"Found owner of type {self._owner_type}: {self._owner!r}")
        else:
            self.logger.info("Could not find owner")

    @register(_methods, group=1)
    async def repository(self) -> list[dict]:
        if self._owner is None:
            self.logger.warning("Cannot fetch repositories: owner not found")
            return []

        repositories_metadata = await self.client.get_repos(
            ignore_archived=self.client.ignore_archived_repos,
            ignore_old=self.client.ignore_old_repos,
            page_size=self.client.page_size,
        )

        for metadata in repositories_metadata:
            content = await self.client.get_repo(metadata["owner"]["login"], metadata["name"])
            self.repositories[metadata["id"]] = {
                "id": metadata["id"],
                "slug": metadata["name"],
                "owner": metadata["owner"]["login"],
                "link": metadata["html_url"],
                "metadata": metadata,
                "default_branch": (content.get("defaultBranchRef") or {}).get("name") or DEFAULT_BRANCH_NAME,
                "content": content,
            }

        self.logger.info(f"Found {len(self.repositories)} repositories")
        repositories_mapped = await self.mapper.process("repository", list(self.repositories.values()), context={})
        return repositories_mapped

    @register(_methods, group=2)
    async def team(self) -> list[dict]:
        if self._owner is None:
            self.logger.warning("Cannot fetch teams: owner not found")
            return []

        if not self.is_organization_owner:
            self.logger.warning("Cannot fetch teams: owner is not an organization")
            return []

        self.teams = {team["databaseId"]: team for team in (await self.client.get_teams(self._owner))}
        self.teams[self.template_inactive_members_team["databaseId"]] = self.template_inactive_members_team

        for team_id, team in self.teams.items():
            self.team_to_repos[team_id] = extract_repositories_from_team(team)
            self.team_to_users[team_id] = extract_team_members_from_team(team)

        teams_mapped = await self.mapper.process("team", list(self.teams.values()), context={"owner": self._owner})
        self.logger.info(f"Found {len(self.teams)-1} teams")
        return teams_mapped

    @register(_methods, group=3)
    async def team_member(self) -> list[dict]:
        if self._owner is None:
            self.logger.warning("Cannot fetch team members: owner not found")
            return []

        if not self.is_organization_owner:
            self.logger.warning("Cannot fetch team members: owner is not an organization")
            return []

        self.users_to_teams = map_users_to_teams(self.team_to_users)

        users_raw = await self.client.get_members(self._owner)

        self.users = {}
        for user in users_raw:
            user_login = user.get("node", {}).get("login")
            self.users[user_login] = user
            self.users[user_login]["teams"] = self.users_to_teams.get(user_login, [])

        members_mapped = await self.mapper.process(
            "team_member", list(self.users.values()), context={"owner": self._owner}
        )
        self.logger.info(f"Found {len(self.teams)-1} team members")
        return members_mapped

    @register(_methods, group=4)
    async def pull_request(self) -> list[dict]:
        if self._owner is None:
            self.logger.warning("Cannot fetch pull requests: owner not found")
            return []

        prs_mapped = []
        inactive_usernames = set()
        for repo_id, repo in self.repositories.items():
            self.repository_to_pull_requests[repo_id] = await self.client.get_pull_requests(
                repo["owner"], repo["slug"], self.PULL_REQUEST_STATUS_TO_FETCH
            )

            prs_mapped.extend(
                (
                    await self.mapper.process(
                        "pull_request",
                        self.repository_to_pull_requests[repo_id],
                        context={"repositoryId": repo["id"], "repositoryName": repo["slug"]},
                    )
                )
            )

            inactive_usernames.update(
                get_inactive_usernames_from_pull_requests(self.repository_to_pull_requests[repo_id], self.users)
            )

        self.logger.info(f"Found {len(prs_mapped)} pull requests from the last {self.client.days_of_history} days")
        new_entities = await self.register_inactive_users(inactive_usernames)
        if new_entities:
            self.logger.info(f"Found {len(new_entities) - 1} inactive members associated to pull requests")

        return new_entities + prs_mapped

    # Disabled
    async def issue(self) -> list[dict]:
        if self._owner is None:
            self.logger.warning("Cannot fetch issues: owner not found")
            return []

        issues_mapped = []

        for repo_id, repo in self.repositories.items():
            repo_issues = await self.client.get_issues(repo["owner"], repo["slug"], self.ISSUE_STATUS_TO_FETCH)

            self.repository_to_pull_requests[repo_id] = repo_issues
            issues_mapped.extend(
                (
                    await self.mapper.process(
                        "pull_request",
                        repo_issues,
                        context={
                            "repository": {"name": repo["metadata"]["name"], "html_url": repo["metadata"]["html_url"]}
                        },
                    )
                )
            )

        self.logger.info(f"Found {len(issues_mapped)} issues from the last {self.client.days_of_history} days")
        return issues_mapped

    @register(_methods, group=4)
    async def workflow(self) -> list[dict]:
        if self._owner is None:
            self.logger.warning("Cannot fetch workflows: owner not found")
            return []

        workflows_mapped = []

        for repo_id, repo in self.repositories.items():
            self.repository_to_workflows[repo_id] = await self.client.get_workflows(repo["owner"], repo["slug"])
            workflows_mapped.extend(
                (
                    await self.mapper.process(
                        "workflow", self.repository_to_workflows[repo_id], context={"repositoryId": repo_id}
                    )
                )
            )

        self.logger.info(f"Found {len(workflows_mapped)} workflows from the last {self.client.days_of_history} days")
        return workflows_mapped

    @register(_methods, group=5)
    async def workflow_run(self) -> list[dict]:
        if self._owner is None:
            self.logger.warning("Cannot fetch workflow runs: owner not found")
            return []

        workflows_runs_mapped = []
        inactive_usernames = set()
        for repo_id, repo in self.repositories.items():
            for workflow in self.repository_to_workflows.get(repo_id) or []:
                self.workflows_to_runs[repo_id] = await self.client.get_workflow_runs(
                    repo["owner"], repo["slug"], workflow["id"]
                )
                workflows_runs_mapped.extend(
                    (
                        await self.mapper.process(
                            "workflow_run",
                            self.workflows_to_runs[repo_id],
                            context={"repositoryId": repo_id, "workflow": workflow},
                        )
                    )
                )

                inactive_usernames.update(
                    get_inactive_usernames_from_workflow_runs(self.workflows_to_runs[repo_id], self.users)
                )
        self.logger.info(
            "Found %d workflow runs from the last %d days", len(workflows_runs_mapped), self.client.days_of_history
        )
        new_entities = await self.register_inactive_users(inactive_usernames)
        if new_entities:
            self.logger.info(f"Found {len(new_entities) - 1} inactive members associated to workflow runs")

        return workflows_runs_mapped

    @register(_methods, group=4)
    async def environment(self) -> list[dict]:
        if self._owner is None:
            self.logger.warning("Cannot fetch environments: owner not found")
            return []

        environments_mapped = []

        for repo_id, repo in self.repositories.items():
            self.repository_to_environments[repo_id] = await self.client.get_environments(repo["owner"], repo["slug"])
            environments_mapped.extend(
                (
                    await self.mapper.process(
                        "environment", self.repository_to_environments[repo_id], context={"repositoryId": repo_id}
                    )
                )
            )

        self.logger.info(f"Found {len(environments_mapped)} environments")
        return environments_mapped

    @register(_methods, group=6)
    async def deployments(self) -> list[dict]:
        if self._owner is None:
            self.logger.warning("Cannot fetch deployments: owner not found")
            return []

        deployments_mapped = []
        inactive_usernames = set()
        for repo_id, repo in self.repositories.items():
            self.repository_to_deployments[repo_id] = []
            for environment in self.repository_to_environments.get(repo_id) or []:
                repo_env_deployments = await self.client.get_deployments(
                    repo["owner"], repo["slug"], [environment["name"]]
                )

                self.repository_to_deployments[repo_id].extend(repo_env_deployments)
                deployments_mapped.extend(
                    (
                        await self.mapper.process(
                            "deployment",
                            repo_env_deployments,
                            context={
                                "repositoryId": repo_id,
                                "repositoryName": repo["slug"],
                                "repositoryLink": repo["link"],
                                "environmentId": environment["id"],
                            },
                        )
                    )
                )

                inactive_usernames.update(get_inactive_usernames_from_deployments(repo_env_deployments, self.users))

        self.logger.info(f"Found {len(deployments_mapped)} deployments")

        new_entities = await self.register_inactive_users(inactive_usernames)
        if new_entities:
            self.logger.info(f"Found {len(new_entities) - 1} inactive members associated to deployments")

        return new_entities + deployments_mapped

    @register(_methods, group=6)
    async def repository_metrics(self) -> list[dict]:
        if self._owner is None:
            self.logger.warning("Cannot fetch repository metrics: owner not found")
            return []

        all_metrics = []
        for repo in self.repositories.values():
            commits = await self.client.get_commits(repo["owner"], repo["slug"], branch=repo["default_branch"])
            repository_metrics = await self.mapper.process(
                "repository_metrics",
                [{"commits": commits}],
                context={"repositoryId": repo["id"], "repositoryName": repo["slug"]},
            )
            all_metrics.extend(repository_metrics)

        self.logger.info(
            f"Calculated {len(all_metrics)} repository metrics from the last {self.client.days_of_history} days"
        )
        return all_metrics

    async def register_inactive_users(self, inactive_usernames):
        if not inactive_usernames:
            return []

        inactive_team_id = self.template_inactive_members_team["databaseId"]

        # Fetch information from all inactive users and add them to the list of known users
        new_users = []
        for username in inactive_usernames:
            self.users[username] = {
                "node": {"name": username, "login": username, "email": "", "role": ""},
                "teams": [inactive_team_id],
            }

            new_users.append(self.users[username])
            self.teams[inactive_team_id]["members"]["nodes"].append(self.users[username])
            self.team_to_users[inactive_team_id].append(username)

        inactive_group_mapped = await self.mapper.process(
            "team", [self.teams[inactive_team_id]], context={"owner": self._owner}
        )
        new_users_mapped = await self.mapper.process("team_member", new_users, context={"owner": self._owner})

        return inactive_group_mapped + new_users_mapped
