import uuid
from datetime import datetime, date

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Country(Base):
    __tablename__ = "countries"

    code: Mapped[str] = mapped_column(String(4), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    ocds_portal_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    schema_variant: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ingestion_method: Mapped[str] = mapped_column(String(20), default="manual")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    country_code: Mapped[str] = mapped_column(ForeignKey("countries.code"))
    source_type: Mapped[str] = mapped_column(String(30))  # ocds_api | scraper | manual_upload
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    terms_of_use_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_ingested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Buyer(Base):
    __tablename__ = "buyers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    country_code: Mapped[str] = mapped_column(ForeignKey("countries.code"))
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name: Mapped[str] = mapped_column(String(500))
    normalized_name: Mapped[str] = mapped_column(String(500), index=True)

    contracts: Mapped[list["Contract"]] = relationship(back_populates="buyer")


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    ocid: Mapped[str | None] = mapped_column(String(200), index=True, nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(200), index=True, nullable=True)
    country_code: Mapped[str] = mapped_column(ForeignKey("countries.code"), index=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("data_sources.id"), nullable=True)
    buyer_id: Mapped[str | None] = mapped_column(ForeignKey("buyers.id"), nullable=True)

    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_code: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(6), nullable=True)
    amount_original: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount_usd: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    award_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    procurement_method: Mapped[str | None] = mapped_column(String(200), nullable=True)
    raw_ocds_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    buyer: Mapped[Buyer | None] = relationship(back_populates="contracts")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="contract")
    statistical_flags: Mapped[list["StatisticalFlag"]] = relationship(back_populates="contract")
    anomalies: Mapped[list["Anomaly"]] = relationship(back_populates="contract")
    documents: Mapped[list["ContractDocument"]] = relationship(back_populates="contract")
    citizen_reports: Mapped[list["CitizenReport"]] = relationship(back_populates="contract")


class ContractDocument(Base):
    __tablename__ = "contract_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"))
    doc_type: Mapped[str] = mapped_column(String(20))  # pdf | photo | link
    storage_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ocr_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    contract: Mapped[Contract] = relationship(back_populates="documents")


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"), index=True)
    model_name: Mapped[str] = mapped_column(String(100))
    model_version: Mapped[str] = mapped_column(String(50))
    predicted_value_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Valor predicho en la moneda original del contrato (contracts.currency), sin
    # convertir. Se usa cuando no hay una tasa de cambio verificable por fecha de
    # contrato para ese país (ver backend/scripts/migrate_colombia.py) — el score
    # de anomalía se calcula como ratio real/predicho, que no depende de la moneda.
    predicted_value_original: Mapped[float | None] = mapped_column(Float, nullable=True)
    range_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    range_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    likelihood_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    contract: Mapped[Contract] = relationship(back_populates="predictions")


class StatisticalFlag(Base):
    __tablename__ = "statistical_flags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"), index=True)
    method: Mapped[str] = mapped_column(String(30))  # iqr | zscore | regression
    reference_group: Mapped[str | None] = mapped_column(String(300), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    contract: Mapped[Contract] = relationship(back_populates="statistical_flags")


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"), index=True)
    anomaly_type: Mapped[str] = mapped_column(String(20))  # overcost | undercost | process | other
    composite_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    nlp_component: Mapped[float | None] = mapped_column(Float, nullable=True)
    stat_component: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | reviewed | dismissed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    contract: Mapped[Contract] = relationship(back_populates="anomalies")


class CitizenReport(Base):
    """A public, unauthenticated comment from a citizen on a specific contract --
    either flagging a concern or adding corroborating/disputing context. This is
    intentionally separate from the model/statistical Anomaly pipeline: it's a
    human signal, not a computed one."""

    __tablename__ = "citizen_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"), index=True)
    comment: Mapped[str] = mapped_column(Text)
    stance: Mapped[str] = mapped_column(String(20), default="flag")  # flag | context
    status: Mapped[str] = mapped_column(String(20), default="visible")  # visible | hidden
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    contract: Mapped[Contract] = relationship(back_populates="citizen_reports")


class Provenance(Base):
    __tablename__ = "provenance"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("data_sources.id"), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_payload_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    country_code: Mapped[str] = mapped_column(ForeignKey("countries.code"))
    source_id: Mapped[str | None] = mapped_column(ForeignKey("data_sources.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    records_ingested: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="running")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_email: Mapped[str] = mapped_column(String(200))
    key_hash: Mapped[str] = mapped_column(String(200), unique=True)
    tier: Mapped[str] = mapped_column(String(30), default="free")
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=60)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
