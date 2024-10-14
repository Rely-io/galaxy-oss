import json
import os
import sys

import click
import humps
from jsonschema import Draft7Validator, ValidationError, SchemaError
from ruamel.yaml import YAML
from galaxy.core.models import Config


def validate_blueprint_schema(blueprint):
    try:
        Draft7Validator.check_schema(blueprint)
    except SchemaError as e:
        print(f"Schema error: {e.message}")
    except ValidationError as e:
        print(f"Validation error: {e.message}")


def validate_keys(d, resource, unsafe=True):
    new_dict = {}
    errors = []
    for k, v in d.items():
        camel_key = humps.camelize(k)
        if unsafe is False:
            if k != camel_key:
                errors.append(f"Key '{k}' for {resource} is not in camelCase.")
            new_dict[k] = v
        else:
            new_dict[camel_key] = v
    return new_dict, errors


def validator(name, unsafe: bool = False):
    click.echo(f"Running validation for integration: '{name}'.")
    plugins_base_path = "galaxy/integrations/"
    blueprints_path = os.path.join(plugins_base_path, name, ".rely/blueprints.json")
    mappings_path = os.path.join(plugins_base_path, name, ".rely/mappings.yaml")
    yaml = YAML()
    errors = []

    with open(blueprints_path, "r") as blueprints_file:
        blueprints = json.loads(blueprints_file.read())
    with open(mappings_path, "r") as mapping_file:
        mappings = yaml.load(mapping_file.read())
    with open(os.path.join(plugins_base_path, name, "config.yaml"), "r") as mapping_file:
        config = yaml.load(mapping_file.read())

    # Validate config
    try:
        Config.model_validate(config)
    except Exception as e:
        errors.append(f"Error validating config: {e}")

    blueprints_copy = blueprints.copy()
    # Validate mapping properties
    for mapping in mappings["resources"]:
        click.echo(f"Validating '{name}' mapping for kind: {mapping['kind']}")
        blueprint = [item for item in blueprints if item["id"] == mapping["mappings"]["blueprintId"].strip('"')]
        if len(blueprint) == 1:
            blueprints_copy.pop(blueprints_copy.index(blueprint[0]))
            print(blueprint)
            validate_blueprint_schema(blueprint[0])
            blueprint[0]["schemaProperties"]["properties"], err = validate_keys(
                blueprint[0]["schemaProperties"]["properties"], f"blueprint '{blueprint[0]['id']}'", unsafe=unsafe
            )
            errors.extend(err)
            mapping["mappings"]["properties"], err = validate_keys(
                mapping["mappings"]["properties"], f"mapping '{mapping['kind']}'", unsafe=unsafe
            )
            errors.extend(err)

            mapping_properties = mapping["mappings"]["properties"].keys()
            blueprint_properties = blueprint[0]["schemaProperties"]["properties"].keys()
            # check if the mapping properties are a subset of the blueprint properties
            missing_properties_in_blueprints = set(mapping_properties) - set(blueprint_properties)
            # check if the blueprint properties are a subset of the mapping properties
            missing_properties_in_mappings = set(blueprint_properties) - set(mapping_properties)
            if missing_properties_in_blueprints:
                errors.append(
                    f"The mapping '{mapping['kind']}' for integration '{name}' has properties {missing_properties_in_blueprints} "
                    f"not in reference blueprintId: '{blueprint[0]['id']}'."
                )
            if missing_properties_in_mappings:
                errors.append(
                    f"The blueprint '{blueprint[0]['id']}' for integration '{name}' has properties {missing_properties_in_mappings} "
                    f"not in reference mapping: '{mapping['kind']}'."
                )
        elif len(blueprint) == 0:
            errors.append(f'Blueprint {mapping["mappings"]["blueprintId"]} for mapping "{mapping["kind"]}" not found.')
        else:
            errors.append(f"Multiple blueprints found for mapping {mapping['kind']}.")

    if len(blueprints_copy) > 0:
        blueprint_ids = []
        for blueprint in blueprints_copy:
            blueprint_ids.append(blueprint["id"])
        errors.append(f"The blueprints: '{blueprint_ids}' dont have any mapping associated.")

    if len(errors) != 0:
        click.echo("Errors:")
        for error in errors:
            click.echo(error)

        click.echo("Validation Failed!")
        if unsafe is True:
            click.echo("Changes were not persisted to files. Please fix the errors before using unsafe option again.")
        sys.exit(1)

    if unsafe is True:
        yaml.preserve_quotes = True
        yaml.width = 120
        with open(blueprints_path, "w") as blueprints_file:
            blueprints_file.write(json.dumps(blueprints, indent=2))
        with open(mappings_path, "w") as mapping_file:
            yaml.dump(mappings, mapping_file)
