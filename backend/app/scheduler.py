from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .config import get_settings
from .services import JOBS, run_job

log = logging.getLogger(__name__)


def build() -> AsyncIOScheduler:
    s = get_settings()
    sch = AsyncIOScheduler(timezone=s.timezone)

    def add(name: str, trigger):
        sch.add_job(run_job, trigger, args=[name, JOBS[name]], id=name, max_instances=1, coalesce=True,
                    misfire_grace_time=3600)

    add("ingest_gmail", IntervalTrigger(minutes=30))
    add("return_windows", CronTrigger(hour=8, minute=0))
    add("price_adjust", CronTrigger(hour=10, minute=0))
    add("watches", IntervalTrigger(hours=6))
    add("flights", IntervalTrigger(minutes=s.flight_status_poll_minutes))
    add("hotels", CronTrigger(hour=s.hotel_recheck_hour, minute=0))
    add("tsa", CronTrigger(hour=s.tsa_morning_hour, minute=0))
    add("trip_brief", CronTrigger(hour=s.trip_brief_hour, minute=0))
    add("subscriptions", CronTrigger(day=1, hour=9, minute=0))
    add("push", IntervalTrigger(minutes=1))
    return sch


async def run_startup_sweep() -> None:
    """On boot, run the cheap daily jobs once so a restart never means a missed deadline."""
    for name in ("return_windows", "subscriptions", "trip_brief"):
        await run_job(name, JOBS[name])
