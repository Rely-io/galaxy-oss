#!/usr/bin/env python
import os
import sys

import click
import humps
from cookiecutter.main import cookiecutter
from dotenv import load_dotenv

from galaxy import __version__
from galaxy.cli.validators import validator
from galaxy.core.main import main
from galaxy.utils.concurrency import run as anyio_run


@click.group()
def cli():
    click.echo("Starting Galaxy Framework CLI")


@cli.command()
def version():
    """Prints the version of the CLI."""
    click.echo(f"Galaxy Framework : {__version__}")


@cli.command()
@click.option("--integration-type", "-it", default=None, help="The integration type name (ex: gitlab, aws, etc.")
@click.option("--integration-id", "-id", default=None, help="The integration rely id.")
@click.option("--config-file", "-c", default=None, help="Path to configuration file to use.")
@click.option("--debug", "-d", is_flag=True, help="Run the framework in debug mode.")
@click.option("--url", "-u", default=None, help="The URL of the Rely API.")
@click.option("--token", "-t", default=None, help="The token to use when calling the Rely API.")
@click.option("--dry-run", "-dr", is_flag=True, default=False, help="Run the integration in dry run mode")
def run(integration_type, integration_id, config_file, debug, url, token, dry_run):
    load_dotenv()
    if debug:
        os.environ["RELY_INTEGRATION_DEBUG"] = "true"
    if config_file and not os.path.isfile(config_file):
        click.echo(f"Error: Configuration file '{config_file}' not found.")
        raise Exception(f"Configuration file '{config_file}' not found.")

    anyio_run(
        main,
        integration_type=integration_type,
        integration_id=integration_id,
        config_file=config_file,
        url=url,
        token=token,
        dry_run=dry_run,
    )


@cli.command()
@click.option("--name", "-i", required=True, help="The name of the new integration.")
def scaffold(name):
    click.echo(f"Creating new integration with name {name}!")
    template_path = "galaxy/cli/cookiecutter"

    if humps.is_snakecase(name) is False:
        click.echo("Integration name must be in snake_case.")
        sys.exit(1)

    try:
        cookiecutter(
            template_path,
            output_dir="galaxy/integrations/",
            no_input=True,
            extra_context={"integration_name": name, "integration_name_pascalcase": humps.pascalize(name)},
        )
        print(f"Integration '{name}' created successfully.")
    except Exception as e:
        raise Exception(f"Error creating project: {e}")


@cli.command()
@click.option("--name", "-i", required=True, help="The name of the new integration.")
@click.option("--unsafe", "-u", is_flag=True, help="With this option enabled changes will be persisted to files.")
def validate(name, unsafe=False):
    validator(name, unsafe=unsafe)


@cli.command()
@click.option("--unsafe", "-u", is_flag=True, help="With this option enabled changes will be persisted to files.")
def validate_all(unsafe=False):
    click.echo("Validating all integrations.")
    integrations = os.listdir("galaxy/integrations/")
    for integration in integrations:
        validator(integration, unsafe=unsafe)


if __name__ == "__main__":
    cli()
