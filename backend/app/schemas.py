from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class PredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_name: str
    model_version: str
    predicted_value_usd: float | None
    range_low: float | None
    range_high: float | None
    likelihood_score: float | None


class AnomalyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    anomaly_type: str
    composite_score: float | None
    nlp_component: float | None
    stat_component: float | None
    confidence: float | None
    status: str


class BuyerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class ContractSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ocid: str | None
    country_code: str
    title: str | None
    category_code: str | None
    currency: str | None
    amount_original: float | None
    amount_usd: float | None
    award_date: date | None
    buyer: BuyerOut | None = None


class ContractDetail(ContractSummary):
    description: str | None
    procurement_method: str | None
    source_url: str | None
    ingested_at: datetime
    predictions: list[PredictionOut] = []
    anomalies: list[AnomalyOut] = []


class Page(BaseModel):
    total: int
    limit: int
    offset: int


class ContractPage(Page):
    items: list[ContractSummary]


class AnomalyWithContract(AnomalyOut):
    contract: ContractSummary


class AnomalyPage(Page):
    items: list[AnomalyWithContract]
