"""Gmail reader. OAuth desktop flow once (opens a browser), token refreshed automatically after.

Scope is gmail.readonly only: we never send, delete or label.
"""
from __future__ import annotations

import base64
import logging
from datetime import datetime, timedelta
from pathlib import Path

from dateutil import parser as dtp

from ..config import get_settings
from .parsers.common import RawEmail, extract_jsonld

log = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

QUERY = (
    '(from:amazon.com OR from:bestbuy.com OR from:ebay.com OR subject:(order OR shipped OR delivered OR receipt '
    'OR itinerary OR confirmation OR reservation OR "e-ticket" OR renewal OR subscription OR invoice)) '
    '-category:promotions -category:social'
)


def credentials_ready() -> bool:
    s = get_settings()
    return Path(s.gmail_token_file).exists() or Path(s.gmail_client_secret_file).exists()


def _service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    s = get_settings()
    creds = None
    tok = Path(s.gmail_token_file)
    if tok.exists():
        creds = Credentials.from_authorized_user_file(str(tok), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(s.gmail_client_secret_file, SCOPES)
            creds = flow.run_local_server(port=0)
        tok.parent.mkdir(parents=True, exist_ok=True)
        tok.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")


def _walk(part, acc: dict[str, str]) -> None:
    mime = part.get("mimeType", "")
    body = (part.get("body") or {}).get("data")
    if body and mime in ("text/html", "text/plain"):
        acc[mime] = acc.get(mime, "") + _decode(body)
    for p in part.get("parts", []) or []:
        _walk(p, acc)


def to_raw(msg: dict) -> RawEmail:
    headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
    acc: dict[str, str] = {}
    _walk(msg["payload"], acc)
    try:
        received = dtp.parse(headers.get("date", "")).replace(tzinfo=None)
    except (ValueError, OverflowError):
        received = datetime.fromtimestamp(int(msg.get("internalDate", "0")) / 1000)
    html = acc.get("text/html", "")
    return RawEmail(message_id=msg["id"], sender=headers.get("from", ""), subject=headers.get("subject", ""),
                    received=received, html=html, text=acc.get("text/plain", ""), jsonld=extract_jsonld(html))


def fetch_recent(days: int | None = None, known_ids: set[str] | None = None, max_messages: int = 400) -> list[RawEmail]:
    s = get_settings()
    days = days or s.gmail_lookback_days
    svc = _service()
    after = (datetime.utcnow() - timedelta(days=days)).strftime("%Y/%m/%d")
    q = f"{QUERY} after:{after}"
    ids: list[str] = []
    token = None
    while len(ids) < max_messages:
        resp = svc.users().messages().list(userId="me", q=q, maxResults=100, pageToken=token).execute()
        ids += [m["id"] for m in resp.get("messages", [])]
        token = resp.get("nextPageToken")
        if not token:
            break
    known_ids = known_ids or set()
    out: list[RawEmail] = []
    for mid in ids:
        if mid in known_ids:
            continue
        msg = svc.users().messages().get(userId="me", id=mid, format="full").execute()
        out.append(to_raw(msg))
    log.info("gmail: fetched %d new messages (of %d matching)", len(out), len(ids))
    return out
