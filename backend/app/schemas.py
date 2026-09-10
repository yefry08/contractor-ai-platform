from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_name: str
    model_version: str
    predicted_value_usd: float | None
    predicted_value_original: float | None
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
    source_url: str | None = None
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


class ExtractionOut(BaseModel):
    ocr_available: bool
    text_excerpt: str = ""
    suggested_title: str | None = None
    suggested_amount: float | None = None
    candidate_amounts: list[float] = []
    warning: str | None = None


class CompareRequest(BaseModel):
    country: str
    currency: str
    amount: float
    category: str | None = None
    buyer_name: str | None = None


class ComparableOut(BaseModel):
    id: str
    title: str | None
    buyer_name: str | None
    amount_original: float
    award_date: str | None


class CompareOut(BaseModel):
    reference_group: str
    group_size: int
    median_amount: float
    submitted_amount: float
    deviation_pct: float
    zscore: float
    zscore_flagged: bool
    iqr_flagged: bool
    verdict: str
    comparables: list[ComparableOut]


class NarrativeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    comparison_summary: str = Field(min_length=1, max_length=2000)


class NarrativeOut(BaseModel):
    available: bool
    narrative: str | None = None


class YearPointOut(BaseModel):
    year: int
    contracts: int
    total_amount_usd: float
    anomalies: int


class CategoryBreakdownOut(BaseModel):
    category_code: str
    contracts: int
    total_amount_usd: float
    anomalies: int


class CountryBreakdownOut(BaseModel):
    country_code: str
    contracts: int
    total_amount_usd: float
    anomalies: int
    anomaly_rate: float


class DashboardSummaryOut(BaseModel):
    country_code: str | None
    total_contracts: int
    total_amount_usd: float
    total_anomalies: int
    anomaly_rate: float
    by_year: list[YearPointOut]
    by_category: list[CategoryBreakdownOut]
    by_country: list[CountryBreakdownOut]


class BuyerRankingOut(BaseModel):
    buyer_id: str
    name: str
    country_code: str
    total_contracts: int
    total_amount_usd: float
    anomalies: int
    anomaly_rate: float


class BuyerRankingList(BaseModel):
    min_contracts: int
    items: list[BuyerRankingOut]


class CitizenReportIn(BaseModel):
    comment: str = Field(min_length=5, max_length=1000)
    stance: str = "flag"
    website: str = Field(default="", max_length=200)  # honeypot -- real users leave this blank

    @field_validator("stance")
    @classmethod
    def _valid_stance(cls, v: str) -> str:
        return v if v in ("flag", "context") else "flag"


class CitizenReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    comment: str
    stance: str
    created_at: datetime


class TenderPortalOut(BaseModel):
    country_code: str
    country_name: str
    portal_name: str
    portal_url: str


class TenderCategoryOut(BaseModel):
    category_code: str
    contracts: int


class TenderBenchmarkOut(BaseModel):
    country_code: str
    category_code: str
    currency: str | None
    sample_size: int
    median_amount: float
    typical_low: float
    typical_high: float


# Provider Favoritism & Market Concentration

class ProviderStatsOut(BaseModel):
    total_providers: int
    total_contracts: int
    total_spending_usd: float
    hhi_concentration: float
    top_10_share: float


class ProviderDetailOut(BaseModel):
    provider_name: str
    country_code: str
    total_contracts: int
    total_spending_usd: float
    market_share: float
    spending_share: float
    avg_contract_value_usd: float
    anomaly_rate: float
    repeat_buyer_count: int


class PriceFavoritismPointOut(BaseModel):
    provider_name: str
    year: int
    avg_contract_value_usd: float
    market_baseline_usd: float
    markup_percent: float


class GeographicPatternOut(BaseModel):
    provider_name: str
    country_code: str
    contracts: int
    total_spending_usd: float
    market_share_in_country: float


class TemporalClusterOut(BaseModel):
    provider_name: str
    award_date: date
    buyer_name: str
    contract_amount_usd: float
    consecutive_awards: int
