from typing import Any, List, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, RootModel

__all__ = ["Config", "ExecutionType", "RelyConfig", "IntegrationConfig", "SchedulerJobStates"]


class ExecutionType:
    DAEMON = "daemon"
    CRONJOB = "cronjob"


class SchedulerJobStates:
    EVENT_JOB_SUBMITTED = "running"
    EVENT_JOB_EXECUTED = "completed"
    EVENT_JOB_ERROR = "error"
    EVENT_JOB_REMOVED = None


class RelyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(..., alias="token")
    url: str = Field(..., alias="url")

    def __repr__(self) -> str:
        return f"RelyConfig(url={self.url!r})"


class IntegrationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., alias="id")
    type: str = Field(..., alias="type")
    execution_type: Literal[ExecutionType.DAEMON, ExecutionType.CRONJOB] = Field(alias="executionType")
    scheduled_interval: int = Field(..., alias="scheduledInterval")
    default_model_mappings: dict[str, str] = Field(..., alias="defaultModelMappings")
    dry_run: bool = Field(False, alias="dryRun")
    properties: dict[str, Any] = Field(..., alias="properties")

    wait_for_tasks_enabled: bool = Field(True, alias="waitForTasksEnabled")
    wait_for_tasks_timeout_seconds: int | None = Field(600, alias="waitForTasksTimeout")

    def __repr__(self) -> str:
        """Return a string representation of the IntegrationConfig.

        Properties are not included as they may contain sensitive information.
        """
        return (
            f"IntegrationConfig(id={self.id}, type={self.type}, execution_type={self.execution_type}, "
            f"scheduled_interval={self.scheduled_interval}, default_model_mappings={self.default_model_mappings}, "
            f"dry_run={self.dry_run}, wait_for_tasks_enabled={self.wait_for_tasks_enabled}, "
            f"wait_for_tasks_timeout_seconds={self.wait_for_tasks_timeout_seconds})"
        )


class Config(BaseModel):
    @classmethod
    def from_yaml(cls, file_path):
        with open(file_path, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    model_config = ConfigDict(extra="forbid")

    rely: RelyConfig
    integration: IntegrationConfig

    def __repr__(self) -> str:
        return f"Config(rely={self.rely!r}, integration={self.integration!r})"


class FileCheck(BaseModel):
    path: str
    destination: str
    regex: str = Field(..., alias="regex")


class FileCheckList(RootModel):
    root: List[FileCheck]

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, item):
        return self.root[item]
