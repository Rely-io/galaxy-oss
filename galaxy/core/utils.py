import logging
import os
import random
import string
import traceback
from typing import Any

import aiohttp
from aiohttp import ClientResponseError
from fastapi import HTTPException, Request, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import ValidationError

from galaxy.core.magneto import Magneto
from galaxy.core.mapper import Mapper
from galaxy.core.models import Config, FileCheckList


def from_env(variable, raise_exception=False) -> str | int:
    value = os.environ.get(variable)
    if raise_exception:
        if value is None:
            raise ValueError(f"Required environment variable {variable} not set.")
        return value
    return value


def get_config_value(param, config, config_path) -> str | int:
    value = param
    if value is None:
        value = config
        if value is None:
            raise Exception(f"{config_path} not found in config file, in environment variables, or as input parameter.")
    return value


async def make_request(session: aiohttp.ClientSession, method: str, url: str, **kwargs) -> dict:
    try:
        async with session.request(method, url, **kwargs) as response:
            if response.status // 100 == 2:
                if kwargs.get("headers", {}).get("Content-Type") in ("text/plain",):
                    return await response.text()
                else:
                    return await response.json()
            response.raise_for_status()
    except ClientResponseError as e:
        if e.status == 401:
            raise Exception("Unauthorized response from client integration API: Please check your API credentials")
        if 400 <= e.status < 500:
            traceback.print_exc()
            raise Exception(f"Client integration API error: {e.status} {e.message}")
        elif 500 <= e.status < 600:
            traceback.print_exc()
            raise Exception(f"Client server integration API error: {e.status} {e.message}")
        # Raise for other unexpected status codes
        else:
            raise Exception(f"Error: {e.status} {e.message}")
    except aiohttp.ClientError as e:
        # Handle other aiohttp client errors
        raise Exception(f"Request for client integration API failed: {str(e)}")


async def update_integration_config_entity(
    magneto_client: Magneto, integration_config_entity: dict, properties: dict[str, Any]
) -> None:
    try:
        await magneto_client.upsert_entity(
            {
                "id": integration_config_entity["id"],
                "blueprintId": integration_config_entity["blueprintId"],
                "properties": properties,
            }
        )
    except Exception as e:
        raise Exception(f"Error updating integration config entity: {str(e)}")


async def get_mapper(request: Request) -> Mapper:
    return request.app.state.mapper


async def get_logger(request: Request) -> logging.Logger:
    return request.app.state.logger


async def get_magneto_client(request: Request) -> Magneto:
    async with request.app.state.magneto_client as client:
        yield client


async def get_api_key(api_key_header: str = Security(APIKeyHeader(name="authorization", auto_error=True))) -> bool:
    token = os.environ.get("RELY_GALAXY_API_TOKEN", None) or "".join(
        random.choices(string.ascii_uppercase + string.digits, k=10)
    )
    if api_key_header == f"Bearer {token}":
        return True
    else:
        raise HTTPException(status_code=403, detail="Could not validate credentials")


def files_to_check(config: Config, logger: logging.Logger) -> list[dict]:
    files_to_check: list | str | FileCheckList = config.integration.properties.get("filesToCheck", "")

    if isinstance(files_to_check, str):
        try:
            files_check_list = FileCheckList.model_validate_json(files_to_check)
        except ValidationError as e:
            files_from_str = [
                {"path": fc[0], "destination": fc[1], "regex": fc[2]}
                for fc in (file_check.split("::") for file_check in files_to_check.split("||"))
                if len(fc) == 3 and fc[0] and fc[1]
            ]

            try:
                files_check_list = FileCheckList.model_validate(files_from_str)
            except ValidationError:
                logger.error(f"Invalid file check config: {files_to_check}: {e}")
                return []

        return list([fc.model_dump() for fc in files_check_list])

    if isinstance(files_to_check, list):
        try:
            files_check_list = FileCheckList.model_validate(files_to_check)

            return list([fc.model_dump() for fc in files_check_list])
        except ValidationError:
            logger.error(f"Invalid file check config: {files_to_check}")
            return []

    logger.warning(f"Invalid file check config: {files_to_check}")
    return []
