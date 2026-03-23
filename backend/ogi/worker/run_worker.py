"""Entry point for starting an RQ worker that processes transform jobs.

Usage:
    python -m ogi.worker.run_worker
"""

from __future__ import annotations

import logging

from redis import Redis
from rq import Worker, Queue

from ogi.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ogi.worker")


def main() -> None:
    conn = Redis.from_url(settings.redis_url)
    queue = Queue(settings.rq_queue_name, connection=conn)
    logger.info("Starting RQ worker on queue '%s' (redis: %s)", settings.rq_queue_name, settings.redis_url)
    worker = Worker([queue], connection=conn)
    worker.work()


if __name__ == "__main__":
    main()
