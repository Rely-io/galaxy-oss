from dataclasses import dataclass

__all__ = ["GalaxyError", "IntegrationRunError", "IntegrationRunMethodError", "EntityPushTaskError"]


class GalaxyError(Exception):
    """Base class for all Galaxy errors."""


class CronjobRunError(GalaxyError):
    """Exception raised when Galaxy cronjob run fails."""


@dataclass(kw_only=True)
class IntegrationRunError(GalaxyError):
    """Exception raised when an integration run fails."""

    integration_id: str
    integration_type: str
    errors: list[Exception]

    def __str__(self):
        return f"Error running integration: {self.integration_id} ({self.integration_type}): {self.errors}"


@dataclass(kw_only=True)
class IntegrationRunMethodError(Exception):
    """Exception raised when an integration run method fails."""

    integration_id: str
    integration_type: str
    method: str
    error: Exception

    def __str__(self):
        return (
            f"Error running in method {self.method!r} for integration {self.integration_id}"
            f" ({self.integration_type}): {self.error}"
        )


@dataclass(kw_only=True)
class EntityPushTaskError(Exception):
    """Exception raised when an entity push task fails."""

    integration_id: str
    integration_type: str
    error: Exception
    entity_ids: list[str]

    def __str__(self):
        if len(self.entity_ids) == 1:
            return f"Entity ({self.entity_ids[0]!r}) push task error: {self.integration_id} ({self.integration_type}): {self.error} "
        return (
            f"Entity push task error: {self.integration_id} ({self.integration_type}): {self.error} "
            f"(entity_ids: {', '.join(self.entity_ids)})"
        )
