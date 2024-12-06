from logging import Logger

from fastapi import APIRouter, Depends

from galaxy.core.magneto import Magneto
from galaxy.core.mapper import Mapper
from galaxy.core.utils import get_logger, get_mapper, get_magneto_client
from galaxy.integrations.flux.models import Event, Reason

router = APIRouter(prefix="/flux", tags=["flux"])


@router.post("/webhook")
async def flux_webhook(
    event: Event,
    mapper: Mapper = Depends(get_mapper),
    logger: Logger = Depends(get_logger),
    magneto_client: Magneto = Depends(get_magneto_client),
) -> None:
    match event.reason:
        case Reason.PROGRESSING | Reason.PROGRESSING_WITH_RETRY:
            return
        case (
            Reason.RECONCILIATION_SUCCEEDED
            | Reason.INSTALL_SUCCEEDED
            | Reason.UPGRADE_SUCCEEDED
            | Reason.TEST_SUCCEEDED
        ):
            status = "success"
        case _:
            status = "failure"

    revision = event.metadata["revision"] if event.metadata else "?"
    try:
        entity, *_ = await mapper.process("pipeline", [event.model_dump()], context={"status": status})
    except Exception:
        logger.error(
            "Failed to process event for %s/%s, revision: %s",
            event.involved_object.kind,
            event.involved_object.name,
            revision,
        )
        return

    try:
        await magneto_client.upsert_entity(entity)
    except Exception:
        logger.error(
            "Failed to push entity for %s/%s, revision: %s",
            event.involved_object.kind,
            event.involved_object.name,
            revision,
        )
