import importlib
from datetime import datetime

import asyncio

from fastapi import FastAPI, Depends, HTTPException
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_SUBMITTED, EVENT_JOB_REMOVED
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

import logging
from galaxy.core.galaxy import call_methods
from galaxy.core.logging import get_log_format
from galaxy.core.magneto import Magneto

from galaxy.core.mapper import Mapper
import uvicorn
from galaxy.core.models import SchedulerJobStates

from galaxy.core.utils import get_api_key


async def run_app(methods, config):
    app = FastAPI()
    logger = logging.getLogger("galaxy")
    app.state.config = config
    app.state.mapper = Mapper(config.integration.type)
    app.state.magneto_client = Magneto(config.rely.url, config.rely.token, logger=logger)
    app.state.logger = logger
    try:
        module = importlib.import_module(f"galaxy.integrations.{config.integration.type}.routes")
        app.include_router(module.router)
    except ModuleNotFoundError:
        logger.warning(f"Integration type {config.integration.type} routes not found")

    job_defaults = {"coalesce": False, "max_instances": 1, "misfire_grace_time": None}
    job_stores = {"default": MemoryJobStore()}
    job_params = {"instance": methods, "config": config}
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

    @app.on_event("startup")
    async def startup_event():
        scheduler.add_job(
            call_methods,
            id=f"{app.state.config.integration.type}-startup",
            name=f"{app.state.config.integration.type}",
            trigger=DateTrigger(run_date=datetime.now()),
            kwargs=job_params,
        )
        scheduler.add_job(
            call_methods,
            id=f"{app.state.config.integration.type}",
            name=f"{app.state.config.integration.type}",
            trigger=IntervalTrigger(minutes=app.state.config.integration.scheduled_interval),
            kwargs=job_params,
        )
        scheduler.start()

    @app.on_event("shutdown")
    async def shutdown_event():
        scheduler.shutdown(wait=True)

    @app.get("/health")
    async def health():
        jobs = app.state.scheduler.get_jobs()
        return {"status": "up", "jobs": [str(job) for job in jobs]}

    @app.post("/trigger/{integration_type}", dependencies=[Depends(get_api_key)])
    async def trigger_integration(integration_type: str) -> dict:
        job = app.state.scheduler.get_job(integration_type)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job_states.get(integration_type, None) == SchedulerJobStates.EVENT_JOB_SUBMITTED:
            raise HTTPException(status_code=425, detail=f"Job already running. Next schedule run: {job.next_run_time}")
        app.state.scheduler.modify_job(integration_type, next_run_time=datetime.now())
        return {"status": "Job triggered"}

    loop = asyncio.get_running_loop()
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["default"]["fmt"] = get_log_format(config)
    log_config["formatters"]["access"]["fmt"] = get_log_format(config)
    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, loop=loop, log_config=log_config)
    server = uvicorn.Server(config=config)
    await server.serve()
