"""Optional, best-effort LLM narrative generation via BazaarLink
(bazaarlink.ai), an OpenAI-compatible AI gateway -- see ADR 0002 for why an
aggregator is used instead of a single vendor, and why this is scoped to
narrative/summary text only, never the anomaly score itself (see ADR 0003:
the LLM is never the source of truth for whether something is flagged).

Verified live against the real API (not assumed from docs): the free model
("auto:free", which currently resolves to qwen/qwen3.7-flash) is text-only
-- no vision/image support, so this cannot do OCR on a photo. It's also a
*global* free-tier allowance shared across every BazaarLink user, not a
per-key quota, which is why the caller rate-limits this far more
conservatively than the app's other endpoints (see main.py) and why this
is opt-in (a button the user clicks) rather than run automatically on
every analysis.

Degrades to None on any failure -- missing key, timeout, rate limit,
content-policy block, malformed response. A narrative is a nice-to-have
add-on; it must never block, replace, or silently fake the actual
statistical comparison the rest of the app relies on.

Caching: Results cached in Redis (24h TTL) if available. Caching failures
are silent (degrades to no cache); the API call always proceeds.
"""

import hashlib
import json
import urllib.error
import urllib.request

from .config import settings

API_URL = "https://api.bazaarlink.ai/v1/chat/completions"
MODEL = "auto:free"
TIMEOUT_SECONDS = 20
MAX_INPUT_CHARS = 6000
CACHE_TTL_SECONDS = 86400  # 24 hours

# Redis connection pool (lazy-loaded)
_redis_client = None


def _get_redis_client():
    """Lazy-load Redis client. Returns None if unavailable."""
    global _redis_client
    if _redis_client is not None or settings.redis_url is None:
        return _redis_client

    try:
        import redis
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)
        _redis_client.ping()  # Test connection
        return _redis_client
    except Exception:  # noqa: BLE001
        return None


def _cache_key(contract_text: str, comparison_summary: str) -> str:
    """Generate cache key from inputs."""
    combined = f"{contract_text[:2000]}|{comparison_summary}"
    return f"narrative:{hashlib.sha256(combined.encode()).hexdigest()}"


def _get_cached_narrative(contract_text: str, comparison_summary: str) -> str | None:
    """Attempt to retrieve cached narrative."""
    try:
        client = _get_redis_client()
        if not client:
            return None
        key = _cache_key(contract_text, comparison_summary)
        return client.get(key)
    except Exception:  # noqa: BLE001
        return None


def _set_cached_narrative(contract_text: str, comparison_summary: str, narrative: str) -> None:
    """Attempt to cache narrative."""
    try:
        client = _get_redis_client()
        if not client:
            return
        key = _cache_key(contract_text, comparison_summary)
        client.setex(key, CACHE_TTL_SECONDS, narrative)
    except Exception:  # noqa: BLE001
        pass  # Silent failure - caching is best-effort

_SYSTEM_PROMPT = (
    "Sos un asistente que resume contratos de compra pública para periodistas y "
    "ciudadanos, en español, en un párrafo breve (máximo 80 palabras). Nunca "
    "acuses de corrupción ni afirmes ilegalidad -- describí objetivamente el "
    "objeto del contrato y, si es relevante, mencioná el resultado de la "
    "comparación estadística que te pasan, sin exagerarlo ni sacar conclusiones "
    "que el dato no respalda."
)


def is_available() -> bool:
    return bool(settings.bazaarlink_api_key)


def generate_narrative(contract_text: str, comparison_summary: str) -> str | None:
    if not settings.bazaarlink_api_key:
        return None

    # Try cache first
    cached = _get_cached_narrative(contract_text, comparison_summary)
    if cached:
        return cached

    user_content = (
        f"Texto del contrato (puede estar truncado):\n{contract_text[:MAX_INPUT_CHARS]}\n\n"
        f"Resultado de la comparación estadística:\n{comparison_summary}"
    )
    body = json.dumps(
        {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": 220,
        }
    ).encode()

    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {settings.bazaarlink_api_key}",
            "Content-Type": "application/json",
            # Cloudflare (in front of api.bazaarlink.ai) returns a 403 "error
            # code: 1010" for urllib's default User-Agent -- same finding as
            # dgcp.gob.do and peacejam.org elsewhere in this codebase, not a
            # hard bot challenge, just a UA string it has listed as
            # suspicious by default.
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            ),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            payload = json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    content = (content or "").strip()
    if content:
        _set_cached_narrative(contract_text, comparison_summary, content)
    return content or None
