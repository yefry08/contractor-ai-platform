"use client";

import { useState } from "react";
import {
  getGeographicFavoritism,
  getPriceFavoritism,
  getProviderStats,
  getTemporalPatterns,
  getTopProviders,
} from "@/lib/api";

const COUNTRY_NAMES: Record<string, string> = {
  PY: "Paraguay",
  CO: "Colombia",
  CR: "Costa Rica",
  DO: "República Dominicana",
};

interface ProviderStats {
  total_providers: number;
  total_contracts: number;
  total_spending_usd: number;
  hhi_concentration: number;
  top_10_share: number;
}

interface ProviderDetail {
  provider_name: string;
  country_code: string;
  total_contracts: number;
  total_spending_usd: number;
  market_share: number;
  spending_share: number;
  avg_contract_value_usd: number;
  anomaly_rate: number;
  repeat_buyer_count: number;
}

interface PriceFavoritismPoint {
  provider_name: string;
  year: number;
  avg_contract_value_usd: number;
  market_baseline_usd: number;
  markup_percent: number;
}

interface GeographicPattern {
  provider_name: string;
  country_code: string;
  contracts: number;
  total_spending_usd: number;
  market_share_in_country: number;
}

interface TemporalCluster {
  provider_name: string;
  award_date: string;
  buyer_name: string;
  contract_amount_usd: number;
  consecutive_awards: number;
}

function fmtUsd(n: number) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

function fmtPct(n: number) {
  return `${(n * 100).toFixed(1)}%`;
}

export function ProviderFavoritismSection({
  initialCountry,
  initialYear,
}: {
  initialCountry?: string;
  initialYear?: number;
}) {
  const [country, setCountry] = useState(initialCountry || "");
  const [startYear, setStartYear] = useState(initialYear || 2023);
  const [endYear, setEndYear] = useState(2025);
  const [stats, setStats] = useState<ProviderStats | null>(null);
  const [providers, setProviders] = useState<ProviderDetail[]>([]);
  const [priceData, setPriceData] = useState<PriceFavoritismPoint[]>([]);
  const [geoData, setGeoData] = useState<GeographicPattern[]>([]);
  const [temporalData, setTemporalData] = useState<TemporalCluster[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      // These go through lib/api, which prefixes NEXT_PUBLIC_API_URL. A bare
      // relative fetch resolves against the frontend origin instead of the API
      // and comes back as a 404 HTML page.
      const [statsRes, providersRes, priceRes, geoRes, temporalRes] = await Promise.all([
        getProviderStats(country || undefined),
        getTopProviders(country || undefined, 20),
        getPriceFavoritism(country || undefined, startYear, endYear),
        getGeographicFavoritism(),
        getTemporalPatterns(country || undefined),
      ]);

      setStats(statsRes);
      setProviders(providersRes);
      setPriceData(priceRes);
      setGeoData(geoRes);
      setTemporalData(temporalRes);
    } catch (err) {
      // Surfaced rather than swallowed: an ignored failure here renders as an
      // empty section, which reads as "no favouritism found" rather than "the
      // request failed".
      setError(err instanceof Error ? err.message : "No se pudo cargar el análisis.");
    } finally {
      setLoading(false);
    }
  }

  // HHI interpretation
  function getHHIInterpretation(hhi: number): string {
    if (hhi > 2500) return "Highly Concentrated (Monopoly risk)";
    if (hhi > 1500) return "Moderately Concentrated";
    if (hhi > 1000) return "Somewhat Concentrated";
    return "Competitive (Low concentration)";
  }

  return (
    <div className="provider-favoritism-section">
      <h2 className="wizard-subtitle">Análisis de Favoritismo y Concentración de Proveedores</h2>
      <p className="wizard-note" style={{ marginBottom: 20 }}>
        Identifica patrones de concentración de mercado, favoritism por precio, favoritism geográfico y clustering temporal
        de adjudicaciones que podrían indicar corrupción o colusión entre compradores e proveedores.
      </p>

      {/* Filters */}
      <div className="filters" style={{ marginBottom: 20 }}>
        <select value={country} onChange={(e) => setCountry(e.target.value)}>
          <option value="">Todos los países</option>
          {Object.entries(COUNTRY_NAMES).map(([code, name]) => (
            <option key={code} value={code}>
              {name}
            </option>
          ))}
        </select>

        <label>
          Desde <input type="number" value={startYear} onChange={(e) => setStartYear(Number(e.target.value))} min="2020" max="2025" />
        </label>

        <label>
          Hasta <input type="number" value={endYear} onChange={(e) => setEndYear(Number(e.target.value))} min="2020" max="2025" />
        </label>

        <button onClick={loadData} disabled={loading} style={{ marginLeft: 10 }}>
          {loading ? "Cargando..." : "Actualizar"}
        </button>
      </div>

      {error && (
        <p className="wizard-note" style={{ color: "var(--danger)" }}>
          {error}
        </p>
      )}

      {!stats && !loading && !error && (
        <p className="wizard-note">Seleccioná los filtros y hacé clic en Actualizar para ver el análisis.</p>
      )}

      {/* Market Concentration Overview */}
      {stats && (
        <>
          <div className="metrics-strip" style={{ marginBottom: 30 }}>
            <div className="metric-card">
              <div className="metric-value">{stats.total_providers.toLocaleString("es")}</div>
              <div className="metric-label">Proveedores únicos</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{stats.hhi_concentration.toFixed(0)}</div>
              <div className="metric-label">HHI (0=competencia, 10000=monopolio)</div>
              <div className="wizard-note" style={{ marginTop: 6, fontSize: "0.9em" }}>
                {getHHIInterpretation(stats.hhi_concentration)}
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{fmtPct(stats.top_10_share / 100)}</div>
              <div className="metric-label">Top 10 share del gasto total</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{fmtUsd(stats.total_spending_usd)}</div>
              <div className="metric-label">Gasto total (USD)</div>
            </div>
          </div>

          <div className="dashboard-grid">
            {/* Top Providers */}
            {providers.length > 0 && (
              <div className="card dashboard-chart-card">
                <h3>Top 20 Proveedores por Gasto</h3>
                <table style={{ fontSize: "0.9em", width: "100%" }}>
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Proveedor</th>
                      <th>Contratos</th>
                      <th>Gasto (USD)</th>
                      <th>Share (%)</th>
                      <th>Promedio/Contrato</th>
                      <th>Tasa Anomalía</th>
                    </tr>
                  </thead>
                  <tbody>
                    {providers.map((p, i) => (
                      <tr key={i}>
                        <td>{i + 1}</td>
                        <td style={{ textAlign: "left", maxWidth: "200px", overflow: "hidden", textOverflow: "ellipsis" }}>
                          {p.provider_name}
                        </td>
                        <td>{p.total_contracts}</td>
                        <td>{fmtUsd(p.total_spending_usd)}</td>
                        <td>{p.spending_share.toFixed(1)}%</td>
                        <td>{fmtUsd(p.avg_contract_value_usd)}</td>
                        <td>
                          <span className={`badge ${p.anomaly_rate > 0.1 ? "wizard-verdict-revisar" : "wizard-verdict-normal"}`}>
                            {fmtPct(p.anomaly_rate)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Price Favoritism Trends */}
            {priceData.length > 0 && (
              <div className="card dashboard-chart-card">
                <h3>Favoritismo por Precio (Markup vs Baseline)</h3>
                <p className="wizard-note" style={{ fontSize: "0.9em", marginBottom: 10 }}>
                  Proveedores que consistentemente reciben montos superiores al promedio del mercado en el mismo año.
                </p>
                <div style={{ maxHeight: "300px", overflowY: "auto" }}>
                  <table style={{ fontSize: "0.85em", width: "100%" }}>
                    <thead>
                      <tr>
                        <th>Proveedor</th>
                        <th>Año</th>
                        <th>Promedio/Contrato</th>
                        <th>Baseline Mercado</th>
                        <th>Markup (%)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {priceData.map((p, i) => (
                        <tr key={i} style={{ backgroundColor: p.markup_percent > 20 ? "rgba(255,107,107,0.1)" : "" }}>
                          <td>{p.provider_name}</td>
                          <td>{p.year}</td>
                          <td>{fmtUsd(p.avg_contract_value_usd)}</td>
                          <td>{fmtUsd(p.market_baseline_usd)}</td>
                          <td style={{ fontWeight: p.markup_percent > 20 ? "bold" : "normal", color: p.markup_percent > 20 ? "#e63946" : "#000" }}>
                            {p.markup_percent > 0 ? "+" : ""}{p.markup_percent.toFixed(1)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Geographic Favoritism */}
            {geoData.length > 0 && (
              <div className="card dashboard-chart-card">
                <h3>Dominancia Geográfica de Proveedores</h3>
                <p className="wizard-note" style={{ fontSize: "0.9em", marginBottom: 10 }}>
                  Top proveedores por país: qué tan concentrado es el mercado en cada región.
                </p>
                <div style={{ maxHeight: "300px", overflowY: "auto" }}>
                  <table style={{ fontSize: "0.85em", width: "100%" }}>
                    <thead>
                      <tr>
                        <th>País</th>
                        <th>Proveedor</th>
                        <th>Contratos</th>
                        <th>Gasto (USD)</th>
                        <th>Market Share en País (%)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {geoData.map((g, i) => (
                        <tr key={i} style={{ backgroundColor: g.market_share_in_country > 15 ? "rgba(255,107,107,0.1)" : "" }}>
                          <td>{COUNTRY_NAMES[g.country_code] || g.country_code}</td>
                          <td>{g.provider_name}</td>
                          <td>{g.contracts}</td>
                          <td>{fmtUsd(g.total_spending_usd)}</td>
                          <td style={{ fontWeight: g.market_share_in_country > 15 ? "bold" : "normal" }}>
                            {g.market_share_in_country.toFixed(1)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Temporal Clustering */}
            {temporalData.length > 0 && (
              <div className="card dashboard-chart-card">
                <h3>Clustering Temporal (Adjudicaciones Concentradas)</h3>
                <p className="wizard-note" style={{ fontSize: "0.9em", marginBottom: 10 }}>
                  Proveedores que reciben 3+ contratos en el mismo mes (puede indicar coordinación).
                </p>
                <div style={{ maxHeight: "300px", overflowY: "auto" }}>
                  <table style={{ fontSize: "0.85em", width: "100%" }}>
                    <thead>
                      <tr>
                        <th>Proveedor</th>
                        <th>Fecha</th>
                        <th>Contratos en Mes</th>
                        <th>Monto (USD)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {temporalData.map((t, i) => (
                        <tr key={i} style={{ backgroundColor: t.consecutive_awards >= 5 ? "rgba(255,107,107,0.1)" : "rgba(255,193,7,0.05)" }}>
                          <td>{t.provider_name}</td>
                          <td>{new Date(t.award_date).toLocaleDateString("es-ES")}</td>
                          <td style={{ fontWeight: "bold", color: t.consecutive_awards >= 5 ? "#e63946" : "#ff9800" }}>
                            {t.consecutive_awards}
                          </td>
                          <td>{fmtUsd(t.contract_amount_usd)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          {/* Interpretation */}
          <div className="card" style={{ marginTop: 20, backgroundColor: "rgba(33,150,243,0.05)", padding: "16px" }}>
            <h3 style={{ marginTop: 0 }}>📊 Cómo Interpretar Estos Datos</h3>
            <ul style={{ fontSize: "0.95em", lineHeight: 1.6 }}>
              <li>
                <strong>HHI &gt; 2500:</strong> Mercado altamente concentrado. Riesgo de monopolio o colusión.
              </li>
              <li>
                <strong>Markup &gt; 20%:</strong> Proveedor recibe consistentemente más del promedio. Indicador de favoritismo por precio.
              </li>
              <li>
                <strong>Market Share &gt; 15% en un país:</strong> Dominancia geográfica. Posible favoritismo regional.
              </li>
              <li>
                <strong>Clustering Temporal:</strong> 5+ adjudicaciones en un mes = riesgo alto de coordinación entre comprador y proveedor.
              </li>
              <li>
                <strong>Anomaly Rate alto:</strong> Proveedor frecuentemente marcado con anomalías estadísticas. Investigación recomendada.
              </li>
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
