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
    # Fraction over/under the median of comparable contracts (0.5 = 50% above).
    # Computed per request from the reference group, not stored.
    stat_deviation: float | None = None
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


class CountryYearCellOut(BaseModel):
    country_code: str
    year: int
    contracts: int
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
    by_country_year: list[CountryYearCellOut] = []


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
    turnstile_token: str | None = Field(default=None, max_length=4096)

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


class BuyerHistoryOut(BaseModel):
    contracts: int
    median_amount: float | None
    currency: str | None
    anomaly_rate: float | None


class OpportunityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    country_code: str
    source: str
    title: str
    description: str | None
    buyer_name: str | None
    region: str | None
    category: str | None
    procurement_method: str | None
    currency: str | None
    estimated_amount: float | None
    published_at: datetime | None
    deadline: datetime
    for_smes: bool | None
    url: str
    buyer_history: BuyerHistoryOut | None = None


class OpportunityPage(BaseModel):
    total: int
    items: list[OpportunityOut]
    counts_by_country: dict[str, int]
    sources: dict[str, str]


class ChannelOut(BaseModel):
    role: str  # procurement | oversight
    name: str
    url: str


_EMAIL = r"^[^@\s]{1,64}@[^@\s]{1,190}\.[A-Za-z]{2,24}$"


class InquiryIn(BaseModel):
    kind: str
    country_code: str = Field(min_length=2, max_length=4)
    process_reference: str | None = Field(default=None, max_length=600)
    institution: str | None = Field(default=None, max_length=300)
    contract_id: str | None = Field(default=None, max_length=36)
    opportunity_id: str | None = Field(default=None, max_length=36)
    subject: str = Field(min_length=5, max_length=200)
    body: str = Field(min_length=20, max_length=5000)
    contact_email: str | None = Field(default=None, max_length=200, pattern=_EMAIL)
    website: str = Field(default="", max_length=200)  # honeypot
    turnstile_token: str | None = Field(default=None, max_length=4096)

    @field_validator("kind")
    @classmethod
    def _valid_kind(cls, v: str) -> str:
        if v not in ("consulta", "reclamo", "alerta"):
            raise ValueError("kind must be consulta, reclamo or alerta")
        return v

    @field_validator("contact_email", "process_reference", "institution", "contract_id", "opportunity_id", mode="before")
    @classmethod
    def _blank_is_none(cls, v):
        return v.strip() or None if isinstance(v, str) else v


class InquiryReceiptOut(BaseModel):
    code: str
    status: str
    channels: list[ChannelOut]


class InquiryStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    kind: str
    country_code: str
    status: str
    response: str | None
    created_at: datetime
    updated_at: datetime
    channels: list[ChannelOut] = []


class AdminInquiryOut(InquiryStatusOut):
    process_reference: str | None
    institution: str | None
    contract_id: str | None
    opportunity_id: str | None
    subject: str
    body: str
    contact_email: str | None


class InquiryUpdateIn(BaseModel):
    status: str
    response: str | None = Field(default=None, max_length=5000)

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        if v not in ("recibido", "en_revision", "derivado", "cerrado"):
            raise ValueError("unknown status")
        return v
