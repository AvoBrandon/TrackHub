"""Apple Push Notification service, token-based auth (no certificates to renew).

Requires: APNS_TEAM_ID, APNS_KEY_ID, the .p8 key file, and APNS_BUNDLE_ID matching the iOS app.
Windows does not need push: the desktop app polls /alerts every minute and shows a native toast.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import httpx
import jwt

from ..config import get_settings

log = logging.getLogger(__name__)
_cached_jwt: tuple[str, float] | None = None


def configured() -> bool:
    s = get_settings()
    return bool(s.apns_team_id and s.apns_key_id and Path(s.apns_key_file).exists())


def _token() -> str:
    global _cached_jwt
    s = get_settings()
    now = time.time()
    if _cached_jwt and now - _cached_jwt[1] < 2400:  # Apple: reuse 20-60 min
        return _cached_jwt[0]
    key = Path(s.apns_key_file).read_text()
    tok = jwt.encode({"iss": s.apns_team_id, "iat": int(now)}, key, algorithm="ES256", headers={"kid": s.apns_key_id})
    _cached_jwt = (tok, now)
    return tok


async def send(device_token: str, title: str, body: str, payload: dict | None = None, badge: int | None = None) -> bool:
    s = get_settings()
    host = "https://api.sandbox.push.apple.com" if s.apns_use_sandbox else "https://api.push.apple.com"
    aps: dict = {"alert": {"title": title, "body": body}, "sound": "default", "mutable-content": 1}
    if badge is not None:
        aps["badge"] = badge
    data = {"aps": aps, **(payload or {})}
    headers = {"authorization": f"bearer {_token()}", "apns-topic": s.apns_bundle_id, "apns-push-type": "alert",
               "apns-priority": "10"}
    async with httpx.AsyncClient(http2=True, timeout=15) as c:
        r = await c.post(f"{host}/3/device/{device_token}", headers=headers, content=json.dumps(data))
    if r.status_code == 200:
        return True
    log.warning("apns %s: %s", r.status_code, r.text[:200])
    return r.status_code in (400, 410) and "BadDeviceToken" in r.text  # treat dead tokens as 'handled'
