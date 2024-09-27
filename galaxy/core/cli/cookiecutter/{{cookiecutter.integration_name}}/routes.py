from fastapi import APIRouter, Depends

from galaxy.core.magneto import Magneto
from galaxy.core.mapper import Mapper
from galaxy.core.utils import get_mapper, get_logger, get_magneto_client

import logging

router = APIRouter(prefix="/{{cookiecutter.integration_name}}", tags=["{{cookiecutter.integration_name}}"])


@router.post("/webhook")
async def {{cookiecutter.integration_name}}_webhook(
    event: dict,
    mapper: Mapper = Depends(get_mapper),
    logger: logging = Depends(get_logger),
    magneto_client: Magneto = Depends(get_magneto_client),
) -> dict:
    entity = await mapper.process("entities", [event])
    logger.info(f"Received entity: {entity}")
    return {"message": "received gitlab webhook"}
