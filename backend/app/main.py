import csv
import io
import time
from datetime import datetime

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from . import ai, analysis, dashboard, models, schemas, tenders, providers
from .config import settings
from .db import get_db

app = FastAPI(
    title="Contractor AI API",
    description=(
        "API pública de solo lectura para detectar anomalías en contrataciones "
        "públicas (Fase 1: Paraguay, dataset histórico). Ver "
        "docs/architecture/PLANNING.md en el repo para el roadmap completo."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    # El proyecto de Vercel puede tener el dominio de producción cambiado
    # (o desplegar previews con subdominios generados) sin que alguien
    # actualice CORS_ALLOW_ORIGINS a mano -- se permite cualquier subdominio
    # *.vercel.app de este proyecto además de la lista explícita, para que
    # este descuido no vuelva a romper el frontend en producción. También se
    # permite localhost/127.0.0.1 en cualquier puerto: `next dev` corre en
    # 3000 por defecto, pero herramientas de preview reasignan el puerto si
    # está ocupado -- exigir que CORS_ALLOW_ORIGINS coincida exacto con el
    # puerto de cada corrida de desarrollo es frágil sin aportar seguridad
    # real (Origin lo fija el navegador, no algo que un sitio remoto pueda
    # falsificar como "localhost").
    allow_origin_regex=r"^(https://contractor-ai(-[a-z0-9]+)*\.vercel\.app|http://(localhost|127\.0\.0\.1):\d+)$",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/countries")
def list_countries(db: Session = Depends(get_db)):
    countries = db.execute(select(models.Country)).scalars().all()
    return [
        {"code": c.code, "name": c.name, "active": c.active}
        for c in countries
    ]


@app.get("/contracts", response_model=schemas.ContractPage)
def list_contracts(
    db: Session = Depends(get_db),
    country: str | None = Query(default=None, description="Código de país, ej. PY"),
    buyer: str | None = Query(default=None, description="Filtra por nombre de comprador (contiene)"),
    category: str | None = Query(default=None),
    min_amount_usd: float | None = Query(default=None),
    max_amount_usd: float | None = Query(default=None),
    only_anomalous: bool = Query(default=False, description="Solo contratos con al menos una anomalía abierta"),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(models.Contract).options(joinedload(models.Contract.buyer))

    if country:
        stmt = stmt.where(models.Contract.country_code == country.upper())
    if category:
        stmt = stmt.where(models.Contract.category_code == category)
    if min_amount_usd is not None:
        stmt = stmt.where(models.Contract.amount_usd >= min_amount_usd)
    if max_amount_usd is not None:
        stmt = stmt.where(models.Contract.amount_usd <= max_amount_usd)
    if buyer:
        stmt = stmt.join(models.Buyer).where(models.Buyer.normalized_name.contains(buyer.lower()))
    if only_anomalous:
        stmt = stmt.join(models.Anomaly).where(models.Anomaly.status == "open")

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    stmt = stmt.order_by(models.Contract.award_date.desc().nullslast()).limit(limit).offset(offset)
    items = db.execute(stmt).unique().scalars().all()

    return schemas.ContractPage(total=total, limit=limit, offset=offset, items=items)


@app.get("/contracts/{contract_id}", response_model=schemas.ContractDetail)
def get_contract(contract_id: str, db: Session = Depends(get_db)):
    stmt = (
        select(models.Contract)
        .options(
            joinedload(models.Contract.buyer),
            joinedload(models.Contract.predictions),
            joinedload(models.Contract.anomalies),
        )
        .where(models.Contract.id == contract_id)
    )
    contract = db.execute(stmt).unique().scalar_one_or_none()
    if contract is None:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")
    return contract


@app.get("/contracts/{contract_id}/reports", response_model=list[schemas.CitizenReportOut])
def list_citizen_reports(contract_id: str, db: Session = Depends(get_db)):
    if db.get(models.Contract, contract_id) is None:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")
    stmt = (
        select(models.CitizenReport)
        .where(models.CitizenReport.contract_id == contract_id, models.CitizenReport.status == "visible")
        .order_by(models.CitizenReport.created_at.desc())
    )
    return db.execute(stmt).scalars().all()


# Best-effort in-memory rate limit shared by every write/expensive endpoint
# below: not a security guarantee (resets on restart, keyed on
# request.client.host which a proxy can obscure), just a soft deterrent
# against a script hammering an endpoint. Real abuse resistance would need a
# shared store (Redis, etc.) and proper proxy IP handling (X-Forwarded-For).
_rate_hits: dict[str, list[float]] = {}


def _rate_limited(request: Request, bucket: str, max_hits: int, window_seconds: int) -> bool:
    client_ip = request.client.host if request.client else "unknown"
    key = f"{bucket}:{client_ip}"
    now = time.time()
    hits = [t for t in _rate_hits.get(key, []) if now - t < window_seconds]
    exceeded = len(hits) >= max_hits
    if not exceeded:
        hits.append(now)
        _rate_hits[key] = hits
    return exceeded


MAX_REPORTS_PER_WINDOW = 5
REPORT_WINDOW_SECONDS = 600


@app.post("/contracts/{contract_id}/reports", response_model=schemas.CitizenReportOut, status_code=201)
def create_citizen_report(
    contract_id: str,
    payload: schemas.CitizenReportIn,
    request: Request,
    db: Session = Depends(get_db),
):
    if db.get(models.Contract, contract_id) is None:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")

    if payload.website:
        # Honeypot field a real user never sees or fills. Respond as if it
        # worked (don't tip off the bot) but never persist anything.
        return schemas.CitizenReportOut(
            id="0", comment=payload.comment, stance=payload.stance, created_at=datetime.utcnow()
        )

    if _rate_limited(request, "reports", MAX_REPORTS_PER_WINDOW, REPORT_WINDOW_SECONDS):
        raise HTTPException(status_code=429, detail="Demasiados reportes. Probá de nuevo en unos minutos.")

    report = models.CitizenReport(contract_id=contract_id, comment=payload.comment.strip(), stance=payload.stance)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@app.get("/anomalies", response_model=schemas.AnomalyPage)
def list_anomalies(
    db: Session = Depends(get_db),
    country: str | None = Query(default=None),
    anomaly_type: str | None = Query(default=None),
    status: str = Query(default="open"),
    min_score: float | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = (
        select(models.Anomaly)
        .join(models.Contract)
        .options(joinedload(models.Anomaly.contract).joinedload(models.Contract.buyer))
    )

    if status:
        stmt = stmt.where(models.Anomaly.status == status)
    if anomaly_type:
        stmt = stmt.where(models.Anomaly.anomaly_type == anomaly_type)
    if min_score is not None:
        stmt = stmt.where(models.Anomaly.composite_score >= min_score)
    if country:
        stmt = stmt.where(models.Contract.country_code == country.upper())

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    stmt = stmt.order_by(models.Anomaly.composite_score.desc().nullslast()).limit(limit).offset(offset)
    items = db.execute(stmt).unique().scalars().all()

    return schemas.AnomalyPage(total=total, limit=limit, offset=offset, items=items)


@app.get("/dashboard/summary", response_model=schemas.DashboardSummaryOut)
def dashboard_summary(
    db: Session = Depends(get_db),
    country: str | None = Query(default=None, description="Código de país, ej. PY. Si se omite, agrega los 4 países."),
):
    result = dashboard.get_summary(db, country.upper() if country else None)
    return schemas.DashboardSummaryOut(
        country_code=result.country_code,
        total_contracts=result.total_contracts,
        total_amount_usd=result.total_amount_usd,
        total_anomalies=result.total_anomalies,
        anomaly_rate=result.anomaly_rate,
        by_year=[schemas.YearPointOut(**vars(p)) for p in result.by_year],
        by_category=[schemas.CategoryBreakdownOut(**vars(c)) for c in result.by_category],
        by_country=[schemas.CountryBreakdownOut(**vars(c)) for c in result.by_country],
    )


@app.get("/rankings/buyers", response_model=schemas.BuyerRankingList)
def rankings_buyers(
    db: Session = Depends(get_db),
    country: str | None = Query(default=None, description="Código de país, ej. PY. Si se omite, agrega los 4 países."),
    limit: int = Query(default=20, ge=1, le=100),
):
    items = dashboard.get_best_buyers(db, country.upper() if country else None, limit)
    return schemas.BuyerRankingList(
        min_contracts=dashboard.MIN_BUYER_CONTRACTS,
        items=[schemas.BuyerRankingOut(**vars(r)) for r in items],
    )


# Provider Favoritism & Market Concentration

@app.get("/providers/stats", response_model=schemas.ProviderStatsOut)
def provider_stats(
    db: Session = Depends(get_db),
    country: str | None = Query(default=None, description="Código de país, ej. PY"),
):
    result = providers.get_provider_stats(db, country.upper() if country else None)
    return schemas.ProviderStatsOut(**vars(result))


@app.get("/providers/top", response_model=list[schemas.ProviderDetailOut])
def top_providers(
    db: Session = Depends(get_db),
    country: str | None = Query(default=None, description="Código de país, ej. PY"),
    limit: int = Query(default=20, ge=1, le=100),
):
    items = providers.get_top_providers(db, country.upper() if country else None, limit)
    return [schemas.ProviderDetailOut(**vars(r)) for r in items]


@app.get("/providers/price-favoritism", response_model=list[schemas.PriceFavoritismPointOut])
def price_favoritism(
    db: Session = Depends(get_db),
    country: str | None = Query(default=None, description="Código de país, ej. PY"),
    start_year: int = Query(default=2023, ge=2000, le=2100),
    end_year: int = Query(default=2025, ge=2000, le=2100),
):
    items = providers.get_price_favoritism_trends(db, country.upper() if country else None, start_year, end_year)
    return [schemas.PriceFavoritismPointOut(**vars(r)) for r in items]


@app.get("/providers/geographic", response_model=list[schemas.GeographicPatternOut])
def geographic_favoritism(db: Session = Depends(get_db)):
    items = providers.get_geographic_favoritism(db)
    return [schemas.GeographicPatternOut(**vars(r)) for r in items]


@app.get("/providers/temporal-patterns", response_model=list[schemas.TemporalClusterOut])
def temporal_patterns(
    db: Session = Depends(get_db),
    country: str | None = Query(default=None, description="Código de país, ej. PY"),
):
    items = providers.get_temporal_patterns(db, country.upper() if country else None)
    return [schemas.TemporalClusterOut(**vars(r)) for r in items]


@app.get("/tenders/portals", response_model=list[schemas.TenderPortalOut])
def tenders_portals(db: Session = Depends(get_db)):
    countries = {c.code: c.name for c in db.execute(select(models.Country)).scalars().all()}
    return [
        schemas.TenderPortalOut(
            country_code=code,
            country_name=countries.get(code, code),
            portal_name=portal["name"],
            portal_url=portal["url"],
        )
        for code, portal in tenders.OFFICIAL_PORTALS.items()
    ]


@app.get("/tenders/categories", response_model=list[schemas.TenderCategoryOut])
def tenders_categories(country: str, db: Session = Depends(get_db)):
    items = tenders.get_categories(db, country.upper())
    return [schemas.TenderCategoryOut(category_code=c.category_code, contracts=c.contracts) for c in items]


@app.get("/tenders/benchmark", response_model=schemas.TenderBenchmarkOut)
def tenders_benchmark(country: str, category: str, db: Session = Depends(get_db)):
    result = tenders.get_price_benchmark(db, country.upper(), category)
    if result is None:
        raise HTTPException(
            status_code=422,
            detail=f"No hay suficientes contratos en {country.upper()}/{category} para armar un benchmark confiable.",
        )
    return schemas.TenderBenchmarkOut(
        country_code=result.country_code,
        category_code=result.category_code,
        currency=result.currency,
        sample_size=result.sample_size,
        median_amount=result.median_amount,
        typical_low=result.typical_low,
        typical_high=result.typical_high,
    )


@app.get("/export/contracts.csv")
def export_contracts_csv(
    db: Session = Depends(get_db),
    country: str | None = Query(default=None),
    category: str | None = Query(default=None),
    only_anomalous: bool = Query(default=False),
    limit: int = Query(default=5000, ge=1, le=20000),
):
    stmt = select(models.Contract).options(joinedload(models.Contract.buyer))
    if country:
        stmt = stmt.where(models.Contract.country_code == country.upper())
    if category:
        stmt = stmt.where(models.Contract.category_code == category)
    if only_anomalous:
        stmt = stmt.join(models.Anomaly).where(models.Anomaly.status == "open")
    stmt = stmt.order_by(models.Contract.award_date.desc().nullslast()).limit(limit)
    rows = db.execute(stmt).unique().scalars().all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "id", "ocid", "country_code", "title", "category_code", "buyer_name",
        "currency", "amount_original", "amount_usd", "award_date", "source_url",
    ])
    for c in rows:
        writer.writerow([
            c.id, c.ocid or "", c.country_code, c.title or "", c.category_code or "",
            c.buyer.name if c.buyer else "", c.currency or "", c.amount_original or "",
            c.amount_usd or "", c.award_date or "", c.source_url or "",
        ])
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=contractor-ai-contracts.csv"},
    )


MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_EXTRACT_PER_WINDOW = 10
MAX_COMPARE_PER_WINDOW = 20
ANALYZE_WINDOW_SECONDS = 300


@app.post("/analyze/extract", response_model=schemas.ExtractionOut)
async def analyze_extract(
    request: Request,
    method: str = Form(..., description="pdf | link"),
    file: UploadFile | None = File(default=None),
    link: str | None = Form(default=None),
):
    if _rate_limited(request, "extract", MAX_EXTRACT_PER_WINDOW, ANALYZE_WINDOW_SECONDS):
        raise HTTPException(status_code=429, detail="Demasiados análisis. Probá de nuevo en unos minutos.")

    if method == "pdf":
        if file is None:
            raise HTTPException(status_code=400, detail="Falta el archivo PDF.")
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="El PDF supera los 15 MB.")
        result = analysis.extract_from_pdf(data)
    elif method == "link":
        if not link:
            raise HTTPException(status_code=400, detail="Falta el link.")
        result = analysis.extract_from_link(link)
    else:
        raise HTTPException(status_code=400, detail="method debe ser pdf o link.")

    return schemas.ExtractionOut(
        ocr_available=result.ocr_available,
        text_excerpt=result.text_excerpt,
        suggested_title=result.suggested_title,
        suggested_amount=result.suggested_amount,
        candidate_amounts=result.candidate_amounts,
        warning=result.warning,
    )


@app.post("/analyze/compare", response_model=schemas.CompareOut)
def analyze_compare(payload: schemas.CompareRequest, request: Request, db: Session = Depends(get_db)):
    if _rate_limited(request, "compare", MAX_COMPARE_PER_WINDOW, ANALYZE_WINDOW_SECONDS):
        raise HTTPException(status_code=429, detail="Demasiadas comparaciones. Probá de nuevo en unos minutos.")
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0.")

    country_code = payload.country.upper()
    country = db.get(models.Country, country_code)
    if country is None:
        raise HTTPException(status_code=400, detail="País no reconocido.")

    result = analysis.compare_amount(
        db,
        country_code=country_code,
        currency=payload.currency.upper(),
        amount=payload.amount,
        category_code=payload.category or None,
        buyer_name=payload.buyer_name or None,
    )
    if result is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"No hay suficientes contratos ingeridos en {country_code} con moneda "
                f"{payload.currency.upper()} para armar una comparación confiable "
                f"(mínimo {analysis.MIN_GROUP_SIZE})."
            ),
        )

    return schemas.CompareOut(
        reference_group=result.reference_group,
        group_size=result.group_size,
        median_amount=result.median_amount,
        submitted_amount=result.submitted_amount,
        deviation_pct=result.deviation_pct,
        zscore=result.zscore,
        zscore_flagged=result.zscore_flagged,
        iqr_flagged=result.iqr_flagged,
        verdict=result.verdict,
        comparables=[
            schemas.ComparableOut(
                id=c.id, title=c.title, buyer_name=c.buyer_name,
                amount_original=c.amount_original, award_date=c.award_date,
            )
            for c in result.comparables
        ],
    )


# BazaarLink's free tier is a *global* allowance shared across every user of
# their service, not a per-key quota -- kept far more conservative than the
# app's other rate limits so this app alone doesn't eat a disproportionate
# share of it.
MAX_NARRATIVE_PER_WINDOW = 3
NARRATIVE_WINDOW_SECONDS = 600


@app.post("/analyze/narrative", response_model=schemas.NarrativeOut)
def analyze_narrative(payload: schemas.NarrativeRequest, request: Request):
    if not ai.is_available():
        return schemas.NarrativeOut(available=False, narrative=None)
    if _rate_limited(request, "narrative", MAX_NARRATIVE_PER_WINDOW, NARRATIVE_WINDOW_SECONDS):
        raise HTTPException(status_code=429, detail="Demasiados resúmenes. Probá de nuevo en unos minutos.")

    narrative = ai.generate_narrative(payload.text, payload.comparison_summary)
    return schemas.NarrativeOut(available=narrative is not None, narrative=narrative)
