from logging import Logger

from fastapi import APIRouter, Depends

from galaxy.core.magneto import Magneto
from galaxy.core.mapper import Mapper
from galaxy.core.utils import get_mapper, get_logger, get_magneto_client

router = APIRouter(prefix="/{{cookiecutter.integration_name}}", tags=["{{cookiecutter.integration_name}}"])


@router.post("/webhook")
async def {{cookiecutter.integration_name}}_webhook(
    event: dict,
    mapper: Mapper = Depends(get_mapper),
    logger: Logger = Depends(get_logger),
    magneto_client: Magneto = Depends(get_magneto_client),
) -> None:
    try:
        entity, *_ = await mapper.process("entities", [event])
        logger.info("Received entity: %s", entity)
    except Exception:
        ...
        return

    try:
        await magneto_client.upsert_entity(entity)
    except Exception:
        ...
