from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from ..config import get_settings


def require_token(authorization: str = Header(default="")) -> None:
    s = get_settings()
    if authorization != f"Bearer {s.api_token}":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad or missing bearer token")


Auth = Depends(require_token)
