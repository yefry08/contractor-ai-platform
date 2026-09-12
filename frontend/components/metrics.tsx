import { listCountries, listAnomalies } from "@/lib/api";
import { getServerT } from "@/lib/i18n-server";

export async function Metrics({ totalContracts }: { totalContracts: number }) {
  const [countries, anomalies, { t, locale }] = await Promise.all([
    listCountries(),
    listAnomalies({ status: "open", limit: 1 }),
    getServerT(),
  ]);

  const items = [
    { value: totalContracts.toLocaleString(locale), label: t("metrics.contracts") },
    { value: anomalies.total.toLocaleString(locale), label: t("metrics.openAnomalies") },
    { value: String(countries.filter((c) => c.active).length), label: t("metrics.activeCountries") },
    { value: "2", label: t("metrics.signals") },
  ];

  return (
    <div className="metrics-strip">
      {items.map((m) => (
        <div key={m.label} className="metric-card">
          <div className="metric-value">{m.value}</div>
          <div className="metric-label">{m.label}</div>
        </div>
      ))}
    </div>
  );
}
