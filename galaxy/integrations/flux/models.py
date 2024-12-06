from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field
from pydantic.functional_serializers import field_serializer


class Kind(str, Enum):
    KUSTOMIZATION = "Kustomization"
    HELM_RELEASE = "HelmRelease"


class Reason(str, Enum):
    PROGRESSING = "Progressing"
    PROGRESSING_WITH_RETRY = "ProgressingWithRetry"

    # Kustomization success
    RECONCILIATION_SUCCEEDED = "ReconciliationSucceeded"

    # HelmRelease success
    INSTALL_SUCCEEDED = "InstallSucceeded"
    UPGRADE_SUCCEEDED = "UpgradeSucceeded"
    TEST_SUCCEEDED = "TestSucceeded"

    # Kustomization failure
    PRUNE_FAILED = "PruneFailed"
    ARTIFACT_FAILED = "ArtifactFailed"
    BUILD_FAILED = "BuildFailed"
    HEALTH_CHECK_FAILED = "HealthCheckFailed"
    DEPENDENCY_NOT_READY = "DependencyNotReady"
    RECONCILIATION_FAILED = "ReconciliationFailed"

    # HelmRelease failure
    INSTALL_FAILED = "InstallFailed"
    UPGRADE_FAILED = "UpgradeFailed"
    TEST_FAILED = "TestFailed"
    ROLLBACK_SUCCEEDED = "RollbackSucceeded"
    UNINSTALL_SUCCEEDED = "UninstallSucceeded"
    ROLLBACK_FAILED = "RollbackFailed"
    UNINSTALL_FAILED = "UninstallFailed"


class InvolvedObject(BaseModel):
    kind: Kind
    namespace: str
    name: str
    uid: str
    api_version: str = Field(alias="apiVersion")
    resource_version: str | None = Field(alias="resourceVersion")


class Event(BaseModel):
    involved_object: InvolvedObject = Field(alias="involvedObject")
    severity: Literal["trace", "info", "error"]
    timestamp: datetime
    message: str
    reason: Reason
    metadata: dict[str, str] | None
    reporting_controller: str = Field(alias="reportingController")
    reporting_instance: str | None = Field(default=None, alias="reportingInstance")

    @field_serializer("timestamp")
    def serialize_timestamp(self, timestamp: datetime, _info):
        return timestamp.isoformat()
