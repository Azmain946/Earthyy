"""RQ worker entry point.

Run with:  python -m app.workers.worker
"""
from redis import Redis
from rq import Worker

from app.core.config import get_settings
from app.core.logging import configure_logging


def main() -> None:
    configure_logging()
    settings = get_settings()
    conn = Redis.from_url(settings.redis_url)
    worker = Worker([settings.job_queue_name], connection=conn)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
