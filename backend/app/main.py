from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from . import models, schemas
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
    allow_methods=["GET"],
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
    limit: int = Query(default=25, le=200),
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


@app.get("/anomalies", response_model=schemas.AnomalyPage)
def list_anomalies(
    db: Session = Depends(get_db),
    country: str | None = Query(default=None),
    anomaly_type: str | None = Query(default=None),
    status: str = Query(default="open"),
    min_score: float | None = Query(default=None),
    limit: int = Query(default=25, le=200),
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
