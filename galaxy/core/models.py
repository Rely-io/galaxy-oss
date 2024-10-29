from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

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


class Config(BaseModel):
    @classmethod
    def from_yaml(cls, file_path):
        with open(file_path, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    model_config = ConfigDict(extra="forbid")

    rely: RelyConfig
    integration: IntegrationConfig
