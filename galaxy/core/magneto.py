import logging
import traceback
from collections import Counter
from typing import Any

import magneto_api_client
from magneto_api_client import BlueprintCreate, BlueprintRead, EntityUpdate, FlowUpdate
from magneto_api_client.exceptions import BadRequestException, NotFoundException

from galaxy.utils.itertools import chunks
from galaxy.utils.requests import (
    ContentTooLargeError,
    RetryPolicy,
    UnprocessableEntityError,
    make_request,
    with_session,
)

__all__ = ["Magneto"]


class Magneto:
    def __init__(self, magneto_url: str, magneto_token: str, logger: logging.Logger):
        self.magneto_url = magneto_url.rstrip("/api/v1")
        self.magneto_token = magneto_token
        self.logger = logger
        self.headers = {"Authorization": f"Bearer {magneto_token}", "Content-Type": "application/json"}
        self.session = None

        self._bulk_chunk_size = 100

    async def __aenter__(self):
        self.session = magneto_api_client.ApiClient(
            magneto_api_client.Configuration(access_token=self.magneto_token, host=self.magneto_url)
        )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()

    async def get_entity(self, entity_id: str) -> dict | None:
        api_instance = magneto_api_client.EntitiesApi(self.session)
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
        self._delete_none(entity["properties"])
        api_instance = magneto_api_client.EntitiesApi(self.session)
        try:
            api_response = await api_instance.upsert_entity_api_v1_entities_id_put(
                entity["id"], EntityUpdate.from_dict(entity), patch=patch
            )
            return api_response.to_dict()
        except Exception as e:
            traceback.print_exc()
            raise Exception("Exception when calling EntitiesApi->upsert_entity_api_v1_entities_id_put: %s\n" % e)

    async def get_plugin(self, plugin_id: str) -> dict:
        api_instance = magneto_api_client.LegacyPluginsApi(self.session)
        try:
            result = await api_instance.get_plugin_api_v1_legacy_plugins_id_get(plugin_id)
            return result.to_dict()
        except Exception as e:
            raise Exception(
                "Exception when calling LegacyPluginsApi->get_plugin_api_v1_legacy_plugins_id_get: %s\n" % e
            )

    async def insert_or_update_entities_bulk(
        self, entities: list[dict], update_only_properties_and_relations: bool = False, patch: bool = True
    ) -> list[dict]:
        url_path = "/api/v1/entities/bulk?unmappedProperties=ignore"
        if patch:
            url_path += "&patch=True"
        if update_only_properties_and_relations:
            url_path += "&updatePropertiesAndRelationsOnly=True"

        self.logger.info("Inserting %d entities to Rely API", len(entities))

        entities_to_add = entities
        added = []
        missing = []

        errors_counter = Counter()

        async with with_session(headers=self.headers) as session:
            chunk_size = self._bulk_chunk_size
            retry_policy = RetryPolicy(logger=self.logger)
            while True:
                for chunk in chunks(entities_to_add, chunk_size):
                    try:
                        response = await make_request(
                            session, "PUT", f"{self.magneto_url}{url_path}", json=chunk, retry_policy=retry_policy
                        )
                        added.extend(response)
                    except (ContentTooLargeError, UnprocessableEntityError) as e:
                        if chunk_size <= 1:
                            errors_counter[e.status] += 1
                            self.logger.debug(
                                "Failed to insert entity %r to Rely API: %r (entity: %r)",
                                chunk[0].get("id"),
                                e,
                                chunk[0],
                            )
                        missing.extend(chunk)

                if len(missing) == 0:
                    break

                if chunk_size <= 1:
                    break

                self.logger.warning("Failed to insert %d entities to Rely API. Retrying...", len(missing))

                chunk_size //= 2
                entities_to_add = missing
                missing = []

        for error_status, errors_count in errors_counter.items():
            self.logger.warning(
                "Failed to insert %d entities to Rely API with status code %d", errors_count, error_status
            )

        return added

    async def get_blueprint(self, blueprint_id: str) -> dict[str, Any]:
        api_instance = magneto_api_client.BlueprintsApi(self.session)
        try:
            response = await api_instance.get_blueprint_api_v1_blueprints_id_get(blueprint_id)
            return response.to_dict()
        except Exception as e:
            raise Exception("Exception when get_blueprint: %s\n" % e)

    async def insert_or_update_blueprint_bulk(self, blueprints: list[dict]) -> list[Any] | list[BlueprintRead]:
        res = []
        bps_to_create = []
        for new_bp in blueprints:
            bps_to_create.append(BlueprintCreate.from_dict(new_bp))

        if len(bps_to_create) == 0:
            return res

        api_instance = magneto_api_client.BlueprintsApi(self.session)
        try:
            response = await api_instance.create_or_update_blueprints_bulk_api_v1_blueprints_bulk_put(
                bps_to_create, user_editable=False
            )
            return response + res
        except Exception as e:
            raise Exception("Exception when calling insert_or_update_blueprint_bulk: %s\n" % e)

    async def upsert_blueprint_relation(
        self, blueprint_id: str, relation_data: dict, *, raise_if_blueprint_not_found: bool = True
    ) -> None:
        api_instance = magneto_api_client.BlueprintsApi(self.session)
        try:
            await api_instance.create_blueprint_relations_api_v1_blueprints_id_relations_post(
                blueprint_id, relation_data
            )
        except NotFoundException:
            self.logger.warning("Update skipped for blueprint '%s': Blueprint not found." % blueprint_id)
            if not raise_if_blueprint_not_found:
                return
            raise Exception("Exception when calling upsert_blueprint_relation: Blueprint not found\n")
        except Exception as e:
            if "already has a relation with key" in str(e):
                return
            raise Exception("Exception when calling upsert_blueprint_relation: %s\n" % e)

    async def upsert_automation(
        self, flow: dict, trigger: bool = False, *, raise_if_blueprint_not_found: bool = True
    ) -> dict | None:
        api_instance = magneto_api_client.FlowsApi(self.session)
        try:
            api_response = await api_instance.upsert_flow_api_v1_flows_id_put(
                flow["id"], FlowUpdate.from_dict(flow), trigger=trigger
            )
            return api_response.to_dict()
        except BadRequestException as e:
            if (
                not raise_if_blueprint_not_found
                and e.body.startswith('{"detail":"Automation error: Blueprint with id ')
                and e.body.endswith(' not found"}')
            ):
                self.logger.warning("Skipped automation update for '%s': Blueprint not found." % flow["id"])
                return
            raise Exception("Exception when calling FlowsApi->upsert_flow_api_v1_flows_id_put: %s\n" % e)
        except Exception as e:
            raise Exception("Exception when calling FlowsApi->upsert_flow_api_v1_flows_id_put: %s\n" % e)
