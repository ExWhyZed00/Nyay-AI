import httpx
import pytest
from fastapi import HTTPException

import app.auth as auth


class FakeResp:
    def __init__(self, status, payload=None):
        self.status_code, self._p, self.text = status, payload or {}, ""

    def json(self):
        return self._p


def setup_function():
    auth._token_cache.clear()
    auth._hits.clear()


def test_missing_or_bad_header():
    for h in (None, "", "Token abc", "Bearer "):
        with pytest.raises(HTTPException) as e:
            auth.get_current_user(h)
        assert e.value.status_code == 401


def test_valid_token_and_cache(monkeypatch):
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append((url, headers))
        return FakeResp(200, {"id": "11111111-1111-1111-1111-111111111111", "email": "a@b.c"})

    monkeypatch.setattr(auth.httpx, "get", fake_get)
    u = auth.get_current_user("Bearer tok123")
    assert u.id.startswith("1111") and u.email == "a@b.c"
    auth.get_current_user("Bearer tok123")
    assert len(calls) == 1  # second call served from cache
    assert calls[0][0].endswith("/auth/v1/user")
    assert calls[0][1]["Authorization"] == "Bearer tok123" and calls[0][1]["apikey"] == "anon-test"


def test_rejected_token(monkeypatch):
    monkeypatch.setattr(auth.httpx, "get", lambda *a, **k: FakeResp(401))
    with pytest.raises(HTTPException) as e:
        auth.get_current_user("Bearer bad")
    assert e.value.status_code == 401


def test_supabase_down(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("nope")

    monkeypatch.setattr(auth.httpx, "get", boom)
    with pytest.raises(HTTPException) as e:
        auth.get_current_user("Bearer x")
    assert e.value.status_code == 503


def test_rate_limit(monkeypatch):
    monkeypatch.setattr(auth.get_settings(), "rate_limit_requests", 3)
    for _ in range(3):
        auth.check_rate_limit("u1")
    with pytest.raises(HTTPException) as e:
        auth.check_rate_limit("u1")
    assert e.value.status_code == 429
    auth.check_rate_limit("u2")  # other users unaffected
