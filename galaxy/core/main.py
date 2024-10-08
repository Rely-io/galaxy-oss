import os

import aiofiles
import humps
import pkg_resources
import yaml
from jinja2 import Environment, FileSystemLoader

from galaxy.core.api import run_app
from galaxy.core.galaxy import call_methods, import_and_instantiate_integration
from galaxy.core.logging import setup_logger
from galaxy.core.magneto import Magneto
from galaxy.core.models import Config, ExecutionType
from galaxy.core.utils import from_env, get_config_value


async def main(
    integration_type: str | None = None,
    integration_id: str | None = None,
    config_file: str | None = None,
    url: str | None = None,
    token: str | None = None,
    dry_run: bool = False,
) -> None:
    if integration_type is None:
        integration_type = from_env("RELY_INTEGRATION_TYPE", raise_exception=True)

    if config_file is None:
        config_file = os.path.join(
            pkg_resources.resource_filename("galaxy", f"integrations/{integration_type}"), "config.yaml"
        )
    async with aiofiles.open(config_file, "r") as file:
        config = await file.read()
    # Do environment variable substitution in the config file
    env = Environment(loader=FileSystemLoader("../.."))
    env.globals["env"] = from_env
    config = Config(**yaml.safe_load(env.from_string(config).render()))

    config.rely.url = get_config_value(url, config.rely.url, "url")
    config.rely.token = get_config_value(token, config.rely.token, "token")
    config.integration.id = get_config_value(integration_id, config.integration.id, "integration_id")
    config.integration.dry_run = dry_run

    logger = setup_logger(config)
    logger.info(f"Starting {integration_type} integration")

    if dry_run is False:
        async with Magneto(config.rely.url, config.rely.token, logger=logger) as session:
            integration_config = await session.get_plugin(str(config.integration.id))

        logger.debug("Config entity from magneto: %r", integration_config)
        if integration_config["dataSource"].lower() != integration_type:
            logger.error(
                f"Integration type mismatch. Expected {integration_type} but got {integration_config['dataSource']}"
            )
            raise Exception("Integration type mismatch between the integration and magneto config")

        config_entity_properties = integration_config.get("properties", None)
        if config_entity_properties is not None:
            for key, value in config_entity_properties.items():
                # Only set the property if it doesn't already exist or is empty
                if not config.integration.properties.get(key) or (
                    # This OR is to handle the scenario of a nested dict with keys but no values
                    isinstance(config.integration.properties[key], dict)
                    and not all(config.integration.properties[key].values())
                ):
                    config.integration.properties[key] = value

        logger.debug("Config entity properties: %r", config.integration.properties)
        if integration_config is None:
            logger.error("Integration not found in magneto")
            raise Exception("Integration not found in magneto")

    logger.debug("Galaxy run config: %r", config)
    module_name = f"galaxy.integrations.{integration_type}.main"
    class_name = humps.pascalize(integration_type)  # Assumes class name is pascal case version of integration_type

    # Create an instance of the plugin
    methods = await import_and_instantiate_integration(module_name, class_name, config=config)

    if config.integration.execution_type == ExecutionType.CRONJOB:
        logger.info("Running galaxy framework in cronjob mode")
        await call_methods(methods, config)
    elif config.integration.execution_type == ExecutionType.DAEMON:
        logger.info("Running galaxy framework in daemon mode")
        await run_app(methods, config)
    else:
        logger.error("Invalid execution type in config file")
        raise Exception("Invalid execution type in config file.")
