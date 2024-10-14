import functools
import importlib
import json
import logging
import traceback
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import anyio

from galaxy.core.blueprints import collect_blueprints
from galaxy.core.logging import get_magneto_logs
from galaxy.core.magneto import Magneto
from galaxy.core.mapper import Mapper
from galaxy.core.models import Config
from galaxy.core.resources import load_integration_resource
from galaxy.core.utils import update_integration_config_entity

__all__ = ["Integration", "IntegrationRunError", "import_and_instantiate_integration", "register", "run_integration"]


@dataclass(kw_only=True)
class IntegrationRunError(Exception):
    integration_id: str
    integration_type: str
    errors: list[Exception]

    def __str__(self):
        return f"Error running integration: {self.integration_id} ({self.integration_type}): {self.errors}"


@dataclass(kw_only=True)
class IntegrationRunMethodError(Exception):
    integration_id: str
    integration_type: str
    method: str
    error: Exception

    def __str__(self):
        return (
            f"Error running in method {self.method!r} for integration {self.integration_id}"
            f" ({self.integration_type}): {self.error}"
        )


class Integration:
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger("galaxy")
        self.mapper = Mapper(config.integration.type)

    @property
    def id_(self) -> str:
        return self.config.integration.id

    @property
    def type_(self) -> str:
        return self.config.integration.type

    @property
    def is_dry_run(self) -> bool:
        return self.config.integration.dry_run

    async def kickstart_integration(self):
        pass


# Decorator to register methods
def register(method_registry: list, group: int = 0) -> callable:
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            return func(self, *args, **kwargs)

        method_registry.append((func, group))
        return wrapper

    return decorator


# Decorator to try to enter an async context of an instance if it is an async context manager
def instance_async_enter(func: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(func)
    async def wrapper(instance: Any, *args: Any, **kwargs: Any) -> Any:
        if instance is not None and hasattr(instance, "__aenter__"):
            async with instance:
                return await func(instance, *args, **kwargs)
        return await func(instance, *args, **kwargs)

    return wrapper


async def import_and_instantiate_integration(
    module_name: str, class_name: str, *args: Any, **kwargs: Any
) -> Integration:
    module = importlib.import_module(module_name)
    cls: type[Integration] = getattr(module, class_name)
    cls_instance = cls(*args, **kwargs)
    await cls_instance.kickstart_integration()
    return cls_instance


@instance_async_enter
async def run_integration(instance: Integration, *, magneto_client: Magneto, logger: logging.Logger) -> None:
    try:
        if not instance.is_dry_run:
            config_entity = await magneto_client.get_entity(instance.id_)
            await _update_integration_config_entity(
                config_entity, is_running=True, magneto_client=magneto_client, logger=logger
            )
        else:
            config_entity = None

        _ = await collect_blueprints(instance.config, magneto_client=magneto_client)
        await _upsert_automations(instance, magneto_client=magneto_client, logger=logger)
        await run_integration_methods(
            instance=instance, config_entity=config_entity, magneto_client=magneto_client, logger=logger
        )

    except IntegrationRunError as e:
        if not instance.is_dry_run:
            await _update_integration_config_entity(
                config_entity, error="; ".join(str(x) for x in e.errors), magneto_client=magneto_client, logger=logger
            )
        raise
    except Exception as e:
        if not instance.is_dry_run:
            await _update_integration_config_entity(
                config_entity, error=str(e), magneto_client=magneto_client, logger=logger
            )
        raise
    finally:
        get_magneto_logs(logger).flush()

    logger.info("Integration %r finished with success", instance.id_)

    if not instance.is_dry_run:
        await _update_integration_config_entity(config_entity, magneto_client=magneto_client, logger=logger)


async def run_integration_methods(
    instance: Integration, *, config_entity: dict[str, Any] | None, magneto_client: Magneto, logger: logging.Logger
) -> None:
    errors: list[Exception] = []
    for group, methods in _group_methods(instance._methods).items():
        logger.info("Executing task group: %r", group)
        try:
            async with anyio.create_task_group() as task_group:
                for method in methods:
                    task_group.start_soon(
                        functools.partial(
                            _run_integration_method,
                            instance=instance,
                            method=method,
                            magneto_client=magneto_client,
                            logger=logger,
                        )
                    )
        except* IntegrationRunMethodError as excgroup:
            for exc in excgroup.exceptions:
                error = f"Error executing method {exc.method} (group {group}): {exc.error}"
                logger.error(error)
                errors.append(Exception(error))
        except* Exception as excgroup:
            for exc in excgroup.exceptions:
                errors.append(Exception(f"Error executing group {group}: {exc}"))

        if not instance.is_dry_run:
            await _update_integration_config_entity(
                config_entity, is_running=True, magneto_client=magneto_client, logger=logger
            )

    if len(errors) > 0:
        raise IntegrationRunError(integration_id=instance.id_, integration_type=instance.type_, errors=errors)


async def _run_integration_method(
    *, instance: Integration, method: Callable, magneto_client: Magneto, logger: logging.Logger
) -> dict:
    try:
        logger.info("Executing method %r", method.__name__)
        method_output = await method(instance)
        logger.debug("Results from method %r: %r", method.__name__, method_output)

        results = []
        if method_output is not None and len(method_output) > 0:
            logger.debug("Magneto response for method %r: %r", method.__name__, method_output)
            if not instance.is_dry_run:
                logger.info("Sending entities to Rely API for method %r", method.__name__)
                response = await magneto_client.insert_or_update_entities_bulk(method_output)
                logger.info("%d entities sent to Rely API for method %r", len(response), method.__name__)
                logger.debug("Magneto response for method %r: %r", method.__name__, response)
                results.extend(response)
        return results

    except Exception as e:
        traceback.print_exc()
        raise IntegrationRunMethodError(
            integration_id=instance.id_, integration_type=instance.type_, method=method.__name__, error=e
        ) from e


def _group_methods(method_registry: list) -> OrderedDict[int, list[Any]]:
    grouped_methods = OrderedDict()
    for func, group in method_registry:
        if isinstance(group, int) is False:
            raise ValueError(f"Group value must be an integer, got {type(group)}")

        if group not in grouped_methods:
            grouped_methods[group] = []
        grouped_methods[group].append(func)
    return OrderedDict(sorted(grouped_methods.items()))


async def _upsert_automations(instance: Integration, *, magneto_client: Magneto, logger: logging.Logger) -> None:
    try:
        automations = json.loads(load_integration_resource(instance.type_, ".rely/automations.json"))
        if instance.config.integration.dry_run is False:
            for automation in automations:
                logger.debug("Upserting automation: %r", automation)
                await magneto_client.upsert_automation(
                    automation,
                    # If automation has errors due to missing blueprints, lets skip it
                    raise_if_blueprint_not_found=False,
                )
    except Exception as e:
        raise Exception(f"Error upserting automations: {e}") from e


async def _update_integration_config_entity(
    config_entity: dict[str, Any],
    *,
    is_running: bool = False,
    error: str | None = None,
    magneto_client: Magneto,
    logger: logging.Logger,
) -> None:
    data = {
        "fetchStatus": "RUNNING" if is_running else "FAILED" if error is not None else "FINISHED",
        "lastFetchedError": error or "",
        "lastFetchedLogs": get_magneto_logs(logger).logs,
    }
    if not is_running:
        now = datetime.now(UTC).isoformat()
        data["lastFetchedAt"] = now
        if error is None:
            data["lastFetchedSuccessAt"] = now

    await update_integration_config_entity(magneto_client, config_entity, data)
