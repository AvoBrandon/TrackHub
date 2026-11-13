"""Entry point: `uvicorn app.main:app --host 0.0.0.0 --port 8787` (or `python -m app`)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import scheduler as sched
from .api.routes import public, router
from .config import get_settings
from .db import init_db

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.scheduler = None
    if settings.scheduler_enabled:
        app.state.scheduler = sched.build()
        app.state.scheduler.start()
        await sched.run_startup_sweep()
    yield
    if app.state.scheduler:
        app.state.scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(public)
app.include_router(router, prefix="/api")
