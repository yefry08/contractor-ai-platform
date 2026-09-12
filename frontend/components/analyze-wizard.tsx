"use client";

import { COUNTRIES } from "@/lib/countries";
import { useState } from "react";
import {
  ApiError,
  Comparison,
  ExtractionMethod,
  compareAnalysis,
  extractAnalysis,
  generateNarrative,
} from "@/lib/api";
import { EyeLoader } from "@/components/ui/eye-loader";
import { useLanguage } from "@/lib/language-context";
import { fmtDeviation } from "@/lib/format";


// Derivado de COUNTRIES en vez de escrito a mano: la lista fija se quedó sin
// PEN al sumar Perú, y el síntoma no habría sido un error sino un desplegable
// que simplemente no ofrece la moneda del país recién agregado. USD va aparte
// porque no es la moneda de ningún país del corpus: es la de los montos que
// Costa Rica ya publica convertidos.
const CURRENCIES = [...new Set([...COUNTRIES.map((c) => c.currency), "USD"])];

const METHODS: { key: ExtractionMethod; icon: string }[] = [
  { key: "pdf", icon: "📄" },
  { key: "link", icon: "🔗" },
];

export function AnalyzeWizard() {
  const { t, locale } = useLanguage();
  const [step, setStep] = useState(1);
  const [method, setMethod] = useState<ExtractionMethod | null>(null);
  const [country, setCountry] = useState("PY");
  const [file, setFile] = useState<File | null>(null);
  const [link, setLink] = useState("");

  const [extracting, setExtracting] = useState(false);
  const [extractWarning, setExtractWarning] = useState<string | null>(null);
  const [textExcerpt, setTextExcerpt] = useState("");

  const [title, setTitle] = useState("");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("PYG");
  const [category, setCategory] = useState("");
  const [buyerName, setBuyerName] = useState("");
  const [candidateAmounts, setCandidateAmounts] = useState<number[]>([]);

  const [comparing, setComparing] = useState(false);
  const [compareError, setCompareError] = useState<string | null>(null);
  const [result, setResult] = useState<Comparison | null>(null);

  const [narrative, setNarrative] = useState<string | null>(null);
  const [narrativeLoading, setNarrativeLoading] = useState(false);
  const [narrativeError, setNarrativeError] = useState<string | null>(null);

  function pickCountry(code: string) {
    setCountry(code);
    setCurrency(COUNTRIES.find((c) => c.code === code)?.currency ?? "PYG");
  }

  function fmtMoney(n: number, cur: string) {
    return `${n.toLocaleString(locale, { maximumFractionDigits: 0 })} ${cur}`;
  }

  async function runExtraction() {
    if (!method) return;
    setExtracting(true);
    setExtractWarning(null);
    try {
      const res = await extractAnalysis(method, {
        file: file ?? undefined,
        link: link || undefined,
      });
      setTextExcerpt(res.text_excerpt);
      setExtractWarning(res.warning);
      if (res.suggested_title) setTitle(res.suggested_title);
      if (res.suggested_amount) setAmount(String(res.suggested_amount));
      setCandidateAmounts(res.candidate_amounts);
      setStep(3);
    } catch (err) {
      setExtractWarning(err instanceof ApiError ? err.message : t("wizard.errorExtract"));
      setStep(3);
    } finally {
      setExtracting(false);
    }
  }

  async function runComparison() {
    const parsedAmount = Number(amount);
    if (!parsedAmount || parsedAmount <= 0) {
      setCompareError(t("wizard.errorAmount"));
      return;
    }
    setComparing(true);
    setCompareError(null);
    setResult(null);
    try {
      const res = await compareAnalysis({
        country,
        currency,
        amount: parsedAmount,
        category: category || undefined,
        buyer_name: buyerName || undefined,
      });
      setResult(res);
      setStep(4);
    } catch (err) {
      setCompareError(err instanceof ApiError ? err.message : t("wizard.errorCompare"));
    } finally {
      setComparing(false);
    }
  }

  async function runNarrative() {
    if (!result) return;
    setNarrativeLoading(true);
    setNarrativeError(null);
    try {
      const summary =
        `verdict: ${result.verdict}, deviation: ${result.deviation_pct.toFixed(1)}%, ` +
        `zscore: ${result.zscore.toFixed(2)}, comparado contra ${result.group_size} contratos (${result.reference_group})`;
      const res = await generateNarrative(textExcerpt || title || "(sin texto extraído)", summary);
      if (res.available && res.narrative) {
        setNarrative(res.narrative);
      } else {
        setNarrativeError(t("wizard.aiUnavailable"));
      }
    } catch (err) {
      setNarrativeError(err instanceof ApiError ? err.message : t("wizard.errorNarrative"));
    } finally {
      setNarrativeLoading(false);
    }
  }

  function reset() {
    setStep(1);
    setMethod(null);
    setFile(null);
    setLink("");
    setExtractWarning(null);
    setTextExcerpt("");
    setTitle("");
    setAmount("");
    setCategory("");
    setBuyerName("");
    setCandidateAmounts([]);
    setCompareError(null);
    setResult(null);
    setNarrative(null);
    setNarrativeError(null);
  }

  const stepNames = [t("wizard.step1"), t("wizard.step2"), t("wizard.step3"), t("wizard.step4")];
  // deviation_pct arrives as a percentage; the shared formatter takes a fraction.
  const deviation = result ? fmtDeviation(result.deviation_pct / 100, locale) : null;

  return (
    <div className="wizard-card">
      <div className="wizard-steps">
        {stepNames.map((label, i) => {
          const n = i + 1;
          const state = n < step ? "done" : n === step ? "current" : "pending";
          return (
            <div key={label} className={`wizard-step wizard-step-${state}`}>
              <span className="wizard-step-n">{n < step ? "✓" : n}</span>
              <span>{label}</span>
            </div>
          );
        })}
      </div>

      {(extracting || comparing) && (
        <div className="wizard-loader">
          <EyeLoader />
          <p className="wizard-note" style={{ marginTop: 16, textAlign: "center", width: "100%" }}>
            {extracting ? t("wizard.processing") : t("wizard.calculating")}
          </p>
        </div>
      )}

      {!extracting && !comparing && step === 1 && (
        <div>
          <h2 className="wizard-title">1 · {t("wizard.title1")}</h2>
          <div className="wizard-methods">
            {METHODS.map((m) => (
              <button
                key={m.key}
                type="button"
                className={`wizard-method ${method === m.key ? "wizard-method-active" : ""}`}
                onClick={() => setMethod(m.key)}
              >
                <span className="wizard-method-icon">{m.icon}</span>
                <span className="wizard-method-title">{t(`wizard.method${m.key}`)}</span>
                <span className="wizard-method-sub">{t(`wizard.method${m.key}Sub`)}</span>
              </button>
            ))}
          </div>

          <div className="wizard-row">
            <label>
              {t("wizard.country")}
              <select value={country} onChange={(e) => pickCountry(e.target.value)}>
                {COUNTRIES.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <div style={{ flex: 1 }} />
            <button type="button" className="wizard-btn-primary" disabled={!method} onClick={() => setStep(2)}>
              {t("common.continue")}
            </button>
          </div>
        </div>
      )}

      {!extracting && !comparing && step === 2 && method && (
        <div>
          <h2 className="wizard-title">2 · {t(`wizard.method${method}`)}</h2>

          {method === "pdf" && (
            <div className="wizard-dropzone">
              <input
                type="file"
                accept="application/pdf"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
              <p>{t("wizard.dropHint")}</p>
            </div>
          )}

          {method === "link" && (
            <input
              type="url"
              className="wizard-input"
              placeholder="https://www.contrataciones.gov.py/licitaciones/adjudicacion/…"
              value={link}
              onChange={(e) => setLink(e.target.value)}
            />
          )}

          <div className="wizard-row">
            <button type="button" className="wizard-btn-secondary" onClick={() => setStep(1)}>
              {t("common.back")}
            </button>
            <div style={{ flex: 1 }} />
            <button
              type="button"
              className="wizard-btn-primary"
              disabled={extracting || (method !== "link" && !file) || (method === "link" && !link)}
              onClick={runExtraction}
            >
              {extracting ? t("wizard.processing") : t("common.continue")}
            </button>
          </div>
        </div>
      )}

      {!extracting && !comparing && step === 3 && (
        <div>
          <h2 className="wizard-title">3 · {t("wizard.title3")}</h2>

          {extractWarning && <div className="wizard-warning">{extractWarning}</div>}
          {textExcerpt && (
            <details className="wizard-excerpt">
              <summary>{t("wizard.excerpt")}</summary>
              <pre>{textExcerpt.slice(0, 1200)}</pre>
            </details>
          )}

          <div className="wizard-form-grid">
            <label className="wizard-field-wide">
              {t("wizard.fieldTitle")}
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={t("wizard.fieldTitlePlaceholder")}
              />
            </label>
            <label>
              {t("wizard.amount")}
              <input
                type="number"
                min="0"
                step="any"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0"
              />
            </label>
            <label>
              {t("wizard.currency")}
              <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
                {CURRENCIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
            <label>
              {t("wizard.buyer")}
              <input
                type="text"
                value={buyerName}
                onChange={(e) => setBuyerName(e.target.value)}
                placeholder={t("wizard.buyerPlaceholder")}
              />
            </label>
            <label>
              {t("wizard.category")}
              <input
                type="text"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder={t("wizard.categoryPlaceholder")}
              />
            </label>
          </div>

          {candidateAmounts.length > 1 && (
            <div className="wizard-candidates">
              <span>{t("wizard.otherAmount")}</span>
              {candidateAmounts.map((c) => (
                <button key={c} type="button" onClick={() => setAmount(String(c))}>
                  {c.toLocaleString(locale)}
                </button>
              ))}
            </div>
          )}

          {compareError && <div className="wizard-warning">{compareError}</div>}

          <div className="wizard-row">
            <button type="button" className="wizard-btn-secondary" onClick={() => setStep(2)}>
              {t("common.back")}
            </button>
            <div style={{ flex: 1 }} />
            <button type="button" className="wizard-btn-primary" disabled={comparing} onClick={runComparison}>
              {comparing ? t("wizard.calculating") : t("wizard.calculate")}
            </button>
          </div>
        </div>
      )}

      {!extracting && !comparing && step === 4 && result && (
        <div>
          <div className="wizard-row" style={{ marginBottom: 18 }}>
            <span className={`badge wizard-verdict-${result.verdict}`}>
              {t(`wizard.verdict${result.verdict}`)}
            </span>
            <span className="wizard-note" style={{ marginLeft: 10 }}>
              {t("wizard.comparedAgainst", {
                n: result.group_size.toLocaleString(locale),
                group: result.reference_group,
              })}
            </span>
          </div>

          <div className="wizard-result-grid">
            <div className="metric-card">
              <div className="metric-value">{fmtMoney(result.submitted_amount, currency)}</div>
              <div className="metric-label">{t("wizard.submitted")}</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{fmtMoney(result.median_amount, currency)}</div>
              <div className="metric-label">{t("wizard.median")}</div>
            </div>
            <div className="metric-card">
              <div className="metric-value" title={deviation?.title ?? undefined}>
                {deviation?.label ?? "—"}
              </div>
              <div className="metric-label">{t("wizard.deviation")}</div>
            </div>
          </div>

          <div className="note">{t("wizard.note")}</div>

          <div className="wizard-narrative">
            {!narrative && (
              <button type="button" className="wizard-btn-secondary" disabled={narrativeLoading} onClick={runNarrative}>
                {narrativeLoading ? t("wizard.generating") : `✨ ${t("wizard.generateAi")}`}
              </button>
            )}
            {narrativeError && <div className="wizard-warning">{narrativeError}</div>}
            {narrative && (
              <div className="wizard-narrative-card">
                <span className="wizard-narrative-label">{t("wizard.aiSummary")}</span>
                <p>{narrative}</p>
              </div>
            )}
          </div>

          {result.comparables.length > 0 && (
            <>
              <h3 className="wizard-subtitle">{t("wizard.comparables")}</h3>
              <table>
                <thead>
                  <tr>
                    <th>{t("home.colTitle")}</th>
                    <th>{t("home.colBuyer")}</th>
                    <th>{t("home.colAmount")}</th>
                    <th>{t("home.colDate")}</th>
                  </tr>
                </thead>
                <tbody>
                  {result.comparables.map((c) => (
                    <tr key={c.id}>
                      <td>
                        <a href={`/contracts/${c.id}`}>{c.title ?? t("common.untitled")}</a>
                      </td>
                      <td>{c.buyer_name ?? "—"}</td>
                      <td>{fmtMoney(c.amount_original, currency)}</td>
                      <td>{c.award_date ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          <div className="wizard-row" style={{ marginTop: 18 }}>
            <button type="button" className="wizard-btn-secondary" onClick={reset}>
              {t("wizard.analyzeAnother")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
