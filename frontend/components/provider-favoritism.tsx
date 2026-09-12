"use client";

import { useState } from "react";
import {
  getGeographicFavoritism,
  getPriceFavoritism,
  getProviderStats,
  getTemporalPatterns,
  getTopProviders,
} from "@/lib/api";
import { COUNTRY_NAMES } from "@/lib/countries";
import { useLanguage } from "@/lib/language-context";
import { fmtCompactUsd, fmtPct } from "@/lib/format";


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

export function ProviderFavoritismSection({
  initialCountry,
  initialYear,
}: {
  initialCountry?: string;
  initialYear?: number;
}) {
  const { t, locale } = useLanguage();
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
      setError(err instanceof Error ? err.message : t("fav.error"));
    } finally {
      setLoading(false);
    }
  }

  function hhiLabel(hhi: number): string {
    if (hhi > 2500) return t("fav.hhiHigh");
    if (hhi > 1500) return t("fav.hhiModerate");
    if (hhi > 1000) return t("fav.hhiSome");
    return t("fav.hhiCompetitive");
  }

  return (
    <div className="provider-favoritism-section">
      <h2 className="wizard-subtitle">{t("fav.title")}</h2>
      <p className="wizard-note" style={{ marginBottom: 20 }}>
        {t("fav.lead")}
      </p>

      <div className="filters" style={{ marginBottom: 20 }}>
        <select value={country} onChange={(e) => setCountry(e.target.value)}>
          <option value="">{t("home.allCountries")}</option>
          {Object.entries(COUNTRY_NAMES).map(([code, name]) => (
            <option key={code} value={code}>
              {name}
            </option>
          ))}
        </select>

        <label>
          {t("fav.from")}{" "}
          <input type="number" value={startYear} onChange={(e) => setStartYear(Number(e.target.value))} min="2020" max="2025" />
        </label>

        <label>
          {t("fav.to")}{" "}
          <input type="number" value={endYear} onChange={(e) => setEndYear(Number(e.target.value))} min="2020" max="2025" />
        </label>

        <button onClick={loadData} disabled={loading} style={{ marginLeft: 10 }}>
          {loading ? t("fav.loading") : t("fav.update")}
        </button>
      </div>

      {error && (
        <p className="wizard-note" style={{ color: "var(--danger)" }}>
          {error}
        </p>
      )}

      {!stats && !loading && !error && <p className="wizard-note">{t("fav.selectFilters")}</p>}

      {stats && (
        <>
          <div className="metrics-strip" style={{ marginBottom: 30 }}>
            <div className="metric-card">
              <div className="metric-value">{stats.total_providers.toLocaleString(locale)}</div>
              <div className="metric-label">{t("fav.providers")}</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{stats.hhi_concentration.toFixed(0)}</div>
              <div className="metric-label">{t("fav.hhi")}</div>
              <div className="wizard-note" style={{ marginTop: 6, fontSize: "0.9em" }}>
                {hhiLabel(stats.hhi_concentration)}
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{fmtPct(stats.top_10_share / 100, locale)}</div>
              <div className="metric-label">{t("fav.top10")}</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{fmtCompactUsd(stats.total_spending_usd, locale)}</div>
              <div className="metric-label">{t("fav.totalSpend")}</div>
            </div>
          </div>

          <div className="dashboard-grid">
            {providers.length > 0 && (
              <div className="card dashboard-chart-card">
                <h3>{t("fav.topProviders")}</h3>
                <table style={{ fontSize: "0.9em", width: "100%" }}>
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>{t("fav.colProvider")}</th>
                      <th>{t("fav.colContracts")}</th>
                      <th>{t("fav.colSpend")}</th>
                      <th>{t("fav.colShare")}</th>
                      <th>{t("fav.colAvg")}</th>
                      <th>{t("fav.colAnomalyRate")}</th>
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
                        <td>{fmtCompactUsd(p.total_spending_usd, locale)}</td>
                        <td>{fmtPct(p.spending_share / 100, locale)}</td>
                        <td>{fmtCompactUsd(p.avg_contract_value_usd, locale)}</td>
                        <td>
                          <span className={`badge ${p.anomaly_rate > 0.1 ? "wizard-verdict-revisar" : "wizard-verdict-normal"}`}>
                            {fmtPct(p.anomaly_rate, locale)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {priceData.length > 0 && (
              <div className="card dashboard-chart-card">
                <h3>{t("fav.priceTitle")}</h3>
                <p className="wizard-note" style={{ fontSize: "0.9em", marginBottom: 10 }}>
                  {t("fav.priceLead")}
                </p>
                <div style={{ maxHeight: "300px", overflowY: "auto" }}>
                  <table style={{ fontSize: "0.85em", width: "100%" }}>
                    <thead>
                      <tr>
                        <th>{t("fav.colProvider")}</th>
                        <th>{t("fav.colYear")}</th>
                        <th>{t("fav.colAvg")}</th>
                        <th>{t("fav.colBaseline")}</th>
                        <th>{t("fav.colMarkup")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {priceData.map((p, i) => {
                        const high = p.markup_percent > 20;
                        return (
                          <tr key={i} style={{ backgroundColor: high ? "var(--warning-bg)" : "" }}>
                            <td>{p.provider_name}</td>
                            <td>{p.year}</td>
                            <td>{fmtCompactUsd(p.avg_contract_value_usd, locale)}</td>
                            <td>{fmtCompactUsd(p.market_baseline_usd, locale)}</td>
                            <td style={{ fontWeight: high ? "bold" : "normal", color: high ? "var(--danger)" : "var(--text)" }}>
                              {p.markup_percent > 0 ? "+" : ""}
                              {Math.round(p.markup_percent).toLocaleString(locale)}%
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {geoData.length > 0 && (
              <div className="card dashboard-chart-card">
                <h3>{t("fav.geoTitle")}</h3>
                <p className="wizard-note" style={{ fontSize: "0.9em", marginBottom: 10 }}>
                  {t("fav.geoLead")}
                </p>
                <div style={{ maxHeight: "300px", overflowY: "auto" }}>
                  <table style={{ fontSize: "0.85em", width: "100%" }}>
                    <thead>
                      <tr>
                        <th>{t("home.colCountry")}</th>
                        <th>{t("fav.colProvider")}</th>
                        <th>{t("fav.colContracts")}</th>
                        <th>{t("fav.colSpend")}</th>
                        <th>{t("fav.colShareCountry")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {geoData.map((g, i) => {
                        const dominant = g.market_share_in_country > 15;
                        return (
                          <tr key={i} style={{ backgroundColor: dominant ? "var(--warning-bg)" : "" }}>
                            <td>{COUNTRY_NAMES[g.country_code] || g.country_code}</td>
                            <td>{g.provider_name}</td>
                            <td>{g.contracts}</td>
                            <td>{fmtCompactUsd(g.total_spending_usd, locale)}</td>
                            <td style={{ fontWeight: dominant ? "bold" : "normal" }}>
                              {fmtPct(g.market_share_in_country / 100, locale)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {temporalData.length > 0 && (
              <div className="card dashboard-chart-card">
                <h3>{t("fav.temporalTitle")}</h3>
                <p className="wizard-note" style={{ fontSize: "0.9em", marginBottom: 10 }}>
                  {t("fav.temporalLead")}
                </p>
                <div style={{ maxHeight: "300px", overflowY: "auto" }}>
                  <table style={{ fontSize: "0.85em", width: "100%" }}>
                    <thead>
                      <tr>
                        <th>{t("fav.colProvider")}</th>
                        <th>{t("home.colDate")}</th>
                        <th>{t("fav.colAwardsMonth")}</th>
                        <th>{t("home.colAmount")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {temporalData.map((tc, i) => (
                        <tr key={i} style={{ backgroundColor: tc.consecutive_awards >= 5 ? "var(--warning-bg)" : "" }}>
                          <td>{tc.provider_name}</td>
                          <td>{new Date(tc.award_date).toLocaleDateString(locale)}</td>
                          <td style={{ fontWeight: "bold", color: tc.consecutive_awards >= 5 ? "var(--danger)" : "var(--amber)" }}>
                            {tc.consecutive_awards}
                          </td>
                          <td>{fmtCompactUsd(tc.contract_amount_usd, locale)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          <div className="card" style={{ marginTop: 20 }}>
            <h3 style={{ marginTop: 0 }}>📊 {t("fav.interpretTitle")}</h3>
            <ul style={{ fontSize: "0.95em", lineHeight: 1.6 }}>
              {["i1", "i2", "i3", "i4", "i5"].map((k) => (
                <li key={k}>
                  <strong>{t(`fav.${k}Label`)}:</strong> {t(`fav.${k}Text`)}
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
