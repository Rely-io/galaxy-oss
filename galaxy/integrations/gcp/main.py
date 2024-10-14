from galaxy.core.galaxy import Integration, register
from galaxy.core.models import Config
from galaxy.integrations.gcp.client import GcpClient


class Gcp(Integration):
    _methods = []

    def __init__(self, config: Config):
        super().__init__(config)
        self.client = GcpClient(self.config, self.logger)

    @register(_methods, group=4)
    async def appengine_applications(self) -> list[dict]:
        applications = await self.client.get_assets(["appengine.googleapis.com/Application"])
        applications_mapped = await self.mapper.process("appengine_application", applications, context={})
        self.logger.info(f"Found {len(applications_mapped)} App Engine Applications")
        return applications_mapped

    @register(_methods, group=4)
    async def cloudfunctions_functions(self) -> list[dict]:
        functions = await self.client.get_assets(["cloudfunctions.googleapis.com/Function"])
        functions_mapped = await self.mapper.process("cloudfunctions_function", functions, context={})
        self.logger.info(f"Found {len(functions_mapped)} Cloud Run Functions")
        return functions_mapped

    @register(_methods, group=2)
    async def cloudresourcemanager_folders(self) -> list[dict]:
        folders = await self.client.get_assets(["cloudresourcemanager.googleapis.com/Folder"])
        folders_mapped = await self.mapper.process("cloudresourcemanager_folder", folders, context={})
        self.logger.info(f"Found {len(folders_mapped)} Cloud Platform Folders")
        return folders_mapped

    @register(_methods, group=1)
    async def cloudresourcemanager_organizations(self) -> list[dict]:
        organizations = await self.client.get_assets(["cloudresourcemanager.googleapis.com/Organization"])
        organizations_mapped = await self.mapper.process("cloudresourcemanager_organization", organizations, context={})
        self.logger.info(f"Found {len(organizations_mapped)} Cloud Platform Organizations")
        return organizations_mapped

    @register(_methods, group=3)
    async def cloudresourcemanager_projects(self) -> list[dict]:
        projects = await self.client.get_assets(["cloudresourcemanager.googleapis.com/Project"])
        projects_mapped = await self.mapper.process("cloudresourcemanager_project", projects, context={})
        self.logger.info(f"Found {len(projects_mapped)} Cloud Platform Projects")
        return projects_mapped

    @register(_methods, group=4)
    async def container_clusters(self) -> list[dict]:
        clusters = await self.client.get_assets(["container.googleapis.com/Cluster"])
        clusters_mapped = await self.mapper.process("container_cluster", clusters, context={})
        self.logger.info(f"Found {len(clusters_mapped)} Kubernetes Engine Clusters")
        return clusters_mapped

    @register(_methods, group=4)
    async def sqladmin_instances(self) -> list[dict]:
        instances = await self.client.get_assets(["sqladmin.googleapis.com/Instance"])
        instances_mapped = await self.mapper.process("sqladmin_instance", instances, context={})
        self.logger.info(f"Found {len(instances_mapped)} Cloud SQL Instances")
        return instances_mapped
