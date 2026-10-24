"""Login check + simple per-user rate limit.

The browser logs in with Supabase and receives an access token (JWT). It sends the
token to us as `Authorization: Bearer <token>`. We ask Supabase "who owns this token?".
This works with every Supabase signing-key setup, so there is no secret to configure.
"""
import logging
import time
from collections import defaultdict, deque

import httpx
from fastapi import Header, HTTPException
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)

_TOKEN_TTL_SECONDS = 60
_token_cache: dict[str, tuple[float, "CurrentUser"]] = {}
_hits: dict[str, deque] = defaultdict(deque)


class CurrentUser(BaseModel):
    id: str
    email: str | None = None


def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Please log in.")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Please log in.")

    now = time.time()
    cached = _token_cache.get(token)
    if cached and cached[0] > now:
        return cached[1]

    s = get_settings()
    try:
        resp = httpx.get(
            f"{s.supabase_url}/auth/v1/user",
            headers={"Authorization": f"Bearer {token}", "apikey": s.supabase_anon_key},
            timeout=10.0,
        )
    except httpx.HTTPError:
        logger.exception("Could not reach Supabase Auth")
        raise HTTPException(status_code=503, detail="Login service unreachable. Try again.")

    if resp.status_code in (401, 403):
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    if resp.status_code != 200:
        logger.error("Supabase Auth returned %s: %s", resp.status_code, resp.text[:200])
        raise HTTPException(status_code=503, detail="Login service error. Try again.")

    data = resp.json()
    user = CurrentUser(id=data["id"], email=data.get("email"))
    if len(_token_cache) > 1000:
        _token_cache.clear()
    _token_cache[token] = (now + _TOKEN_TTL_SECONDS, user)
    return user


def check_rate_limit(user_id: str) -> None:
    """Allow N chat requests per window per user (in-memory, resets on restart)."""
    s = get_settings()
    now = time.time()
    q = _hits[user_id]
    while q and q[0] <= now - s.rate_limit_window_seconds:
        q.popleft()
    if len(q) >= s.rate_limit_requests:
        raise HTTPException(
            status_code=429,
            detail="Too many questions in a short time. Please wait a few minutes.",
        )
    q.append(now)
