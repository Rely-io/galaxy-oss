from galaxy.core.galaxy import Integration, register
from galaxy.core.models import Config
from galaxy.integrations.bitbucket.client import BitbucketClient

__all__ = ["Bitbucket"]


class Bitbucket(Integration):
    _methods = []

    def __init__(self, config: Config):
        super().__init__(config)
        self.client = BitbucketClient(self.config, self.logger)
        self.workspaces = {}
        self.workspace_users = {}
        self.workspace_projects = {}
        self.workspace_repositories = {}
        self.workspace_repository_pull_requests = {}
        self.workspace_repository_pipelines = {}
        self.workspace_repository_environments = {}
        self.workspace_repository_deployments = {}

    async def kickstart_integration(self):
        await self.client.init_credentials()

    @register(_methods, group=1)
    async def workspace(self) -> list[dict]:
        workspaces_mapped = []
        for workspace_slug in self.config.integration.properties["workspaces"]:
            self.workspaces[workspace_slug] = await self.client.get_workspace(workspace_slug)
            workspaces_mapped.extend(
                (await self.mapper.process("workspace", [self.workspaces[workspace_slug]], context={}))
            )
        self.logger.info(f"Found {len(workspaces_mapped)} users")
        return workspaces_mapped

    @register(_methods, group=2)
    async def users(self) -> list[dict]:
        users_mapped = []
        for workspace_slug in self.workspaces.keys():
            self.workspace_users[workspace_slug] = await self.client.get_users(workspace_slug)
            users_mapped.extend((await self.mapper.process("user", self.workspace_users[workspace_slug], context={})))
        self.logger.info(f"Found {len(users_mapped)} users")
        return users_mapped

    @register(_methods, group=3)
    async def projects(self) -> list[dict]:
        projects_mapped = []
        for workspace_slug in self.workspaces.keys():
            self.workspace_projects[workspace_slug] = await self.client.get_projects(workspace_slug)
            projects_mapped.extend(
                (await self.mapper.process("project", self.workspace_projects[workspace_slug], context={}))
            )
        self.logger.info(f"Found {len(projects_mapped)} users")
        return projects_mapped

    @register(_methods, group=3)
    async def repositories(self) -> list[dict]:
        repositories_mapped = []
        for workspace_slug in self.workspaces.keys():
            self.workspace_repositories[workspace_slug] = await self.client.get_repositories(workspace_slug)
            for repository in self.workspace_repositories[workspace_slug]:
                repository["readme_content"] = await self.client.get_readme(
                    workspace_slug, repository["slug"], repository.get("mainbranch", {}).get("slug", "main")
                )
            repositories_mapped.extend(
                (await self.mapper.process("repository", self.workspace_repositories[workspace_slug], context={}))
            )
        self.logger.info(f"Found {len(repositories_mapped)} users")
        return repositories_mapped

    @register(_methods, group=4)
    async def pull_requests(self) -> list[dict]:
        pull_requests_mapped = []
        for workspace_slug, repositories in self.workspace_repositories.items():
            self.workspace_repository_pull_requests[workspace_slug] = {}
            for repository in repositories:
                self.workspace_repository_pull_requests[workspace_slug][
                    repository["slug"]
                ] = await self.client.get_pull_requests(workspace_slug, repository["slug"])
                pull_requests_mapped.extend(
                    (
                        await self.mapper.process(
                            "pull_request",
                            self.workspace_repository_pull_requests[workspace_slug][repository["slug"]],
                            context={
                                "repositoryId": repository["uuid"],
                                "repositoryUrl": f"https://bitbucket.org/{workspace_slug}/{repository['slug']}",
                            },
                        )
                    )
                )
        self.logger.info(f"Found {len(pull_requests_mapped)} pull requests")
        return pull_requests_mapped

    @register(_methods, group=4)
    async def pipelines(self) -> list[dict]:
        pipelines_mapped = []
        for workspace_slug, repositories in self.workspace_repositories.items():
            self.workspace_repository_pipelines[workspace_slug] = {}
            for repository in repositories:
                self.workspace_repository_pipelines[workspace_slug][
                    repository["slug"]
                ] = await self.client.get_pipelines(workspace_slug, repository["slug"])
                pipelines_mapped.extend(
                    (
                        await self.mapper.process(
                            "pipeline",
                            self.workspace_repository_pipelines[workspace_slug][repository["slug"]],
                            context={"repositoryUrl": f"https://bitbucket.org/{workspace_slug}/{repository['slug']}"},
                        )
                    )
                )
        self.logger.info(f"Found {len(pipelines_mapped)} pipelines")
        return pipelines_mapped

    @register(_methods, group=4)
    async def environments(self) -> list[dict]:
        environments_mapped = []
        for workspace_slug, repositories in self.workspace_repositories.items():
            self.workspace_repository_environments[workspace_slug] = {}
            for repository in repositories:
                self.workspace_repository_environments[workspace_slug][
                    repository["slug"]
                ] = await self.client.get_environments(workspace_slug, repository["slug"])
                environments_mapped.extend(
                    (
                        await self.mapper.process(
                            "environment",
                            self.workspace_repository_environments[workspace_slug][repository["slug"]],
                            context={
                                "repositoryUrl": f"https://bitbucket.org/{workspace_slug}/{repository['slug']}",
                                "repositoryId": repository["uuid"],
                            },
                        )
                    )
                )
        self.logger.info(f"Found {len(environments_mapped)} environments")
        return environments_mapped

    @register(_methods, group=5)
    async def deployments(self) -> list[dict]:
        deployments_mapped = []
        for workspace_slug, repositories in self.workspace_repositories.items():
            self.workspace_repository_deployments[workspace_slug] = {}
            for repository in repositories:
                self.workspace_repository_deployments[workspace_slug][
                    repository["slug"]
                ] = await self.client.get_deployments(workspace_slug, repository["slug"])
                deployments_mapped.extend(
                    (
                        await self.mapper.process(
                            "deployment",
                            self.workspace_repository_deployments[workspace_slug][repository["slug"]],
                            context={
                                "repositoryUrl": f"https://bitbucket.org/{workspace_slug}/{repository['slug']}",
                                "repositoryId": repository["uuid"],
                            },
                        )
                    )
                )
        self.logger.info(f"Found {len(deployments_mapped)} deployments")
        return deployments_mapped
