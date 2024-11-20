import logging
import traceback
from collections import Counter
from collections.abc import AsyncGenerator, Collection
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, TypeAlias

import magneto_api_client
from magneto_api_client import (
    ApiResponse,
    BlueprintCreate,
    BlueprintRead,
    EntityUpdate,
    FlowUpdate,
    TaskCreate,
    TaskData,
    TaskRead,
    TaskType,
)
from magneto_api_client import models as magneto_models
from magneto_api_client.exceptions import ApiException, BadRequestException, NotFoundException
from pydantic import ValidationError

from galaxy.utils.itertools import chunks

__all__ = ["Magneto", "magneto_models", "TaskWithEntities"]


TaskWithEntities: TypeAlias = tuple[TaskRead, list[dict[str, Any]]]


class Magneto:
    BULK_CHUNK_SIZE: int = 100

    def __init__(self, magneto_url: str, magneto_token: str, logger: logging.Logger):
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

    async def get_automation(self, automation_id: str) -> dict[str, Any]:
        api_instance = magneto_api_client.FlowsApi(self.session)
        try:
            result = await api_instance.get_flow_api_v1_flows_id_get(automation_id)
            return result.to_dict()
        except Exception as e:
            raise Exception("Exception when calling FlowsApi->get_flow_api_v1_flows_id_get: %s\n" % e)

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

    async def get_task(self, task_id: str) -> TaskRead:
        api_instance = magneto_api_client.TasksApi(self.session)
        try:
            return await api_instance.get_task_by_id_api_v1_tasks_id_get(task_id)
        except Exception as e:
            raise Exception("Exception when calling TasksApi->get_task_api_v1_tasks_id_get: %s\n" % e)

    async def get_tasks(self, task_ids: Collection[str]) -> AsyncGenerator[TaskRead, None]:
        # Currently there is not an endpoint to get multiple tasks, so this is a custom implementation that just
        # calls get_task for each task_id
        for task_id in task_ids:
            task = await self.get_task(task_id)
            yield task

    async def create_task(self, task: dict[str, Any] | TaskCreate) -> TaskRead:
        if isinstance(task, dict):
            try:
                task: TaskCreate = TaskCreate.from_dict(task)
            except ValidationError as e:
                raise Exception(f"Task validation error: {e}")

        self.logger.debug("Magneto Client: creating task of type %r", task.type)

        api_instance = magneto_api_client.TasksApi(self.session)
        try:
            api_response: ApiResponse[TaskRead] = await api_instance.create_task_api_v1_tasks_post_with_http_info(task)
        except ApiException as e:
            message = e.reason or e.body
            if message is None:
                try:
                    message = str(e)
                except Exception:
                    self.logger.warning(
                        "Unable to parse error message on TasksApi->create_task_api_v1_tasks_post: %s", e
                    )
            raise MagnetoApiError(status_code=int(e.status or 500), message=message) from e
        except Exception as e:
            raise Exception(f"Exception when calling TasksApi->create_task_api_v1_tasks_post: {e}")

        if api_response.status_code >= HTTPStatus.BAD_REQUEST:
            raise MagnetoApiError(status_code=api_response.status_code, message=api_response.raw_data.decode())

        self.logger.debug("Task created: %r", api_response.data.id)
        return api_response.data

    async def upsert_entities_bulk_task(
        self, entities: list[dict[str, Any]], update_properties_and_relations_only: bool = False, patch: bool = True
    ) -> TaskRead:
        params = {
            "unmapped_properties": "ignore",
            "patch": patch,
            "update_properties_and_relations_only": update_properties_and_relations_only,
        }
        task_create = TaskCreate(type=TaskType.ENTITIES_BULK_UPSERT, data=TaskData(payload=entities, parameters=params))
        return await self.create_task(task_create)

    async def upsert_entities_bulk_chunks(
        self,
        entities: list[dict[str, Any]],
        update_properties_and_relations_only: bool = False,
        patch: bool = True,
        chunk_size: int = BULK_CHUNK_SIZE,
    ) -> list[TaskWithEntities]:
        """Create tasks to upsert entities in chunks to avoid hitting the API limits.

        There are two error scenarios when creating a task that support a retry mechanism:
            - if the API request fails with 413 (Request Entity Too Large): this means that the request is too large
                and we need to split the request in smaller chunks
            - if the API request fails with 422 (Unprocessable Entity): this means that the request payload contains
                invalid data and we split it into smaller chunks to try to isolate the issue
        If there are still errors after the retries that contain a single entity is means that the issues are related
        to the entities of those tasks.

        Args:
            entities: list of entities to upsert
            update_properties_and_relations_only: if True, only properties and relations will be updated
            patch: if True, only properties and relations will be updated
            chunk_size: number of entities to upsert in each chunk

        Returns:
            list of tasks created
        """
        created_tasks = []

        missing_entities = []
        entities_to_add = entities
        errors_counter = Counter()

        while True:
            for chunk in chunks(entities_to_add, chunk_size):
                try:
                    task = await self.upsert_entities_bulk_task(
                        chunk, update_properties_and_relations_only=update_properties_and_relations_only, patch=patch
                    )
                    created_tasks.append((task, chunk))
                except MagnetoApiError as e:
                    if e.status_code not in (HTTPStatus.REQUEST_ENTITY_TOO_LARGE, HTTPStatus.UNPROCESSABLE_ENTITY):
                        raise

                    if chunk_size <= 1:
                        errors_counter[e.status_code] += 1
                        self.logger.debug(
                            "Failed to create task to insert entity %r to Rely API: %r (entity: %r)",
                            chunk[0].get("id"),
                            e,
                            chunk[0],
                        )
                    missing_entities.extend(chunk)

            if len(missing_entities) == 0:
                break

            if chunk_size <= 1:
                break

            self.logger.warning(
                "Failed to create task to insert %d entities to Rely API. Retrying...", len(missing_entities)
            )

            chunk_size //= 2
            entities_to_add = missing_entities
            missing_entities = []

        for error_status, errors_count in errors_counter.items():
            self.logger.warning(
                "Failed to create task to insert %d entities to Rely API with status code %d",
                errors_count,
                error_status,
            )

        return created_tasks


@dataclass(kw_only=True)
class MagnetoApiError(Exception):
    status_code: int
    message: str | None = None

    def __str__(self):
        return f"{self.status_code}: {self.message}"
