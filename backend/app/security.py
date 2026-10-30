"""Abuse protection shared by every endpoint that writes or costs money.

Three layers, cheapest first:

1. A honeypot field in each form (handled by the endpoint): bots fill it,
   people never see it.
2. Per-client rate limits (`rate_limited`), keyed on the real client IP.
3. Cloudflare Turnstile (`verify_turnstile`): a privacy-preserving challenge,
   no puzzle to solve for most people. Only enforced when
   TURNSTILE_SECRET_KEY is set, so local development and the test suite work
   without a Cloudflare account; production sets it (docs/security/cloudflare.md).

The rate limit lives in process memory: it resets on restart and isn't
shared between instances. That is enough for one free Render instance; a
WAF rate-limiting rule at Cloudflare is the layer that stops a real flood
before it reaches the API.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.parse
import urllib.request

from fastapi import Request

from .config import settings

log = logging.getLogger(__name__)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

_rate_hits: dict[str, list[float]] = {}


def client_ip(request: Request) -> str:
    """The address of whoever is actually calling.

    Behind Render's proxy `request.client.host` is the proxy itself, so every
    visitor would share one rate-limit bucket (and one abuser would lock
    everyone out). Cloudflare, when it fronts the site, sends the original
    client in CF-Connecting-IP; otherwise Render appends it as the LAST hop
    of X-Forwarded-For. The leftmost entries are whatever the client chose
    to send, so they are never trusted.
    """
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def rate_limited(request: Request, bucket: str, max_hits: int, window_seconds: int) -> bool:
    key = f"{bucket}:{client_ip(request)}"
    now = time.time()
    hits = [t for t in _rate_hits.get(key, []) if now - t < window_seconds]
    exceeded = len(hits) >= max_hits
    if not exceeded:
        hits.append(now)
    _rate_hits[key] = hits
    if len(_rate_hits) > 50_000:  # keep a flood of distinct IPs from growing memory forever
        _rate_hits.clear()
    return exceeded


def reset_rate_limits() -> None:
    _rate_hits.clear()


def verify_turnstile(token: str | None, request: Request) -> bool:
    """True when Turnstile is off, or Cloudflare confirms the token."""
    secret = settings.turnstile_secret_key
    if not secret:
        return True
    if not token:
        return False
    data = urllib.parse.urlencode({"secret": secret, "response": token, "remoteip": client_ip(request)}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(TURNSTILE_VERIFY_URL, data=data), timeout=8) as resp:
            return bool(json.load(resp).get("success"))
    except Exception as exc:  # noqa: BLE001
        # Cloudflare unreachable: fail closed. A form that can't be verified
        # is the abuse case this layer exists for.
        log.warning("turnstile verification failed: %s", exc)
        return False


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    # The API only ever returns JSON or CSV; nothing it serves should run.
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    for name, value in SECURITY_HEADERS.items():
        # /docs and /redoc are HTML pages that load Swagger's own scripts.
        if name == "Content-Security-Policy" and path in ("/docs", "/redoc", "/docs/oauth2-redirect"):
            continue
        response.headers.setdefault(name, value)
    return response
