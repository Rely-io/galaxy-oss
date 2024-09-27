import logging
import traceback
from typing import Any

import aiohttp

import magneto_api_client

from magneto_api_client import EntityUpdate, BlueprintCreate, BlueprintRead, FlowUpdate
from tenacity import retry, stop_after_attempt, wait_random_exponential, before_sleep_log


__all__ = ["Magneto"]


class Magneto:
    def __init__(self, magneto_url: str, magneto_token: str, logger: logging.Logger):
        # TODO: remove this strip once the magneto env var can be updated to the url root. For compatibility with old
        #  strip the /api/v1 from the end of the url if it exists
        self.magneto_url = magneto_url.rstrip("/api/v1")
        self.magneto_token = magneto_token
        self.logger = logger
        self.headers = {"Authorization": f"Bearer {magneto_token}", "Content-Type": "application/json"}
        self.session = None

    async def __aenter__(self):
        self.session = magneto_api_client.ApiClient(
            magneto_api_client.Configuration(access_token=self.magneto_token, host=self.magneto_url)
        )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()

    async def get_entity(self, entity_id: str) -> dict | None:
        async with self.session as api_client:
            api_instance = magneto_api_client.EntitiesApi(api_client)
            try:
                result = await api_instance.get_entity_api_v1_entities_id_get(entity_id)
                return result.to_dict()
            except Exception as e:
                raise Exception("Exception when calling EntitiesApi->get_entity_api_v1_entities_id_get: %s\n" % e)

    def _delete_none(self, _dict: dict) -> None:
        """Delete None values recursively from all the dictionaries"""
        for key, value in list(_dict.items()):
            if isinstance(value, dict):
                self._delete_none(value)
            elif value is None:
                del _dict[key]
            elif isinstance(value, list):
                for v_i in value:
                    if isinstance(v_i, dict):
                        self._delete_none(v_i)

    async def upsert_entity(self, entity: dict, patch: bool = True) -> dict | None:
        async with self.session as api_client:
            self._delete_none(entity["properties"])
            api_instance = magneto_api_client.EntitiesApi(api_client)
            try:
                api_response = await api_instance.upsert_entity_api_v1_entities_id_put(
                    entity["id"], EntityUpdate.from_dict(entity), patch=patch
                )
                return api_response.to_dict()
            except Exception as e:
                traceback.print_exc()
                raise Exception("Exception when calling EntitiesApi->upsert_entity_api_v1_entities_id_put: %s\n" % e)

    async def get_plugin(self, plugin_id: str) -> dict:
        async with self.session as api_client:
            api_instance = magneto_api_client.LegacyPluginsApi(api_client)
            try:
                result = await api_instance.get_plugin_api_v1_legacy_plugins_id_get(plugin_id)
                return result.to_dict()
            except Exception as e:
                raise Exception(
                    "Exception when calling LegacyPluginsApi->get_plugin_api_v1_legacy_plugins_id_get: %s\n" % e
                )

    def split_entities_into_chunks(self, entities: list[dict], chunk_size: int) -> list[list[dict]]:
        chunks = []
        for i in range(0, len(entities), chunk_size):
            chunks.append([entity_id for entity_id in entities[i : i + chunk_size]])

        return chunks

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_random_exponential(min=1, max=60),
        before_sleep=before_sleep_log(logging.getLogger("galaxy"), logging.WARNING),
        reraise=True,
    )
    async def insert_or_update_entities_bulk(
        self, entities: list[dict], update_only_properties_and_relations: bool = False, patch: bool = True
    ) -> list[dict]:
        added = []

        url_path = "/api/v1/entities/bulk?unmappedProperties=ignore"
        if patch:
            url_path += "&patch=True"
        if update_only_properties_and_relations:
            url_path += "&updatePropertiesAndRelationsOnly=True"

        for chunk in self.split_entities_into_chunks(entities, 99):
            self.logger.info(f"Inserting {len(chunk)} entities to Rely API")
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                response = await session.request(
                    "PUT", f"{self.magneto_url}{url_path}", headers=self.headers, json=chunk
                )
                if response.status // 100 != 2:
                    raise Exception(f"Error inserting entities to Rely API. {await response.text()}")
                else:
                    added.extend(await response.json())
        return added

    async def get_blueprint(self, blueprint_id: str) -> dict[str, Any]:
        async with self.session as api_client:
            api_instance = magneto_api_client.BlueprintsApi(api_client)
            try:
                response = await api_instance.get_blueprint_api_v1_blueprints_id_get(blueprint_id)
                return response.to_dict()
            except Exception as e:
                raise Exception("Exception when get_blueprint: %s\n" % e)

    async def insert_or_update_blueprint_bulk(self, blueprints: list[dict]) -> list[Any] | list[BlueprintRead]:
        async with self.session as api_client:
            res = []
            bps_to_create = []
            for new_bp in blueprints:
                bps_to_create.append(BlueprintCreate.from_dict(new_bp))

            if len(bps_to_create) == 0:
                return res

            api_instance = magneto_api_client.BlueprintsApi(api_client)
            try:
                response = await api_instance.create_or_update_blueprints_bulk_api_v1_blueprints_bulk_put(
                    bps_to_create, user_editable=False
                )
                return response + res
            except Exception as e:
                raise Exception("Exception when calling insert_or_update_blueprint_bulk: %s\n" % e)

    async def upsert_blueprint_relation(self, blueprint_id: str, relation_data: dict) -> None:
        async with self.session as api_client:
            api_instance = magneto_api_client.BlueprintsApi(api_client)
            try:
                await api_instance.create_blueprint_relations_api_v1_blueprints_id_relations_post(
                    blueprint_id, relation_data
                )
            except Exception as e:
                if "already has a relation with key" in str(e):
                    return
                else:
                    raise Exception("Exception when calling upsert_blueprint_relation: %s\n" % e)

    async def upsert_automation(self, flow: dict, trigger: bool = False) -> dict | None:
        async with self.session as api_client:
            api_instance = magneto_api_client.FlowsApi(api_client)
            try:
                api_response = await api_instance.upsert_flow_api_v1_flows_id_put(
                    flow["id"], FlowUpdate.from_dict(flow), trigger=trigger
                )
                return api_response.to_dict()
            except Exception as e:
                raise Exception("Exception when calling FlowsApi->upsert_flow_api_v1_flows_id_put: %s\n" % e)
