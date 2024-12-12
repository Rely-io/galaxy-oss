import re
from typing import Any

import jq
import yaml

from galaxy.core.resources import load_integration_resource
from galaxy.utils.concurrency import run_in_thread

__all__ = ["Mapper", "MapperError", "MapperNotFoundError", "MapperCompilationError"]


class Mapper:
    MAPPINGS_FILE_PATH: str = ".rely/mappings.yaml"

    def __init__(self, integration_name: str):
        self.integration_name = integration_name
        self.id_allowed_chars = "[^a-zA-Z0-9-]"

        self._mappings: dict[str, dict[str, Any]] | None = None
        self._compiled_mappings: dict[str, dict[str, Any]] = {}

    @property
    def mappings(self) -> dict[str, dict[str, Any]]:
        if self._mappings is None:
            mappings = yaml.safe_load(load_integration_resource(self.integration_name, self.MAPPINGS_FILE_PATH))
            self._mappings = {mapping["kind"]: mapping["mappings"] for mapping in mappings.get("resources") or []}
        return self._mappings

    def get_compiled_mappings(self, mapping_kind: str) -> list[Any]:
        if mapping_kind not in self._compiled_mappings:
            try:
                self._compiled_mappings[mapping_kind] = self._compile_mappings(self.mappings.get(mapping_kind) or {})
            except Exception as e:
                raise MapperCompilationError(mapping_kind) from e
        return self._compiled_mappings[mapping_kind]

    def _compile_mappings(self, item: Any) -> Any:
        if isinstance(item, dict):
            return {key: self._compile_mappings(value) for key, value in item.items()}
        if isinstance(item, list | tuple | set):
            return [self._compile_mappings(value) for value in item]
        if isinstance(item, str):
            try:
                return jq.compile(item)
            except Exception as e:
                raise Exception(f"Error compiling maps with expression {item}: {e}") from e
        return item

    def _map_data(self, compiled_mapping: Any, context: dict[str, Any]) -> Any:
        if isinstance(compiled_mapping, dict):
            return {key: self._map_data(value, context) for key, value in compiled_mapping.items()}
        if isinstance(compiled_mapping, list):
            return [self._map_data(item, context) for item in compiled_mapping]
        if isinstance(compiled_mapping, jq._Program):
            try:
                return compiled_mapping.input(context).first()
            except Exception as e:
                raise Exception(f"Error mapping with expression {compiled_mapping} and payload {context}: {e}") from e
        return compiled_mapping

    def _map_entity(self, compiled_mapping: dict, json_data: dict[str, Any]) -> dict:
        return self._sanitize(self._map_data(compiled_mapping, json_data))

    def _replace_non_matching_characters(self, input_string: str, regex_pattern: str) -> str:
        res = re.sub(regex_pattern, ".", input_string)
        return res

    def _sanitize(self, entity: dict) -> dict:
        if entity.get("id"):
            entity["id"] = self._replace_non_matching_characters(str(entity["id"]).lower(), self.id_allowed_chars)

        for relation in entity.get("relations", {}).values():
            if not relation.get("value"):
                continue

            if isinstance(relation["value"], list):
                relation["value"] = [
                    value
                    if not value
                    else self._replace_non_matching_characters(str(value).lower(), self.id_allowed_chars)
                    for value in relation["value"]
                ]
            else:
                relation["value"] = self._replace_non_matching_characters(
                    str(relation["value"]).lower(), self.id_allowed_chars
                )

        return entity

    def process_sync(self, mapping_kind: str, json_data: list[dict], context: Any | None = None) -> list[Any]:
        mappings = self.get_compiled_mappings(mapping_kind)
        if not mappings:
            raise MapperNotFoundError(mapping_kind)
        return [self._map_entity(mappings, {**each, "context": context}) for each in json_data]

    async def process(self, mapping_kind: str, json_data: list[dict], context: Any | None = None) -> tuple[Any]:
        # There is no advantage in using async here as all the work is done in a thread.
        # Keeping it as async for now to avoid breaking existing code that calls this as `await mapper.process(...)`.
        return await run_in_thread(self.process_sync, mapping_kind, json_data, context)


class MapperError(Exception):
    """Base class for Mapper errors."""


class MapperNotFoundError(MapperError):
    """Mapper not found error."""

    def __init__(self, mapping_kind: str):
        super().__init__(f"Unknown Mapper {mapping_kind}")


class MapperCompilationError(MapperError):
    """Mapper compilation error."""

    def __init__(self, mapping_kind: str):
        super().__init__(f"Error compiling mappings for kind {mapping_kind}")
