import asyncio
import re
from typing import Any

import jq
import yaml

from galaxy.core.resources import load_integration_resource

__all__ = ["Mapper"]


class Mapper:
    def __init__(self, integration_name: str):
        self.integration_name = integration_name
        self.id_allowed_chars = "[^a-zA-Z0-9-]"

    async def _load_mapping(self, mapping_kind: str) -> list[dict]:
        mappings = yaml.safe_load(load_integration_resource(self.integration_name, ".rely/mappings.yaml"))
        return [mapping for mapping in mappings.get("resources") if mapping["kind"] == mapping_kind]

    def _compile_mappings(self, mapping: dict) -> dict:
        compiled_mapping = {}
        for key, value in mapping.items():
            if isinstance(value, dict):
                compiled_mapping[key] = self._compile_mappings(value)
            elif isinstance(value, list):
                compiled_mapping[key] = [
                    self._compile_mappings(item) if isinstance(item, dict) else item for item in value
                ]
            else:
                try:
                    compiled_mapping[key] = jq.compile(value) if isinstance(value, str) else value
                except Exception as e:
                    raise Exception(f"Error compiling maps for key {key} with expression {value}: {e}")
        return compiled_mapping

    def _map_entity(self, compiled_mapping: dict, json_data: dict) -> dict:
        entity = {}

        for key, value in compiled_mapping.items():
            if isinstance(value, dict):
                entity[key] = self._map_entity(value, json_data)
            elif isinstance(value, list):
                entity[key] = [self._map_entity(item, json_data) if isinstance(item, dict) else item for item in value]
            else:
                try:
                    entity[key] = value.input(json_data).first() if isinstance(value, jq._Program) else value
                except Exception as e:
                    raise Exception(f"Error mapping key {key} with expression {value} and payload {json_data}: {e}")

        return self._sanitize(entity)

    def _replace_non_matching_characters(self, input_string: str, regex_pattern: str) -> str:
        res = re.sub(regex_pattern, ".", input_string)
        return res

    def _sanitize(self, entity: dict) -> dict:
        if entity.get("id"):
            entity["id"] = str(entity["id"]).lower()
            entity["id"] = self._replace_non_matching_characters(entity["id"], self.id_allowed_chars).lower()
        for relation in entity.get("relations", {}).values():
            if isinstance(relation["value"], list):
                relation["value"] = [
                    self._replace_non_matching_characters(value, self.id_allowed_chars).lower()
                    for value in relation["value"]
                ]
            else:
                if relation["value"]:
                    relation["value"] = relation["value"].lower()
                    relation["value"] = self._replace_non_matching_characters(relation["value"], self.id_allowed_chars)

        return entity

    async def process(self, mapping_kind: str, json_data: list[dict], context=None) -> tuple[Any]:
        try:
            mappings = await self._load_mapping(mapping_kind)
            if not mappings:
                raise Exception(f"Unknown Mapper {mapping_kind}")
            compiled_mappings = self._compile_mappings(mappings[0]["mappings"])

            loop = asyncio.get_running_loop()

            entities = await asyncio.gather(
                *[
                    loop.run_in_executor(None, self._map_entity, compiled_mappings, {**each, "context": context})
                    for each in json_data
                ]
            )
            return entities
        except Exception as e:
            raise e
