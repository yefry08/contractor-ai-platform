"""Support code for POST /analyze/* -- lets a visitor submit a contract that
isn't in the ingested dataset and see how its amount compares to similar
already-ingested contracts.

Two capabilities kept deliberately separate, and deliberately honest about
what this environment can and can't do:

1. Text extraction (`extract_from_pdf`, `extract_from_link`) is best-effort
   only: native-PDF text via pypdf, or a raw HTML-stripped fetch for a
   pasted link. Neither does OCR -- Tesseract isn't installed here, so
   scanned PDFs and photos return no extracted text. The API says so
   explicitly (`ocr_available: False`) instead of silently returning
   nothing and letting the caller assume it tried harder than it did.
   Whatever text comes back is only ever a *suggestion* the caller must
   confirm -- this module never sends extracted numbers straight into the
   comparison without the user seeing them first.

2. Comparison (`compare_amount`) reuses the exact same modified z-score /
   IQR formulas as scripts/compute_statistical_anomalies.py (see app/stats.py)
   against contracts already in the database. There is no live BERT/XGBoost
   inference in this environment -- no trained weights, no feature
   pipeline -- so this deliberately does not claim an ML "confidence
   score". It's the same transparent statistical method used everywhere
   else in this app, applied on the fly to one extra data point instead of
   during batch ingestion.
"""

import io
import ipaddress
import math
import re
import socket
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .stats import IQR_MULTIPLIER, MIN_GROUP_SIZE, ZSCORE_THRESHOLD, compute_group_stats, modified_zscore

MAX_FETCH_BYTES = 3_000_000
FETCH_TIMEOUT_SECONDS = 10

_AMOUNT_RE = re.compile(r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?|\d{4,}")


class _TextExtractor(HTMLParser):
    """Strips tags, keeps a rough reading-order text dump. Not a renderer --
    good enough to feed the same regex heuristics used for PDFs."""

    def __init__(self):
        super().__init__()
        self._skip = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.chunks.append(data.strip())


@dataclass
class ExtractionResult:
    ocr_available: bool
    text_excerpt: str = ""
    suggested_title: str | None = None
    suggested_amount: float | None = None
    warning: str | None = None
    candidate_amounts: list[float] = field(default_factory=list)


def _pick_title(lines: list[str]) -> str | None:
    for line in lines:
        cleaned = line.strip()
        if len(cleaned) >= 8:
            return cleaned[:300]
    return None


def _amount_candidates(text: str) -> list[float]:
    out = []
    for raw in _AMOUNT_RE.findall(text):
        normalized = raw
        if "," in normalized and "." in normalized:
            # Whichever separator appears last is the decimal separator.
            if normalized.rfind(",") > normalized.rfind("."):
                normalized = normalized.replace(".", "").replace(",", ".")
            else:
                normalized = normalized.replace(",", "")
        elif "," in normalized:
            # Ambiguous (1,234 could be thousands or a decimal comma) --
            # treat a single group of exactly 3 digits after the comma as
            # thousands, matching how PYG/COP/CRC/DOP amounts are usually
            # written in these portals.
            normalized = normalized.replace(",", "")
        try:
            value = float(normalized)
        except ValueError:
            continue
        if value >= 1000:
            out.append(value)
    # Largest first: the contract amount is usually the biggest number
    # on the page/document, ahead of dates, IDs, phone numbers, etc.
    return sorted(set(out), reverse=True)[:8]


def extract_from_pdf(data: bytes) -> ExtractionResult:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ExtractionResult(ocr_available=False, warning="pypdf no está instalado en el servidor.")

    try:
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:15])
    except Exception as exc:  # noqa: BLE001
        return ExtractionResult(
            ocr_available=False,
            warning=f"No se pudo leer el PDF ({exc.__class__.__name__}). Completá los datos manualmente.",
        )

    text = text.strip()
    if not text:
        return ExtractionResult(
            ocr_available=False,
            warning=(
                "El PDF no tiene texto extraíble -- probablemente es un escaneo/imagen. "
                "Este entorno no tiene OCR instalado (Tesseract no está disponible), así "
                "que no podemos leerlo automáticamente. Completá los datos manualmente."
            ),
        )

    lines = [l for l in text.splitlines() if l.strip()]
    candidates = _amount_candidates(text)
    return ExtractionResult(
        ocr_available=True,
        text_excerpt=text[:4000],
        suggested_title=_pick_title(lines),
        suggested_amount=candidates[0] if candidates else None,
        candidate_amounts=candidates,
    )


def _is_safe_public_url(url: str) -> str | None:
    """Returns an error message if the URL isn't safe to fetch server-side,
    None if it's fine. Blocks non-http(s) schemes and anything resolving to
    a private/loopback/link-local address (SSRF guard) -- this endpoint
    takes an arbitrary URL from the public internet."""

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "Solo se admiten links http:// o https://."
    if not parsed.hostname:
        return "URL inválida."
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        return "No se pudo resolver ese dominio."
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return "Ese link apunta a una dirección de red no pública."
    return None


def extract_from_link(url: str) -> ExtractionResult:
    unsafe_reason = _is_safe_public_url(url)
    if unsafe_reason:
        return ExtractionResult(ocr_available=False, warning=unsafe_reason)

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as resp:
            raw = resp.read(MAX_FETCH_BYTES)
            content_type = resp.headers.get("Content-Type", "")
    except Exception as exc:  # noqa: BLE001
        return ExtractionResult(
            ocr_available=False,
            warning=f"No se pudo obtener esa página ({exc.__class__.__name__}). Completá los datos manualmente.",
        )

    try:
        html = raw.decode("utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        html = ""

    if "text/html" in content_type or "<html" in html.lower():
        parser = _TextExtractor()
        parser.feed(html)
        text = "\n".join(parser.chunks)
    elif "application/pdf" in content_type:
        return extract_from_pdf(raw)
    else:
        text = html

    text = text.strip()
    if not text:
        return ExtractionResult(
            ocr_available=False,
            warning="La página no devolvió texto legible. Completá los datos manualmente.",
        )

    lines = [l for l in text.splitlines() if l.strip()]
    candidates = _amount_candidates(text)
    return ExtractionResult(
        ocr_available=True,
        text_excerpt=text[:4000],
        suggested_title=_pick_title(lines),
        suggested_amount=candidates[0] if candidates else None,
        candidate_amounts=candidates,
    )


@dataclass
class ComparableContract:
    id: str
    title: str | None
    buyer_name: str | None
    amount_original: float
    award_date: str | None


@dataclass
class ComparisonResult:
    reference_group: str
    group_size: int
    median_amount: float
    submitted_amount: float
    deviation_pct: float
    zscore: float
    zscore_flagged: bool
    iqr_flagged: bool
    verdict: str
    comparables: list[ComparableContract]


def compare_amount(
    db: Session,
    country_code: str,
    currency: str,
    amount: float,
    category_code: str | None,
    buyer_name: str | None,
) -> ComparisonResult | None:
    """Returns None if there isn't enough same-country/same-currency data to
    form any reference group at all."""

    base_stmt = (
        select(models.Contract)
        .where(models.Contract.country_code == country_code)
        .where(models.Contract.currency == currency)
        .where(models.Contract.amount_original.isnot(None))
        .where(models.Contract.amount_original > 0)
    )

    normalized_buyer = (buyer_name or "").strip().lower()
    group_stmt = base_stmt
    reference_group = f"{country_code}:country"

    if normalized_buyer:
        buyer_stmt = base_stmt.join(models.Buyer).where(models.Buyer.normalized_name == normalized_buyer)
        buyer_rows = db.execute(buyer_stmt).unique().scalars().all()
        if len(buyer_rows) >= MIN_GROUP_SIZE:
            group_stmt = buyer_stmt
            reference_group = f"{country_code}:comprador"

    if reference_group == f"{country_code}:country" and category_code:
        category_stmt = base_stmt.where(models.Contract.category_code == category_code)
        category_rows = db.execute(category_stmt).unique().scalars().all()
        if len(category_rows) >= MIN_GROUP_SIZE:
            group_stmt = category_stmt
            reference_group = f"{country_code}:categoría"

    rows = db.execute(group_stmt).unique().scalars().all()
    if len(rows) < MIN_GROUP_SIZE:
        rows = db.execute(base_stmt).unique().scalars().all()
        reference_group = f"{country_code}:country"
        if len(rows) < MIN_GROUP_SIZE:
            return None

    log_amounts = [math.log(r.amount_original) for r in rows]
    group_stats = compute_group_stats(log_amounts)

    log_submitted = math.log(amount)
    z = modified_zscore(log_submitted, group_stats["median"], group_stats["mad"])
    zscore_flagged = abs(z) > ZSCORE_THRESHOLD

    iqr = group_stats["iqr"]
    lower_fence = group_stats["q1"] - IQR_MULTIPLIER * iqr
    upper_fence = group_stats["q3"] + IQR_MULTIPLIER * iqr
    iqr_flagged = bool(iqr > 0 and (log_submitted < lower_fence or log_submitted > upper_fence))

    median_amount = math.exp(group_stats["median"])
    deviation_pct = (amount - median_amount) / median_amount * 100 if median_amount else 0.0

    if zscore_flagged and abs(z) > 5:
        verdict = "alta"
    elif zscore_flagged or iqr_flagged:
        verdict = "revisar"
    else:
        verdict = "normal"

    sorted_rows = sorted(rows, key=lambda r: abs(math.log(r.amount_original) - log_submitted))[:5]
    comparables = [
        ComparableContract(
            id=r.id,
            title=r.title,
            buyer_name=r.buyer.name if r.buyer else None,
            amount_original=r.amount_original,
            award_date=r.award_date.isoformat() if r.award_date else None,
        )
        for r in sorted_rows
    ]

    return ComparisonResult(
        reference_group=reference_group,
        group_size=len(rows),
        median_amount=median_amount,
        submitted_amount=amount,
        deviation_pct=deviation_pct,
        zscore=z,
        zscore_flagged=zscore_flagged,
        iqr_flagged=iqr_flagged,
        verdict=verdict,
        comparables=comparables,
    )
