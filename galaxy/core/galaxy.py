import functools
import importlib
import json
import logging
import time
import traceback
from collections import OrderedDict
from collections.abc import AsyncGenerator, Callable
from datetime import UTC, datetime
from typing import Any

import anyio

from galaxy.core.blueprints import collect_blueprints
from galaxy.core.exceptions import (
    EntityPushTaskError,
    GalaxyError,
    IntegrationRunError,
    IntegrationRunMethodError,
    IntegrationRunWarning,
)
from galaxy.core.logging import get_magneto_logs
from galaxy.core.magneto import Magneto, TaskWithEntities, magneto_models
from galaxy.core.mapper import Mapper
from galaxy.core.models import Config
from galaxy.core.resources import load_integration_resource
from galaxy.core.utils import update_integration_config_entity

__all__ = ["Integration", "import_and_instantiate_integration", "register", "run_integration"]


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
async def run_integration(instance: Integration, *, magneto_client: Magneto, logger: logging.Logger) -> bool:
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
    except IntegrationRunWarning as e:
        if not instance.is_dry_run:
            await _update_integration_config_entity(
                config_entity, warnings=[str(w) for w in e.warnings], magneto_client=magneto_client, logger=logger
            )
        logger.warning("Integration %r finished with warnings.", instance.id_)
        return True
    except IntegrationRunError as e:
        if not instance.is_dry_run:
            await _update_integration_config_entity(
                config_entity, error="; ".join(str(x) for x in e.errors), magneto_client=magneto_client, logger=logger
            )
        logger.exception(e)

        return False
    except Exception as e:
        if not instance.is_dry_run:
            await _update_integration_config_entity(
                config_entity, error=str(e), magneto_client=magneto_client, logger=logger
            )

        raise GalaxyError(e) from e
    else:
        logger.info("Integration %r finished with success", instance.id_)
        if not instance.is_dry_run:
            await _update_integration_config_entity(config_entity, magneto_client=magneto_client, logger=logger)

        return True
    finally:
        get_magneto_logs(logger).flush()


async def run_integration_methods(
    instance: Integration, *, config_entity: dict[str, Any] | None, magneto_client: Magneto, logger: logging.Logger
) -> None:
    errors: list[Exception] = []
    warnings: list[Exception] = []
    entities_found = {}
    tasks_entities: dict[str, TaskWithEntities] = {}

    method_logger_width = max(len(method.__name__) for method, _ in instance._methods)

    async def _run_integration_method_and_push_to_magneto(method: Callable) -> None:
        logger.info("%-*s | Executing method", method_logger_width, method.__name__)

        start_time = time.time()
        method_entities = [e async for e in _run_integration_method_to_entities(instance=instance, method=method)]
        end_time = time.time()
        logger.debug(
            "%-*s | Execution: %d ms", method_logger_width, method.__name__, int((end_time - start_time) * 1000)
        )

        logger.info("%-*s | Entities found: %d", method_logger_width, method.__name__, len(method_entities))
        logger.debug("%-*s | Results: %r", method_logger_width, method.__name__, method_entities)

        if not instance.is_dry_run:
            created_tasks = await magneto_client.upsert_entities_bulk_chunks(method_entities)
            logger.info("%-*s | Push tasks created: %d", method_logger_width, method.__name__, len(created_tasks))

        for task, entities in created_tasks:
            tasks_entities[task.id] = (task, entities)
        entities_found[method.__name__] = len(method_entities)

    for group, methods in _group_methods(instance._methods).items():
        logger.debug("Executing task group: %r", group)

        try:
            async with anyio.create_task_group() as task_group:
                for method in methods:
                    task_group.start_soon(_run_integration_method_and_push_to_magneto, method)

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

    logger.info("Entities found (total: %d): %r", sum(entities_found.values()), entities_found)

    if not instance.config.integration.wait_for_tasks_enabled:
        logger.info("Not waiting for push tasks (created tasks: %d)", len(tasks_entities))
    elif not instance.is_dry_run:
        try:
            tasks_success, tasks_failed = await _wait_for_push_tasks_to_finish(
                entities_tasks=tasks_entities,
                magneto_client=magneto_client,
                logger=logger,
                timeout=instance.config.integration.wait_for_tasks_timeout_seconds,
            )
            logger.info(
                "Push tasks finished with success: %d / %d", len(tasks_success), len(tasks_success) + len(tasks_failed)
            )

            if tasks_failed:
                logger.info("Retrying failed push tasks: %d", len(tasks_failed))
                retried_tasks_success, tasks_failed = await _retry_failed_push_tasks(
                    failed_tasks=tasks_failed,
                    magneto_client=magneto_client,
                    logger=logger,
                    timeout=instance.config.integration.wait_for_tasks_timeout_seconds,
                )
                if retried_tasks_success:
                    tasks_success.update(retried_tasks_success)
                    logger.info(
                        "Retry push tasks finished with success: %d / %d",
                        len(retried_tasks_success),
                        len(retried_tasks_success) + len(tasks_failed),
                    )
                else:
                    logger.info("All push tasks retries failed (%d)", len(tasks_failed))

            if tasks_failed:
                logger.warning("Failed to push %d entities", len(tasks_failed))
                for task, entities in tasks_failed.values():
                    # These are considered warnings and not errors as they are not fatal for the integration run
                    warnings.append(
                        EntityPushTaskError(
                            integration_id=instance.id_,
                            integration_type=instance.type_,
                            error=Exception(f" ({task.error.type}) {task.error.message}"),
                            entity_ids=[entity.get("id") or "unknown" for entity in entities],
                        )
                    )
                    logger.debug("Push task error: task=%r, entities=%r", task, entities)
        except TimeoutError as e:
            errors.append(Exception(f"Timeout waiting for push tasks to finish: {e}"))

    if len(errors) > 0:
        raise IntegrationRunError(integration_id=instance.id_, integration_type=instance.type_, errors=errors)

    if len(warnings) > 0:
        raise IntegrationRunWarning(integration_id=instance.id_, integration_type=instance.type_, warnings=warnings)


async def _run_integration_method_to_entities(
    *, instance: Integration, method: Callable
) -> AsyncGenerator[dict[str, Any], None]:
    try:
        entities = await method(instance)
        for entity in entities or ():
            yield entity
    except Exception as e:
        traceback.print_exc()
        raise IntegrationRunMethodError(
            integration_id=instance.id_, integration_type=instance.type_, method=method.__name__, error=e
        ) from e


async def _retry_failed_push_tasks(
    *,
    failed_tasks: dict[str, TaskWithEntities],
    magneto_client: Magneto,
    logger: logging.Logger,
    timeout: int | None = None,
) -> tuple[dict[str, TaskWithEntities], dict[str, TaskWithEntities]]:
    entities_from_failed_tasks = [entity for _, entities in failed_tasks.values() for entity in entities]
    logger.info("Entities from failed tasks to retry: %d", len(entities_from_failed_tasks))

    created_tasks = await magneto_client.upsert_entities_bulk_chunks(entities_from_failed_tasks, chunk_size=1)
    logger.info("Push tasks created for retry: %d", len(created_tasks))

    return await _wait_for_push_tasks_to_finish(
        entities_tasks={task.id: (task, entities) for task, entities in created_tasks},
        magneto_client=magneto_client,
        logger=logger,
        timeout=timeout,
    )


async def _wait_for_push_tasks_to_finish(
    *,
    entities_tasks: dict[str, TaskWithEntities],
    magneto_client: Magneto,
    logger: logging.Logger,
    timeout: int | None = None,
) -> tuple[dict[str, TaskWithEntities], dict[str, TaskWithEntities]]:
    if not entities_tasks:
        return [], []

    tasks_success: dict[str, TaskWithEntities] = {}
    tasks_errors: dict[str, TaskWithEntities] = {}

    async def _func() -> None:
        task_ids = (task_id for task_id in entities_tasks)
        while True:
            logger.info(
                "Waiting for push tasks to finish (%d / %d)",
                len(tasks_success) + len(tasks_errors),
                len(entities_tasks),
            )
            task_ids_unfinished = []
            async for task in magneto_client.get_tasks(task_ids=task_ids):
                match task.status:
                    case magneto_models.TaskStatus.SUCCESS:
                        logger.debug("Task %r finished successfully", task.id)
                        tasks_success[task.id] = (task, entities_tasks[task.id][1])
                    case magneto_models.TaskStatus.FAILED:
                        logger.warning("Task %r failed with error: %s", task.id, task.error.type)
                        logger.debug("Task %r error message: %s", task.id, task.error.message)
                        tasks_errors[task.id] = (task, entities_tasks[task.id][1])
                    case magneto_models.TaskStatus.CREATED | magneto_models.TaskStatus.RUNNING:
                        logger.debug("Task %r still running", task.id)
                        task_ids_unfinished.append(task.id)
                    case _:
                        raise ValueError(f"Unknown task status: {task.status}")

            if len(task_ids_unfinished) == 0:
                break
            await anyio.sleep(5)
            task_ids = task_ids_unfinished

    if timeout is not None and timeout <= 0:
        timeout = None

    with anyio.fail_after(timeout):
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(_func)

    return tasks_success, tasks_errors


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
    if instance.is_dry_run is True:
        return

    try:
        automations = json.loads(load_integration_resource(instance.type_, ".rely/automations.json"))
        for automation in automations:
            logger.debug("Upserting automation: %r", automation)
            try:
                existing_automation = await magneto_client.get_automation(automation["id"])
                if existing_automation is not None:
                    automation["isActive"] = existing_automation["isActive"]
            except Exception:
                logger.info("Automation %r not found, creating a new one", automation["id"])

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
    warnings: list[str] | None = None,
    magneto_client: Magneto,
    logger: logging.Logger,
) -> None:
    data = {
        "fetchStatus": "RUNNING"
        if is_running
        else "FAILED"
        if error is not None
        else "WARNING"
        if warnings
        else "FINISHED",
        "lastFetchedError": error or "",
        "lastFetchedLogs": get_magneto_logs(logger).logs,
    }
    if not is_running:
        now = datetime.now(UTC).isoformat()
        data["lastFetchedAt"] = now
        if error is None:
            data["lastFetchedSuccessAt"] = now

    await update_integration_config_entity(magneto_client, config_entity, data)
