import re
from types import TracebackType
from enum import Enum

from galaxy.core.galaxy import Integration, register
from galaxy.core.models import Config
from galaxy.core.utils import files_to_check
from galaxy.integrations.gitlab.client import GitlabClient
from galaxy.integrations.gitlab.utils import (
    add_user_to_inactive_group,
    get_inactive_usernames_from_deployments,
    get_inactive_usernames_from_issues,
    get_inactive_usernames_from_merge_requests,
    get_inactive_usernames_from_pipelines,
    get_required_reviews,
    map_users_to_groups,
)

__all__ = ["Gitlab"]

DEFAULT_BRANCH_NAME: str = "main"


class FileCheckStatus(Enum):
    FILE_FOUND = "FILE_FOUND"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_FOUND_NO_MATCH = "FILE_FOUND_NO_MATCH"


class Gitlab(Integration):
    _methods = []
    # Default Group for previous members of the organization
    template_inactive_members_group = {
        "id": "former-gitlab-members",
        "name": "Former Organization Members",
        "description": "Group for all previous members of the organization.",
        "projects_count": 0,
        "members_count": 0,
    }

    def __init__(self, config: Config):
        super().__init__(config)
        self.client = GitlabClient(self.config, self.logger)
        self.groups = {}
        self.repositories = {}

        self.group_to_repos = {}
        self.repo_to_groups = {}

        self.group_to_users = {}
        self.user_to_groups = {}
        self.username_to_user_id = {}

        self.repository_to_issues = {}
        self.repository_to_merge_requests = {}
        self.repository_to_pipelines = {}
        self.repository_to_environments = {}
        self.repository_to_deployments = {}

        self.jobs = []

    async def __aenter__(self) -> "GitlabClient":
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type: type, exc: Exception, tb: TracebackType) -> None:
        await self.client.__aexit__(exc_type, exc, tb)

    @property
    def repo_files_to_check(self) -> list[dict]:
        return files_to_check(self.config, self.logger)

    @register(_methods, group=1)
    async def groups(self) -> list[dict]:
        groups_mapped = []
        for group in await self.client.get_groups():
            # Fetch group repositories and assign ownership to group
            self.group_to_repos[group["id"]] = (await self.client.get_group_repos(group)) or []
            for repo in self.group_to_repos[group["id"]]:
                self.repo_to_groups[repo["id"]] = group

            # Fetch group users and assign team-membership
            self.group_to_users[group["id"]] = (await self.client.get_users(group["id"])) or []

            group["projects_count"] = len(self.group_to_repos[group["id"]])
            group["members_count"] = len(self.group_to_users[group["id"]])

            self.groups[group["id"]] = group

        # Initialize group for inactive users
        self.groups[self.template_inactive_members_group["id"]] = self.template_inactive_members_group
        self.group_to_repos[self.template_inactive_members_group["id"]] = []
        self.group_to_users[self.template_inactive_members_group["id"]] = []

        groups_mapped.extend((await self.mapper.process("group", list(self.groups.values()), context={})))
        self.logger.info(f"Found {len(self.groups)} groups")
        return groups_mapped

    @register(_methods, group=2)
    async def repositories(self) -> list[dict]:
        repos_mapped = []
        for group_id, repositories in self.group_to_repos.items():
            for repo in repositories:
                self.repositories[repo["id"]] = repo

                if repo.get("repository") is None:
                    repo["repository"] = {}

                if repo["repository"].get("rootRef") is None:
                    repo["repository"]["rootRef"] = DEFAULT_BRANCH_NAME

                repo["requiredReviews"] = get_required_reviews(repo.get("branchRules", []))
                if self.repo_files_to_check:
                    repo["repoFilesChecks"] = await self.get_repo_files(repo["fullPath"])

            repos_mapped.extend(
                (await self.mapper.process("repository", repositories, context={"ownerGroup": group_id}))
            )
        self.logger.info(f"Found {len(repos_mapped)} repositories")
        return repos_mapped

    async def get_repo_files(self, repo_full_path: str) -> dict:
        repo_file_checks = {}
        for file_check in self.repo_files_to_check:
            file = await self.client.get_file(repo_full_path, file_check["path"])
            if file:
                if file_check["regex"]:
                    result = re.search(file_check["regex"], file["content"]) if file_check["regex"] else None
                    repo_file_checks[file_check["destination"]] = (
                        result.group(1) if result else FileCheckStatus.FILE_FOUND_NO_MATCH
                    )
                else:
                    repo_file_checks[file_check["destination"]] = FileCheckStatus.FILE_FOUND
            else:
                repo_file_checks[file_check["destination"]] = FileCheckStatus.FILE_NOT_FOUND

        return repo_file_checks

    @register(_methods, group=3)
    async def users(self) -> list[dict]:
        self.user_to_groups, self.username_to_user_id = map_users_to_groups(self.group_to_users)
        users_mapped = await self.mapper.process("user", list(self.user_to_groups.values()), context={})
        self.logger.info(f"Found {len(users_mapped)} users")
        return users_mapped

    @register(_methods, group=4)
    async def issues(self) -> list[dict]:
        issues_mapped = []
        inactive_usernames = set()

        # Get Issues from all Repositories and Identify References to users that no longer belong to the org
        for group_id, repositories in self.group_to_repos.items():
            for repository in repositories:
                self.repository_to_issues[repository["id"]] = await self.client.get_issues(
                    repository, history_days=self.client.days_of_history
                )

                inactive_usernames.update(
                    get_inactive_usernames_from_issues(
                        self.repository_to_issues[repository["id"]], self.username_to_user_id
                    )
                )

                issues_mapped.extend(
                    (
                        await self.mapper.process(
                            "issue",
                            self.repository_to_issues[repository["id"]],
                            context={"repository": repository, "ownerGroup": self.repo_to_groups[repository["id"]]},
                        )
                    )
                )

        new_entities = await self.register_inactive_users(inactive_usernames)

        self.logger.info(f"Found {len(issues_mapped)} issues from the last " f"{self.client.days_of_history} days")
        if new_entities:
            self.logger.info(f"Found {len(new_entities) - 1} inactive members associated to issues")

        return new_entities + issues_mapped

    @register(_methods, group=4)
    async def merge_requests(self) -> list[dict]:
        mrs_mapped = []
        inactive_usernames = set()

        for group_id, repositories in self.group_to_repos.items():
            for repository in repositories:
                self.repository_to_merge_requests[repository["id"]] = await self.client.get_merge_requests(
                    repository, history_days=self.client.days_of_history
                )

                inactive_usernames.update(
                    get_inactive_usernames_from_merge_requests(
                        self.repository_to_merge_requests[repository["id"]], self.username_to_user_id
                    )
                )

                mrs_mapped.extend(
                    (
                        await self.mapper.process(
                            "merge_request",
                            self.repository_to_merge_requests[repository["id"]],
                            context={"repository": repository, "ownerGroup": self.repo_to_groups[repository["id"]]},
                        )
                    )
                )

        new_entities = await self.register_inactive_users(inactive_usernames)

        self.logger.info(f"Found {len(mrs_mapped)} merge requests from the last " f"{self.client.days_of_history} days")
        if new_entities:
            self.logger.info(f"Found {len(new_entities) - 1} inactive members associated to merge requests")

        return new_entities + mrs_mapped

    @register(_methods, group=4)
    async def pipelines(self) -> list[dict]:
        pipelines_mapped = []
        inactive_usernames = set()

        for group_id, repositories in self.group_to_repos.items():
            for repository in repositories:
                self.repository_to_pipelines[repository["id"]] = await self.client.get_pipelines(
                    repository, history_days=self.client.days_of_history
                )

                inactive_usernames.update(
                    get_inactive_usernames_from_pipelines(
                        self.repository_to_pipelines[repository["id"]], self.username_to_user_id
                    )
                )

                pipelines_mapped.extend(
                    (
                        await self.mapper.process(
                            "pipeline",
                            self.repository_to_pipelines[repository["id"]],
                            context={"repository": repository, "ownerGroup": self.repo_to_groups[repository["id"]]},
                        )
                    )
                )

        new_entities = await self.register_inactive_users(inactive_usernames)

        self.logger.info(
            f"Found {len(pipelines_mapped)} pipelines from the last " f"{self.client.days_of_history} days"
        )
        if new_entities:
            self.logger.info(f"Found {len(new_entities) - 1} inactive members associated to pipelines")

        return new_entities + pipelines_mapped

    @register(_methods, group=4)
    async def environments(self) -> list[dict]:
        environments_mapped = []

        for group_id, repositories in self.group_to_repos.items():
            for repository in repositories:
                self.repository_to_environments[repository["id"]] = await self.client.get_environments(repository)
                environments_mapped.extend(
                    (
                        await self.mapper.process(
                            "environment",
                            self.repository_to_environments[repository["id"]],
                            context={"repository": repository, "ownerGroup": self.repo_to_groups[repository["id"]]},
                        )
                    )
                )

        self.logger.info(f"Found {len(environments_mapped)} environments")
        return environments_mapped

    @register(_methods, group=5)
    async def deployments(self) -> list[dict]:
        deployments_mapped = []
        inactive_usernames = set()

        for repository_id, environments in self.repository_to_environments.items():
            for environment in environments:
                self.repository_to_deployments[repository_id] = await self.client.get_deployments(
                    self.repositories[repository_id],
                    environment["node"]["name"],
                    history_days=self.client.days_of_history,
                )

                inactive_usernames.update(
                    get_inactive_usernames_from_deployments(
                        self.repository_to_deployments[repository_id], self.username_to_user_id
                    )
                )

                deployments_mapped.extend(
                    (
                        await self.mapper.process(
                            "deployment",
                            self.repository_to_deployments[repository_id],
                            context={"repository": self.repositories[repository_id], "environment": environment},
                        )
                    )
                )
        new_entities = await self.register_inactive_users(inactive_usernames)

        self.logger.info(
            f"Found {len(deployments_mapped)} deployments from the last " f"{self.client.days_of_history} days"
        )
        if new_entities:
            self.logger.info(f"Found {len(new_entities) - 1} inactive members associated to deployments")

        return new_entities + deployments_mapped

    @register(_methods, group=5)
    async def repository_metrics(self) -> list[dict]:
        all_metrics = []
        for repo in self.repositories.values():
            project_id = repo["id"].split("/")[-1]
            commits = await self.client.get_commits(project_id, branch=repo["repository"]["rootRef"])
            repository_metrics = await self.mapper.process(
                "repository_metrics", [{"commits": commits}], context={"repository": repo}
            )
            all_metrics.extend(repository_metrics)

        self.logger.info(
            f"Calculated {len(all_metrics)} repository metrics from the last {self.client.days_of_history} days"
        )
        return all_metrics

    async def jobs(self) -> list[dict]:
        self.logger.info(f"Found {len(self.jobs)} jobs")
        return self.jobs

    async def register_inactive_users(self, inactive_usernames):
        if not inactive_usernames:
            return []

        inactive_group_id = self.template_inactive_members_group["id"]

        # Fetch information from all inactive users and add them to the list of known users
        new_users = []
        for username in inactive_usernames:
            inactive_user = await self.client.get_user_by_username(username)
            inactive_user = add_user_to_inactive_group(inactive_user, self.template_inactive_members_group)
            new_users.append(inactive_user)

            self.groups[inactive_group_id]["members_count"] += 1
            self.username_to_user_id[inactive_user["username"]] = inactive_user["id"]
            self.user_to_groups[inactive_user["id"]] = inactive_user
            self.group_to_users[self.template_inactive_members_group["id"]].append(inactive_user)

        inactive_group_mapped = await self.mapper.process("group", [self.groups[inactive_group_id]], context={})
        new_users_mapped = await self.mapper.process("user", new_users, context={})

        return inactive_group_mapped + new_users_mapped
