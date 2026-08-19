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
"""

import json
import urllib.error
import urllib.request

from .config import settings

API_URL = "https://api.bazaarlink.ai/v1/chat/completions"
MODEL = "auto:free"
TIMEOUT_SECONDS = 20
MAX_INPUT_CHARS = 6000

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
    return content or None
