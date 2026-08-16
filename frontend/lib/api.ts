const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type Buyer = { id: string; name: string };

export type ContractSummary = {
  id: string;
  ocid: string | null;
  country_code: string;
  title: string | null;
  category_code: string | null;
  currency: string | null;
  amount_original: number | null;
  amount_usd: number | null;
  award_date: string | null;
  buyer: Buyer | null;
};

export type Prediction = {
  model_name: string;
  model_version: string;
  predicted_value_usd: number | null;
  predicted_value_original: number | null;
  range_low: number | null;
  range_high: number | null;
  likelihood_score: number | null;
};

export type Country = { code: string; name: string; active: boolean };

export function listCountries(): Promise<Country[]> {
  return apiFetch<Country[]>("/countries");
}

export type Anomaly = {
  id: string;
  anomaly_type: string;
  composite_score: number | null;
  nlp_component: number | null;
  stat_component: number | null;
  confidence: number | null;
  status: string;
};

export type ContractDetail = ContractSummary & {
  description: string | null;
  procurement_method: string | null;
  source_url: string | null;
  ingested_at: string;
  predictions: Prediction[];
  anomalies: Anomaly[];
};

export type AnomalyWithContract = Anomaly & { contract: ContractSummary };

export type Page<T> = { total: number; limit: number; offset: number; items: T[] };

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${path} devolvió ${res.status}`);
  }
  return res.json();
}

export function listContracts(params: Record<string, string | number | boolean | undefined>) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  }
  return apiFetch<Page<ContractSummary>>(`/contracts?${qs.toString()}`);
}

export function getContract(id: string) {
  return apiFetch<ContractDetail>(`/contracts/${id}`);
}

export function listAnomalies(params: Record<string, string | number | boolean | undefined>) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  }
  return apiFetch<Page<AnomalyWithContract>>(`/anomalies?${qs.toString()}`);
}

export type ExtractionMethod = "pdf" | "link" | "photo";

export type Extraction = {
  ocr_available: boolean;
  text_excerpt: string;
  suggested_title: string | null;
  suggested_amount: number | null;
  candidate_amounts: number[];
  warning: string | null;
};

export type Comparable = {
  id: string;
  title: string | null;
  buyer_name: string | null;
  amount_original: number;
  award_date: string | null;
};

export type Comparison = {
  reference_group: string;
  group_size: number;
  median_amount: number;
  submitted_amount: number;
  deviation_pct: number;
  zscore: number;
  zscore_flagged: boolean;
  iqr_flagged: boolean;
  verdict: "alta" | "revisar" | "normal";
  comparables: Comparable[];
};

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

async function apiFetchForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(body?.detail || `API ${path} devolvió ${res.status}`, res.status);
  }
  return res.json();
}

async function apiFetchJson<T>(path: string, payload: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(body?.detail || `API ${path} devolvió ${res.status}`, res.status);
  }
  return res.json();
}

export function extractAnalysis(method: ExtractionMethod, opts: { file?: File; link?: string }) {
  const form = new FormData();
  form.set("method", method);
  if (opts.file) form.set("file", opts.file);
  if (opts.link) form.set("link", opts.link);
  return apiFetchForm<Extraction>("/analyze/extract", form);
}

export function compareAnalysis(payload: {
  country: string;
  currency: string;
  amount: number;
  category?: string;
  buyer_name?: string;
}) {
  return apiFetchJson<Comparison>("/analyze/compare", payload);
}
