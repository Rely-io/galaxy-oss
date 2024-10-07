import json
import re
from collections import defaultdict

import aiofiles
import pkg_resources

from galaxy.core.magneto import Magneto
from galaxy.core.models import Config

__all__ = ["get_relation_for_default_model_association", "collect_blueprints"]


def get_relation_for_default_model_association(blueprint_data: dict) -> dict:
    relation_title_camel_case = blueprint_data["title"].replace(" ", "")
    return {
        relation_title_camel_case: {
            "value": blueprint_data["id"],
            "array": False,
            "title": blueprint_data["title"],
            "description": f"The upstream {relation_title_camel_case}",
        }
    }


async def collect_blueprints(config: Config, magneto_client: Magneto) -> list[dict]:
    selected_blueprints = config.integration.properties.get("assetsForDiscovery")
    default_model_mappings = config.integration.default_model_mappings
    blueprints_path = pkg_resources.resource_filename(
        "galaxy", f"integrations/{config.integration.type}/.rely/blueprints.json"
    )
    async with aiofiles.open(blueprints_path, "r") as blueprints_file:
        blueprints = [
            bp
            for bp in json.loads(await blueprints_file.read())
            if selected_blueprints is None or bp["id"] in selected_blueprints
        ]

    relations_to_create: dict[str, list] = {}
    relations_to_remove: dict[str, set] = defaultdict(set)
    for blueprint in blueprints:
        for mapping in default_model_mappings.keys():
            if re.match(mapping, blueprint["id"]):
                if default_model_mappings[mapping] not in relations_to_create:
                    relations_to_create[default_model_mappings[mapping]] = []
                relations_to_create[default_model_mappings[mapping]].append(
                    get_relation_for_default_model_association(blueprint)
                )

        # Remove blueprint relations that have target blueprints that are not in the selected blueprints
        if selected_blueprints is not None:
            for relation_key, relation in (blueprint.get("relations") or {}).items():
                value = relation.get("value")
                if value and value not in selected_blueprints:
                    relations_to_remove[blueprint["id"]].add(relation_key)
            if relations_to_remove[blueprint["id"]]:
                blueprint["relations"] = {
                    relation_key: relation
                    for relation_key, relation in blueprint.get("relations").items()
                    if relation_key not in relations_to_remove[blueprint["id"]]
                }

    if config.integration.dry_run is False:
        async with magneto_client as session:
            blueprints = await session.insert_or_update_blueprint_bulk(blueprints=blueprints)
        for blueprint_id in relations_to_create:
            for relation in relations_to_create[blueprint_id]:
                async with magneto_client as session:
                    await session.upsert_blueprint_relation(blueprint_id, relation)

        # Need to iterate and remove "invalid" relations again since the relations might be here again if the blueprint
        #   already had them on server side, but we want to ignore them for the current run
        for blueprint in blueprints:
            if relations_to_remove[blueprint.id]:
                blueprint["relations"] = {
                    relation_key: relation
                    for relation_key, relation in blueprint.get("relations").items()
                    if relation_key not in relations_to_remove[blueprint["id"]]
                }

    return blueprints
