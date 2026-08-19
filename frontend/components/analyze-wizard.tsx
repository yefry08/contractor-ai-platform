"use client";

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

const COUNTRIES = [
  { code: "PY", name: "Paraguay", currency: "PYG" },
  { code: "CO", name: "Colombia", currency: "COP" },
  { code: "CR", name: "Costa Rica", currency: "CRC" },
  { code: "DO", name: "República Dominicana", currency: "DOP" },
];

const CURRENCIES = ["PYG", "COP", "CRC", "USD", "DOP"];

const METHODS: { key: ExtractionMethod; icon: string; title: string; sub: string }[] = [
  { key: "pdf", icon: "📄", title: "Subir PDF", sub: "Nativo o escaneado" },
  { key: "link", icon: "🔗", title: "Pegar link", sub: "Publicación oficial" },
];

const VERDICT_LABEL: Record<Comparison["verdict"], string> = {
  alta: "Alta desviación",
  revisar: "Revisar",
  normal: "Normal",
};

function fmtMoney(n: number, currency: string) {
  return `${n.toLocaleString("es", { maximumFractionDigits: 0 })} ${currency}`;
}

export function AnalyzeWizard() {
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
      setExtractWarning(err instanceof ApiError ? err.message : "No se pudo procesar el documento.");
      setStep(3);
    } finally {
      setExtracting(false);
    }
  }

  async function runComparison() {
    const parsedAmount = Number(amount);
    if (!parsedAmount || parsedAmount <= 0) {
      setCompareError("Ingresá un monto válido, mayor a 0.");
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
      setCompareError(err instanceof ApiError ? err.message : "No se pudo calcular la comparación.");
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
        setNarrativeError("El resumen con IA no está disponible en este momento.");
      }
    } catch (err) {
      setNarrativeError(err instanceof ApiError ? err.message : "No se pudo generar el resumen.");
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

  const stepNames = ["Elegir método", "Cargar", "Confirmar", "Resultado"];

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
            {extracting ? "Procesando el documento…" : "Calculando la comparación…"}
          </p>
        </div>
      )}

      {!extracting && !comparing && step === 1 && (
        <div>
          <h2 className="wizard-title">1 · Elegí cómo cargarlo</h2>
          <div className="wizard-methods">
            {METHODS.map((m) => (
              <button
                key={m.key}
                type="button"
                className={`wizard-method ${method === m.key ? "wizard-method-active" : ""}`}
                onClick={() => setMethod(m.key)}
              >
                <span className="wizard-method-icon">{m.icon}</span>
                <span className="wizard-method-title">{m.title}</span>
                <span className="wizard-method-sub">{m.sub}</span>
              </button>
            ))}
          </div>

          <div className="wizard-row">
            <label>
              País del contrato
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
              Continuar
            </button>
          </div>
        </div>
      )}

      {!extracting && !comparing && step === 2 && method && (
        <div>
          <h2 className="wizard-title">2 · {METHODS.find((m) => m.key === method)?.title}</h2>

          {method === "pdf" && (
            <div className="wizard-dropzone">
              <input
                type="file"
                accept="application/pdf"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
              <p>PDF nativo o escaneado, hasta 15 MB.</p>
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
              Atrás
            </button>
            <div style={{ flex: 1 }} />
            <button
              type="button"
              className="wizard-btn-primary"
              disabled={extracting || (method !== "link" && !file) || (method === "link" && !link)}
              onClick={runExtraction}
            >
              {extracting ? "Procesando…" : "Continuar"}
            </button>
          </div>
        </div>
      )}

      {!extracting && !comparing && step === 3 && (
        <div>
          <h2 className="wizard-title">3 · Confirmá los datos</h2>

          {extractWarning && <div className="wizard-warning">{extractWarning}</div>}
          {textExcerpt && (
            <details className="wizard-excerpt">
              <summary>Texto extraído (vista previa)</summary>
              <pre>{textExcerpt.slice(0, 1200)}</pre>
            </details>
          )}

          <div className="wizard-form-grid">
            <label className="wizard-field-wide">
              Título / objeto del contrato
              <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Opcional, solo para tu referencia" />
            </label>
            <label>
              Monto
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
              Moneda
              <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
                {CURRENCIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Comprador (opcional)
              <input type="text" value={buyerName} onChange={(e) => setBuyerName(e.target.value)} placeholder="Nombre exacto si lo sabés" />
            </label>
            <label>
              Categoría (opcional)
              <input type="text" value={category} onChange={(e) => setCategory(e.target.value)} placeholder="ej. services" />
            </label>
          </div>

          {candidateAmounts.length > 1 && (
            <div className="wizard-candidates">
              <span>¿Es otro el monto?</span>
              {candidateAmounts.map((c) => (
                <button key={c} type="button" onClick={() => setAmount(String(c))}>
                  {c.toLocaleString("es")}
                </button>
              ))}
            </div>
          )}

          {compareError && <div className="wizard-warning">{compareError}</div>}

          <div className="wizard-row">
            <button type="button" className="wizard-btn-secondary" onClick={() => setStep(2)}>
              Atrás
            </button>
            <div style={{ flex: 1 }} />
            <button type="button" className="wizard-btn-primary" disabled={comparing} onClick={runComparison}>
              {comparing ? "Calculando…" : "Calcular"}
            </button>
          </div>
        </div>
      )}

      {!extracting && !comparing && step === 4 && result && (
        <div>
          <div className="wizard-row" style={{ marginBottom: 18 }}>
            <span className={`badge wizard-verdict-${result.verdict}`}>{VERDICT_LABEL[result.verdict]}</span>
            <span className="wizard-note" style={{ marginLeft: 10 }}>
              Comparado contra {result.group_size.toLocaleString("es")} contratos ({result.reference_group})
            </span>
          </div>

          <div className="wizard-result-grid">
            <div className="metric-card">
              <div className="metric-value">{fmtMoney(result.submitted_amount, currency)}</div>
              <div className="metric-label">Monto ingresado</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{fmtMoney(result.median_amount, currency)}</div>
              <div className="metric-label">Mediana de referencia</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">
                {result.deviation_pct >= 0 ? "+" : ""}
                {result.deviation_pct.toFixed(1)}%
              </div>
              <div className="metric-label">Desviación · z={result.zscore.toFixed(2)}</div>
            </div>
          </div>

          <div className="note">
            Esto NO es una acusación de corrupción. El veredicto de arriba es puramente
            estadístico (mediana + MAD sobre el logaritmo del monto, misma fórmula que usa el
            resto de la app — ver /anomalies) contra contratos ya ingeridos del mismo país y
            moneda — ningún modelo de IA participa en ese cálculo. El resumen en lenguaje
            natural de abajo sí es opcional y generado por un modelo de IA externo (mejor
            esfuerzo, puede no estar disponible); nunca es la fuente del veredicto.
          </div>

          <div className="wizard-narrative">
            {!narrative && (
              <button type="button" className="wizard-btn-secondary" disabled={narrativeLoading} onClick={runNarrative}>
                {narrativeLoading ? "Generando…" : "✨ Generar resumen con IA (opcional)"}
              </button>
            )}
            {narrativeError && <div className="wizard-warning">{narrativeError}</div>}
            {narrative && (
              <div className="wizard-narrative-card">
                <span className="wizard-narrative-label">Resumen generado por IA</span>
                <p>{narrative}</p>
              </div>
            )}
          </div>

          {result.comparables.length > 0 && (
            <>
              <h3 className="wizard-subtitle">Contratos comparables más cercanos</h3>
              <table>
                <thead>
                  <tr>
                    <th>Título</th>
                    <th>Comprador</th>
                    <th>Monto</th>
                    <th>Fecha</th>
                  </tr>
                </thead>
                <tbody>
                  {result.comparables.map((c) => (
                    <tr key={c.id}>
                      <td>
                        <a href={`/contracts/${c.id}`}>{c.title ?? "(sin título)"}</a>
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
              Analizar otro
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
