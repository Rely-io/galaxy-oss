from fastapi import APIRouter, Depends

from galaxy.core.magneto import Magneto
from galaxy.core.mapper import Mapper
from galaxy.core.utils import get_mapper, get_logger, get_magneto_client

import logging

router = APIRouter(prefix="/gitlab", tags=["gitlab"])


@router.post("/webhook")
async def gitlab_webhook(
    event: dict,
    mapper: Mapper = Depends(get_mapper),
    logger: logging = Depends(get_logger),
    magneto_client: Magneto = Depends(get_magneto_client),
) -> dict:
    try:
        entity = await mapper.process(f"{event.get('object_kind')}_hook", [event])
        logger.info(f"Received entity: {entity}")
    except IndexError:
        logger.warning(f"No mapping found for webhook event: '{event.get('object_kind')}'. Skipping execution")

    return {"message": "received gitlab webhook"}
