from galaxy.core.galaxy import Integration, register
from galaxy.core.models import Config
from galaxy.integrations.github.client import GithubClient
from galaxy.integrations.github.utils import (
    extract_repositories_from_team,
    extract_team_members_from_team,
    map_users_to_teams,
)

__all__ = ["Github"]


class Github(Integration):
    _methods = []

    PULL_REQUEST_STATUS_TO_FETCH = ["OPEN", "CLOSED", "MERGED"]
    ISSUE_STATUS_TO_FETCH = ["open", "closed"]

    # Default Group for previous members of the organization
    template_inactive_members_team = {
        "databaseId": "former-github-members",
        "name": "Former Organization Members",
        "description": "Group for all previous members of the organization.",
        "repositories": {"repositories": {"nodes": []}},
        "members": {"repositories": {"nodes": []}},
    }
    everyone_team = {
        "name": "Everyone",
        "description": "Default team for all public users",
        "url": "",  # You can set a URL if needed
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
        self.organization = None

        self.teams = {}
        self.repositories = {}

        self.team_to_repos = {}
        self.team_to_users = {}

        self.repository_to_pull_requests = {}
        self.repository_to_issues = {}
        self.repository_to_workflows = {}

        self.workflows_to_runs = {}

    def helper(self):
        pass

    @register(_methods, group=1)
    async def organization(self) -> None:
        repo = await self.client.list_repositories_with_access_token(limit=1, include_archived=True, include_old=True)
        if len(repo) > 0:
            self.organization = repo[0]["owner"]["login"].lower()
            self.logger.info(f"Found organization: {self.organization!r}")
        else:
            self.logger.info("Could not find organization")

    @register(_methods, group=1)
    async def repository(self) -> None:
        repositories_metadata = await self.client.list_repositories_with_access_token()

        for metadata in repositories_metadata:
            self.repositories[metadata["id"]] = {
                "id": metadata["id"],
                "slug": metadata["name"],
                "owner": metadata["owner"]["login"],
                "metadata": metadata,
                "content": await self.client.get_repo(metadata["owner"]["login"], metadata["name"]),
            }

        self.logger.info(f"Found {len(self.repositories)} repositories")
        repositories_mapped = await self.mapper.process("repository", list(self.repositories.values()), context={})
        return repositories_mapped

    @register(_methods, group=2)
    async def team(self) -> list[dict]:
        self.teams = {team["databaseId"]: team for team in (await self.client.get_all_teams(self.organization))}
        for team_id, team in self.teams.items():
            self.team_to_repos[team_id] = extract_repositories_from_team(team)
            self.team_to_users[team_id] = extract_team_members_from_team(team)

        teams_mapped = await self.mapper.process(
            "team", list(self.teams.values()), context={"organization": self.organization}
        )
        self.logger.info(f"Found {len(self.teams)-1} teams")
        return teams_mapped

    @register(_methods, group=3)
    async def team_member(self) -> list[dict]:
        self.users_to_teams = map_users_to_teams(self.team_to_users)

        users_raw = await self.client.get_all_members(self.organization)

        self.users = {}
        for user in users_raw:
            user_login = user.get("node", {}).get("login")
            self.users[user_login] = user
            self.users[user_login]["teams"] = self.users_to_teams.get(user_login, [])

        members_mapped = await self.mapper.process(
            "team_member", list(self.users.values()), context={"organization": self.organization}
        )
        self.logger.info(f"Found {len(self.teams)-1} team members")
        return members_mapped

    @register(_methods, group=4)
    async def pull_request(self) -> list[dict]:
        prs_mapped = []

        for repo_id, repo in self.repositories.items():
            self.repository_to_pull_requests[repo_id] = await self.client.get_all_requests(
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

        self.logger.info(
            f"Found {len(prs_mapped)} pull requests from the last "
            f"{self.config.integration.properties['daysOfHistory']} days"
        )
        return prs_mapped

    async def issue(self) -> list[dict]:
        issues_mapped = []

        for repo_id, repo in self.repositories.items():
            repo_issues = await self.client.get_all_issues(repo["owner"], repo["slug"], self.ISSUE_STATUS_TO_FETCH)

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

        self.logger.info(
            f"Found {len(issues_mapped)} issues from the last "
            f"{self.config.integration.properties['daysOfHistory']} days"
        )
        return issues_mapped

    @register(_methods, group=4)
    async def workflow(self) -> list[dict]:
        workflows_mapped = []

        for repo_id, repo in self.repositories.items():
            self.repository_to_workflows[repo_id] = await self.client.get_all_workflows(repo["owner"], repo["slug"])
            workflows_mapped.extend(
                (
                    await self.mapper.process(
                        "workflow", self.repository_to_workflows[repo_id], context={"repositoryId": repo_id}
                    )
                )
            )

        self.logger.info(
            f"Found {len(workflows_mapped)} workflows from the last "
            f"{self.config.integration.properties['daysOfHistory']} days"
        )
        return workflows_mapped

    @register(_methods, group=5)
    async def workflow_run(self) -> list[dict]:
        workflows_runs_mapped = []

        for repo_id, repo in self.repositories.items():
            for workflow in self.repository_to_workflows[repo_id]:
                self.workflows_to_runs[repo_id] = await self.client.get_all_workflow_runs(
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

        self.logger.info(
            f"Found {len(workflows_runs_mapped)} workflow runs from the last "
            f"{self.config.integration.properties['daysOfHistory']} days"
        )
        return workflows_runs_mapped
