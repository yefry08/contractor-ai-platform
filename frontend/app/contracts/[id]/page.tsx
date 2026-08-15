import { getContract } from "@/lib/api";

function fmtUsd(n: number | null) {
  if (n === null) return "—";
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

export default async function ContractDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const c = await getContract(id);
  const prediction = c.predictions[0];
  const anomaly = c.anomalies[0];

  return (
    <>
      <a href="/">← Volver a contratos</a>
      <h1>{c.title ?? "(sin título)"}</h1>
      <p className="subtitle">
        {c.buyer?.name ?? "Comprador desconocido"} · {c.country_code} · {c.award_date ?? "fecha desconocida"}
      </p>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Descripción</h2>
        <p>{c.description ?? "Sin descripción disponible."}</p>
        <p>
          <strong>Método de contratación:</strong> {c.procurement_method ?? "—"} <br />
          <strong>Categoría:</strong> {c.category_code ?? "—"} <br />
          <strong>Monto original:</strong> {c.amount_original?.toLocaleString("es")} {c.currency} <br />
          <strong>Monto ajustado (USD, CPI):</strong> {fmtUsd(c.amount_usd)} <br />
          <strong>OCID:</strong> <code>{c.ocid}</code>
        </p>
      </div>

      {prediction && (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>Predicción del modelo (NLP)</h2>
          <p>
            <strong>Valor predicho:</strong> {fmtUsd(prediction.predicted_value_usd)} <br />
            <strong>Rango de referencia:</strong> {fmtUsd(prediction.range_low)} – {fmtUsd(prediction.range_high)} <br />
            <strong>Score de similitud:</strong> {prediction.likelihood_score?.toFixed(4) ?? "—"} <br />
            <strong>Modelo:</strong> {prediction.model_name} ({prediction.model_version})
          </p>
        </div>
      )}

      {anomaly && (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>
            <span className={`badge ${anomaly.anomaly_type}`}>
              {anomaly.anomaly_type === "overcost" ? "Sobrecosto" : "Subcosto"}
            </span>
          </h2>
          <p>
            Desviación respecto al valor predicho:{" "}
            <strong>{anomaly.nlp_component !== null ? `${(anomaly.nlp_component * 100).toFixed(1)}%` : "—"}</strong>
          </p>
          <div className="note">
            Este score viene únicamente del modelo NLP. Todavía no hay una segunda capa
            estadística independiente que lo corrobore (Fase 5 del roadmap) — tratar como
            una señal a investigar, no como una conclusión.
          </div>
        </div>
      )}
    </>
  );
}
