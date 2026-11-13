from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings

_engine = None


def engine():
    global _engine
    if _engine is None:
        s = get_settings()
        s.data_dir  # ensure exists
        _engine = create_engine(s.database_url, connect_args={"check_same_thread": False} if s.database_url.startswith("sqlite") else {})
    return _engine


def init_db() -> None:
    from . import models  # noqa: F401  (register tables)

    SQLModel.metadata.create_all(engine())


@contextmanager
def session() -> Iterator[Session]:
    with Session(engine()) as s:
        yield s


def get_session() -> Iterator[Session]:
    with Session(engine()) as s:
        yield s
