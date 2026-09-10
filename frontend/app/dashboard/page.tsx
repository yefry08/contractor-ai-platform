import { getDashboardSummary, getBestBuyers, exportCsvUrl, CountryBreakdown } from "@/lib/api";
import { BarChart } from "@/components/ui/bar-chart";
import { Heatmap, MIN_RELIABLE_CONTRACTS } from "@/components/ui/heatmap";
import { ProviderFavoritismSection } from "@/components/provider-favoritism";
import { ContractsGraph } from "@/components/contracts-graph";
import { COUNTRIES, COUNTRY_NAMES } from "@/lib/countries";
import { getServerT } from "@/lib/i18n-server";


function fmtCompactUsd(n: number) {
  if (n <= 0) return "$0";
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

function fmtPct(n: number) {
  return `${(n * 100).toFixed(1)}%`;
}

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const country = sp.country || undefined;

  const [summary, buyers, { t, locale }] = await Promise.all([
    getDashboardSummary(country),
    getBestBuyers(country, 12),
    getServerT(),
  ]);

  const yearData = summary.by_year.map((y) => ({
    label: String(y.year),
    value: y.contracts,
    displayValue: y.contracts.toLocaleString(locale),
  }));

  const anomalyRateData = summary.by_year.map((y) => ({
    label: String(y.year),
    value: y.contracts ? y.anomalies / y.contracts : 0,
    displayValue: y.contracts ? `${((y.anomalies / y.contracts) * 100).toFixed(0)}%` : "0%",
  }));

  const categoryData = summary.by_category.map((c) => ({
    label: c.category_code.length > 14 ? `${c.category_code.slice(0, 13)}…` : c.category_code,
    value: c.contracts,
    displayValue: c.contracts.toLocaleString(locale),
  }));

  const countryData = summary.by_country.map((c: CountryBreakdown) => ({
    label: c.country_code,
    value: c.contracts,
    displayValue: c.contracts.toLocaleString(locale),
  }));

  const scope = country
    ? t("dashboard.scopeCountry", { country: COUNTRY_NAMES[country] ?? country })
    : t("dashboard.scopeAll", { count: COUNTRIES.length });

  return (
    <>
      <h1>{t("dashboard.title")}</h1>
      <p className="subtitle">
        {t("dashboard.subtitle", { n: summary.total_contracts.toLocaleString(locale), scope })}
      </p>

      <form className="filters" method="get">
        <select name="country" defaultValue={country ?? ""}>
          <option value="">{t("dashboard.allCountries")}</option>
          {Object.entries(COUNTRY_NAMES).map(([code, name]) => (
            <option key={code} value={code}>
              {name}
            </option>
          ))}
        </select>
        <button type="submit">{t("dashboard.filter")}</button>
        <a className="wizard-btn-secondary" style={{ textDecoration: "none" }} href={exportCsvUrl({ country })}>
          {t("dashboard.downloadCsv")}
        </a>
      </form>

      <div className="metrics-strip">
        <div className="metric-card">
          <div className="metric-value">{summary.total_contracts.toLocaleString(locale)}</div>
          <div className="metric-label">{t("dashboard.metricContracts")}</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{fmtCompactUsd(summary.total_amount_usd)}</div>
          <div className="metric-label">{t("dashboard.metricAmount")}</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{summary.total_anomalies.toLocaleString(locale)}</div>
          <div className="metric-label">{t("dashboard.metricAnomalies")}</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{fmtPct(summary.anomaly_rate)}</div>
          <div className="metric-label">{t("dashboard.metricRate")}</div>
        </div>
      </div>

      <div className="dashboard-grid">
        {!country && (
          <div className="card dashboard-chart-card dashboard-chart-wide">
            <h3>{t("heatmap.title")}</h3>
            <p className="heatmap-note">{t("heatmap.note", { min: MIN_RELIABLE_CONTRACTS })}</p>
            <Heatmap cells={summary.by_country_year} />
          </div>
        )}
        <div className="card dashboard-chart-card">
          <h3>{t("dashboard.chartContractsByYear")}</h3>
          <BarChart data={yearData} />
        </div>
        <div className="card dashboard-chart-card">
          <h3>{t("dashboard.chartRateByYear")}</h3>
          <BarChart data={anomalyRateData} color="var(--danger)" />
        </div>
        <div className="card dashboard-chart-card">
          <h3>{t("dashboard.chartTopCategories")}</h3>
          <BarChart data={categoryData} color="var(--ok)" />
        </div>
        {!country && countryData.length > 0 && (
          <div className="card dashboard-chart-card">
            <h3>{t("dashboard.chartCountryComparison")}</h3>
            <BarChart data={countryData} />
          </div>
        )}
      </div>

      <hr style={{ margin: "40px 0", border: "none", borderTop: "1px solid var(--border)" }} />

      <ContractsGraph initialCountry={country} />

      <h2 className="wizard-subtitle">
        {t("dashboard.bestTitle")}
        {country ? ` — ${COUNTRY_NAMES[country] ?? country}` : ""}
      </h2>
      <p className="wizard-note" style={{ marginBottom: 14 }}>
        {t("dashboard.bestNote", { min: buyers.min_contracts })}
      </p>

      {buyers.items.length === 0 ? (
        <p className="wizard-note">{t("dashboard.bestEmpty", { min: buyers.min_contracts })}</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>{t("dashboard.colInstitution")}</th>
              <th>{t("dashboard.colCountry")}</th>
              <th>{t("dashboard.colContracts")}</th>
              <th>{t("dashboard.colAmount")}</th>
              <th>{t("dashboard.colAnomalies")}</th>
              <th>{t("dashboard.colRate")}</th>
            </tr>
          </thead>
          <tbody>
            {buyers.items.map((b, i) => (
              <tr key={b.buyer_id}>
                <td>{i + 1}</td>
                <td>{b.name}</td>
                <td>{b.country_code}</td>
                <td>{b.total_contracts.toLocaleString(locale)}</td>
                <td>{fmtCompactUsd(b.total_amount_usd)}</td>
                <td>{b.anomalies}</td>
                <td>
                  <span className={`badge ${b.anomaly_rate === 0 ? "wizard-verdict-normal" : "wizard-verdict-revisar"}`}>
                    {fmtPct(b.anomaly_rate)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <hr style={{ margin: "40px 0", border: "none", borderTop: "1px solid var(--border)" }} />

      <ProviderFavoritismSection initialCountry={country} initialYear={2023} />
    </>
  );
}
