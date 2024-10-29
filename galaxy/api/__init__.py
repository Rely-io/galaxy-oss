import importlib
import logging
from datetime import datetime

import anyio
import uvicorn
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_REMOVED, EVENT_JOB_SUBMITTED
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import Depends, FastAPI, HTTPException

from galaxy.core.galaxy import Integration, run_integration
from galaxy.core.logging import get_log_format
from galaxy.core.magneto import Magneto
from galaxy.core.mapper import Mapper
from galaxy.core.models import SchedulerJobStates
from galaxy.core.resources import get_integration_module_name
from galaxy.core.utils import get_api_key


async def run_app(instance: Integration):
    logger = logging.getLogger("galaxy")

    app = FastAPI()
    app.state.config = instance.config
    app.state.mapper = Mapper(instance.type_)
    app.state.magneto_client = Magneto(instance.config.rely.url, instance.config.rely.token, logger=logger)
    app.state.logger = logger

    try:
        module = importlib.import_module(f"{get_integration_module_name(instance.type_)}.routes")
        app.include_router(module.router)
    except ModuleNotFoundError:
        logger.warning("Integration type %r routes not found", instance.type_)

    job_defaults = {"coalesce": False, "max_instances": 1, "misfire_grace_time": None}
    job_stores = {"default": MemoryJobStore()}
    job_states = {}

    scheduler = AsyncIOScheduler(jobstores=job_stores, job_defaults=job_defaults)
    app.state.scheduler = scheduler

    def job_listener(event):
        job_id = event.job_id
        if event.code == EVENT_JOB_SUBMITTED:
            job_states[job_id] = SchedulerJobStates.EVENT_JOB_SUBMITTED
        elif event.code == EVENT_JOB_EXECUTED:
            job_states[job_id] = SchedulerJobStates.EVENT_JOB_EXECUTED
        elif event.code == EVENT_JOB_ERROR:
            job_states[job_id] = SchedulerJobStates.EVENT_JOB_ERROR
        elif event.code == EVENT_JOB_REMOVED:
            job_states.pop(job_id, None)

    scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_SUBMITTED | EVENT_JOB_REMOVED)

    async def _run_integration():
        async with Magneto(instance.config.rely.url, instance.config.rely.token, logger=logger) as magneto_client:
            success = await run_integration(instance, magneto_client=magneto_client, logger=app.state.logger)
            if success:
                logger.info("Integration %r run completed successfully: %r", instance.type_, instance.id_)
            else:
                logger.error("Integration %r run failed: %r", instance.type_, instance.id_)

    @app.on_event("startup")
    async def startup_event():
        scheduler.add_job(
            _run_integration,
            id=f"{app.state.config.integration.type}-startup",
            name=f"{app.state.config.integration.type}",
            trigger=DateTrigger(run_date=datetime.now()),
        )
        scheduler.add_job(
            _run_integration,
            id=f"{app.state.config.integration.type}",
            name=f"{app.state.config.integration.type}",
            trigger=IntervalTrigger(minutes=app.state.config.integration.scheduled_interval),
        )
        scheduler.start()

    @app.on_event("shutdown")
    async def shutdown_event():
        scheduler.shutdown(wait=True)

    @app.get("/health")
    async def health():
        jobs = app.state.scheduler.get_jobs()
        return {"status": "up", "jobs": [str(job) for job in jobs]}

    @app.get("/live")
    async def live():
        return {"status": "alive"}

    @app.post("/trigger/{integration_type}", dependencies=[Depends(get_api_key)])
    async def trigger_integration(integration_type: str) -> dict:
        job = app.state.scheduler.get_job(integration_type)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job_states.get(integration_type, None) == SchedulerJobStates.EVENT_JOB_SUBMITTED:
            raise HTTPException(status_code=425, detail=f"Job already running. Next schedule run: {job.next_run_time}")
        app.state.scheduler.modify_job(integration_type, next_run_time=datetime.now())
        return {"status": "Job triggered"}

    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["default"]["fmt"] = get_log_format(instance.config)
    log_config["formatters"]["access"]["fmt"] = get_log_format(instance.config)
    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, log_config=log_config)
    server = uvicorn.Server(config=config)
    async with anyio.create_task_group() as task_group:
        task_group.start_soon(server.serve)
