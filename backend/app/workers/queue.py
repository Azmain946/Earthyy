"""Job queue integration (RQ + Redis).

`enqueue_analysis` either pushes the job to the RQ queue (normal operation)
or runs it inline when EARTHYY_EAGER_JOBS=true (tests / single-process dev).
"""
from __future__ import annotations

import logging

from redis import Redis
from rq import Queue

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_queue: Queue | None = None


def get_queue() -> Queue:
    global _queue
    if _queue is None:
        _queue = Queue(
            settings.job_queue_name,
            connection=Redis.from_url(settings.redis_url),
            default_timeout=1800,
        )
    return _queue


def enqueue_analysis(job_id: str) -> None:
    from app.services.analysis_runner import run_analysis_job

    if settings.eager_jobs:
        logger.info("event=job_eager_run job=%s", job_id)
        run_analysis_job(job_id)
        return
    get_queue().enqueue(run_analysis_job, job_id, job_id=f"analysis-{job_id}")
    logger.info("event=job_enqueued job=%s", job_id)
