import { getDashboardSummary, getBestBuyers, exportCsvUrl, CountryBreakdown } from "@/lib/api";
import { BarChart } from "@/components/ui/bar-chart";
import { ProviderFavoritismSection } from "@/components/provider-favoritism";

const COUNTRY_NAMES: Record<string, string> = {
  PY: "Paraguay",
  CO: "Colombia",
  CR: "Costa Rica",
  DO: "República Dominicana",
};

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

  const [summary, buyers] = await Promise.all([
    getDashboardSummary(country),
    getBestBuyers(country, 12),
  ]);

  const yearData = summary.by_year.map((y) => ({
    label: String(y.year),
    value: y.contracts,
    displayValue: String(y.contracts),
  }));

  const anomalyRateData = summary.by_year.map((y) => ({
    label: String(y.year),
    value: y.contracts ? y.anomalies / y.contracts : 0,
    displayValue: y.contracts ? `${((y.anomalies / y.contracts) * 100).toFixed(0)}%` : "0%",
  }));

  const categoryData = summary.by_category.map((c) => ({
    label: c.category_code.length > 14 ? `${c.category_code.slice(0, 13)}…` : c.category_code,
    value: c.contracts,
    displayValue: c.contracts.toLocaleString("es"),
  }));

  const countryData = summary.by_country.map((c: CountryBreakdown) => ({
    label: c.country_code,
    value: c.contracts,
    displayValue: c.contracts.toLocaleString("es"),
  }));

  return (
    <>
      <h1>Panel institucional</h1>
      <p className="subtitle">
        Vista agregada de {summary.total_contracts.toLocaleString("es")} contratos
        {country ? ` en ${COUNTRY_NAMES[country] ?? country}` : " en los 4 países cubiertos"}:
        volumen, tendencia y tasa de anomalías detectadas por la capa estadística
        (mediana + MAD sobre el logaritmo del monto).
      </p>

      <form className="filters" method="get">
        <select name="country" defaultValue={country ?? ""}>
          <option value="">Todos los países</option>
          {Object.entries(COUNTRY_NAMES).map(([code, name]) => (
            <option key={code} value={code}>
              {name}
            </option>
          ))}
        </select>
        <button type="submit">Filtrar</button>
        <a className="wizard-btn-secondary" style={{ textDecoration: "none" }} href={exportCsvUrl({ country })}>
          Descargar CSV
        </a>
      </form>

      <div className="metrics-strip">
        <div className="metric-card">
          <div className="metric-value">{summary.total_contracts.toLocaleString("es")}</div>
          <div className="metric-label">Contratos</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{fmtCompactUsd(summary.total_amount_usd)}</div>
          <div className="metric-label">Monto total (USD, cobertura parcial)</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{summary.total_anomalies.toLocaleString("es")}</div>
          <div className="metric-label">Anomalías abiertas</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{fmtPct(summary.anomaly_rate)}</div>
          <div className="metric-label">Tasa de anomalías</div>
        </div>
      </div>

      <div className="dashboard-grid">
        <div className="card dashboard-chart-card">
          <h3>Contratos por año</h3>
          <BarChart data={yearData} />
        </div>
        <div className="card dashboard-chart-card">
          <h3>Tasa de anomalías por año</h3>
          <BarChart data={anomalyRateData} color="var(--danger)" />
        </div>
        <div className="card dashboard-chart-card">
          <h3>Categorías principales</h3>
          <BarChart data={categoryData} color="var(--ok)" />
        </div>
        {!country && countryData.length > 0 && (
          <div className="card dashboard-chart-card">
            <h3>Comparación entre países</h3>
            <BarChart data={countryData} />
          </div>
        )}
      </div>

      <h2 className="wizard-subtitle">
        Instituciones con mejor historial de contratación
        {country ? ` en ${COUNTRY_NAMES[country] ?? country}` : ""}
      </h2>
      <p className="wizard-note" style={{ marginBottom: 14 }}>
        Instituciones con al menos {buyers.min_contracts} contratos ingeridos y la menor
        proporción de anomalías estadísticas abiertas, ordenadas de mejor a peor. No es un
        certificado de integridad — es una lectura del mismo dato que ya se usa en el resto
        de la app.
      </p>

      {buyers.items.length === 0 ? (
        <p className="wizard-note">
          No hay suficientes instituciones con {buyers.min_contracts}+ contratos para este filtro.
        </p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Institución</th>
              <th>País</th>
              <th>Contratos</th>
              <th>Monto total</th>
              <th>Anomalías</th>
              <th>Tasa</th>
            </tr>
          </thead>
          <tbody>
            {buyers.items.map((b, i) => (
              <tr key={b.buyer_id}>
                <td>{i + 1}</td>
                <td>{b.name}</td>
                <td>{b.country_code}</td>
                <td>{b.total_contracts.toLocaleString("es")}</td>
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
