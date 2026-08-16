import { listCountries, listAnomalies } from "@/lib/api";

export async function Metrics({ totalContracts }: { totalContracts: number }) {
  const [countries, anomalies] = await Promise.all([
    listCountries(),
    listAnomalies({ status: "open", limit: 1 }),
  ]);

  const items = [
    { value: totalContracts.toLocaleString("es"), label: "contratos ingeridos" },
    { value: anomalies.total.toLocaleString("es"), label: "anomalías abiertas" },
    { value: String(countries.filter((c) => c.active).length), label: "países OCDS activos" },
    { value: "2", label: "señales de detección independientes" },
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
