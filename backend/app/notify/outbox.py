"""Create alerts idempotently. Every watcher funnels through `emit`; dedupe_key prevents repeats."""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlmodel import Session, select

from ..models import Alert, AlertKind

log = logging.getLogger(__name__)


def emit(s: Session, kind: AlertKind, dedupe_key: str, title: str, body: str, *,
         money: float = 0.0, action_url: str = "", payload: dict[str, Any] | None = None) -> Alert | None:
    if s.exec(select(Alert).where(Alert.dedupe_key == dedupe_key)).first():
        return None
    a = Alert(kind=kind, dedupe_key=dedupe_key, title=title[:120], body=body[:2000], money_at_stake=round(money, 2),
              action_url=action_url, payload_json=json.dumps(payload or {}, default=str))
    s.add(a)
    s.commit()
    s.refresh(a)
    log.info("alert %s: %s", kind.value, title)
    return a
