"use client";

import { useEffect, useState } from "react";
import { ApiError, TenderBenchmark, TenderCategory, TenderPortal, getTenderBenchmark } from "@/lib/api";

function fmtAmount(n: number, currency: string | null) {
  return `${Math.round(n).toLocaleString("es")} ${currency ?? ""}`.trim();
}

export function TenderCountryCard({ portal, categories }: { portal: TenderPortal; categories: TenderCategory[] }) {
  const [category, setCategory] = useState(categories[0]?.category_code ?? "");
  const [benchmark, setBenchmark] = useState<TenderBenchmark | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // The <select> starts pre-set to the first category, but onChange only
  // fires on an actual change -- without this, a visitor who never touches
  // the dropdown would see a category selected with no benchmark ever shown.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (categories[0]?.category_code) loadBenchmark(categories[0].category_code);
  }, []);

  async function loadBenchmark(nextCategory: string) {
    setCategory(nextCategory);
    setBenchmark(null);
    setError(null);
    if (!nextCategory) return;
    setLoading(true);
    try {
      const result = await getTenderBenchmark(portal.country_code, nextCategory);
      setBenchmark(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo calcular el benchmark.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card tender-card">
      <h3 className="tender-card-title">{portal.country_name}</h3>

      {categories.length === 0 ? (
        <p className="wizard-note">Todavía no hay suficientes contratos ingeridos por categoría en este país.</p>
      ) : (
        <>
          <label className="tender-select-label">
            Categoría de contrato
            <select value={category} onChange={(e) => loadBenchmark(e.target.value)}>
              {categories.map((c) => (
                <option key={c.category_code} value={c.category_code}>
                  {c.category_code} ({c.contracts.toLocaleString("es")})
                </option>
              ))}
            </select>
          </label>

          {loading && <p className="wizard-note">Calculando…</p>}
          {error && <div className="wizard-warning">{error}</div>}

          {benchmark && !loading && (
            <div className="tender-benchmark">
              <div className="tender-benchmark-median">
                <span className="tender-benchmark-value">{fmtAmount(benchmark.median_amount, benchmark.currency)}</span>
                <span className="tender-benchmark-label">Precio mediano histórico</span>
              </div>
              <p className="wizard-note">
                Rango típico: {fmtAmount(benchmark.typical_low, benchmark.currency)} –{" "}
                {fmtAmount(benchmark.typical_high, benchmark.currency)} · basado en{" "}
                {benchmark.sample_size.toLocaleString("es")} contratos similares ya ingeridos.
              </p>
            </div>
          )}
        </>
      )}

      <a
        href={portal.portal_url}
        target="_blank"
        rel="noopener noreferrer"
        className="wizard-btn-primary tender-portal-link"
      >
        Ver licitaciones oficiales en {portal.portal_name} →
      </a>
    </div>
  );
}
