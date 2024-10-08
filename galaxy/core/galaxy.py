import asyncio
import functools
import importlib
import json
import logging
import traceback
from collections import OrderedDict
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import aiofiles
import pkg_resources

from galaxy.core.blueprints import collect_blueprints
from galaxy.core.logging import get_magneto_logs
from galaxy.core.magneto import Magneto
from galaxy.core.mapper import Mapper
from galaxy.core.models import Config
from galaxy.core.utils import update_integration_config_entity

__all__ = ["Integration", "register", "import_and_instantiate_integration", "group_methods", "worker", "call_methods"]


class Integration:
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger("galaxy")
        self.mapper = Mapper(config.integration.type)

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


async def import_and_instantiate_integration(module_name: str, class_name: str, *args, **kwargs) -> object:
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    cls_instance = cls(*args, **kwargs)
    await cls_instance.kickstart_integration()
    return cls_instance


def group_methods(method_registry: list) -> OrderedDict[int, list[Any]]:
    grouped_methods = OrderedDict()
    for func, group in method_registry:
        if isinstance(group, int) is False:
            raise ValueError(f"Group value must be an integer, got {type(group)}")

        if group not in grouped_methods:
            grouped_methods[group] = []
        grouped_methods[group].append(func)
    return OrderedDict(sorted(grouped_methods.items()))


async def worker(queue: asyncio.Queue) -> dict:
    while not queue.empty():
        method, instance, config, logger, blueprints = await queue.get()
        magneto_client = Magneto(config.rely.url, config.rely.token, logger=logger)
        result = {"response": [], "error": None, "method": method.__name__}
        try:
            logger.info(f"Executing method '{method.__name__}'")
            method_output = await method(instance)
            logger.debug("Results from method %r: %r", method.__name__, method_output)
            if method_output is not None and len(method_output) > 0:
                if config.integration.dry_run is False:
                    logger.info("Sending entities to Rely API for method %r", method.__name__)
                    async with magneto_client as magneto:
                        response = await magneto.insert_or_update_entities_bulk(method_output)
                        logger.debug("Magneto response for method %r: %r", method.__name__, response)
                        logger.info(f"{len(response)} entities sent to Rely API for method '{method.__name__}'")
                        result["response"].extend(response)
            return result
        except Exception as error:
            traceback.print_exc()
            result["error"] = error
            return result
        finally:
            if config.integration.dry_run is False:
                async with magneto_client as magneto:
                    config_entity = await magneto.get_entity(config.integration.id)
                    await update_integration_config_entity(
                        magneto_client, config_entity, {"lastFetchedLogs": get_magneto_logs(logger).logs}
                    )
            queue.task_done()


# Function to call all registered methods using asyncio.Queue
@instance_async_enter
async def call_methods(instance, config: Config) -> None:
    logger = logging.getLogger("galaxy")
    grouped_methods = group_methods(instance._methods)
    magneto_client = Magneto(config.rely.url, config.rely.token, logger=logger)

    if config.integration.dry_run is False:
        async with magneto_client as magneto:
            config_entity = await magneto.get_entity(config.integration.id)
        await update_integration_config_entity(
            magneto_client, config_entity, {"fetchStatus": "RUNNING", "lastFetchedError": "", "lastFetchedLogs": []}
        )

    blueprints = await collect_blueprints(config, magneto_client)
    automations_path = pkg_resources.resource_filename(
        "galaxy", f"integrations/{config.integration.type}/.rely/automations.json"
    )
    try:
        async with aiofiles.open(automations_path, "r") as automations_file:
            automations = json.loads(await automations_file.read())

        if config.integration.dry_run is False:
            for automation in automations:
                logger.debug("Upserting automation: %r", automation)
                async with magneto_client as magneto:
                    # If automation has errors due to missing blueprints, lets skip it
                    await magneto.upsert_automation(automation, raise_if_blueprint_not_found=False)
    except Exception as e:
        if config.integration.dry_run is False:
            async with magneto_client as magneto:
                config_entity = await magneto.get_entity(config.integration.id)
            await update_integration_config_entity(
                magneto_client,
                config_entity,
                {
                    "fetchStatus": "FAILED",
                    "lastFetchedAt": datetime.now(UTC).isoformat(),
                    "lastFetchedError": "Error creating automations",
                    "lastFetchedLogs": get_magneto_logs(logger).logs,
                },
            )
        raise Exception(f"Error upserting automations: {e}")

    # Enqueue all methods into the queue
    for group, methods in grouped_methods.items():
        queue = asyncio.Queue()
        logger.info(f"Executing task group: {group}")
        for method in methods:
            await queue.put((method, instance, config, logger, blueprints))

        workers = [asyncio.create_task(worker(queue)) for _ in range(queue.qsize())]
        await queue.join()

        errors = []
        results = await asyncio.gather(*workers, return_exceptions=True)
        for result in results:
            logger.debug("Result from worker coroutine: %r", result)
            if result["error"] is not None:
                if config.integration.dry_run is False:
                    errors.append(f"Errors in  method '{result['method']}': {result['error']}")

        if len(errors) > 0:
            if config.integration.dry_run is False:
                await update_integration_config_entity(
                    magneto_client,
                    config_entity,
                    {
                        "fetchStatus": "FAILED",
                        "lastFetchedAt": datetime.now(UTC).isoformat(),
                        "lastFetchedError": str(errors),
                        "lastFetchedLogs": get_magneto_logs(logger).logs,
                    },
                )
            raise Exception(f"Error in worker coroutines: {errors}")

    logger.info(f"All methods for integration '{config.integration.type}' processed successfully")
    if config.integration.dry_run is False:
        finished_at = datetime.now(UTC).isoformat()
        await update_integration_config_entity(
            magneto_client,
            config_entity,
            {
                "fetchStatus": "FINISHED",
                "lastFetchedAt": finished_at,
                "lastFetchedSuccessAt": finished_at,
                "lastFetchedError": "",
                "lastFetchedLogs": get_magneto_logs(logger).logs,
            },
        )

    get_magneto_logs(logger).flush()
