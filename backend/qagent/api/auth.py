"""
Simple shared-account auth: one email/password from config, a signed session token in an HttpOnly cookie.
The cookie (not a header) is deliberate: EventSource streams and <img> tags cannot set headers but do send cookies.
A `Authorization: Bearer <token>` header is accepted too, for scripts.
"""
import base64
import hashlib
import hmac
import json
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from qagent.config import settings

COOKIE = "qagent_session"
router = APIRouter(prefix="/auth", tags=["Auth"])

_failures: Dict[str, Deque[float]] = defaultdict(deque)
MAX_FAILURES, WINDOW_S = 5, 60


def _sign(payload: str) -> str:
    return hmac.new(settings.auth_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def make_token(email: str, ttl_s: Optional[int] = None) -> str:
    body = base64.urlsafe_b64encode(json.dumps({"sub": email, "exp": int(time.time()) + (ttl_s or settings.auth_ttl_hours * 3600)}).encode()).decode()
    return f"{body}.{_sign(body)}"


def read_token(token: Optional[str]) -> Optional[str]:
    """The email in a valid, unexpired token; otherwise None."""
    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(body)):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(body.encode()))
    except ValueError:
        return None
    return data["sub"] if data.get("exp", 0) > time.time() else None


def require_user(request: Request) -> str:
    """Dependency for every protected route."""
    token = request.cookies.get(COOKIE)
    if not token and request.headers.get("authorization", "").lower().startswith("bearer "):
        token = request.headers["authorization"][7:]
    email = read_token(token)
    if email is None:
        raise HTTPException(status_code=401, detail="Sign in to continue")
    return email


class LoginRequest(BaseModel):
    email: str
    password: str


class SessionResponse(BaseModel):
    email: str


def _throttled(key: str) -> bool:
    q = _failures[key]
    while q and q[0] < time.time() - WINDOW_S:
        q.popleft()
    return len(q) >= MAX_FAILURES


@router.post("/login", response_model=SessionResponse)
async def login(payload: LoginRequest, request: Request, response: Response):
    key = request.client.host if request.client else "unknown"
    if _throttled(key):
        raise HTTPException(status_code=429, detail="Too many attempts. Wait a minute and try again.")
    ok_email = hmac.compare_digest(payload.email.strip().lower().encode(), settings.auth_email.lower().encode())
    ok_pw = hmac.compare_digest(payload.password.encode(), settings.auth_password.encode())
    if not (ok_email and ok_pw):
        _failures[key].append(time.time())
        raise HTTPException(status_code=401, detail="Email or password is not correct")
    _failures.pop(key, None)
    response.set_cookie(COOKIE, make_token(settings.auth_email), httponly=True, samesite=settings.auth_cookie_samesite,
                        secure=settings.auth_cookie_secure, max_age=settings.auth_ttl_hours * 3600, path="/")
    return SessionResponse(email=settings.auth_email)


@router.post("/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")


@router.get("/me", response_model=SessionResponse)
async def me(email: str = Depends(require_user)):
    return SessionResponse(email=email)
