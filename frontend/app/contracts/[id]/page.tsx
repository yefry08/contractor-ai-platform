import { getContract, listCitizenReports } from "@/lib/api";
import { CitizenReports } from "@/components/citizen-reports";

function fmtUsd(n: number | null) {
  if (n === null) return "—";
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

function fmtOriginal(n: number | null, currency: string | null) {
  if (n === null) return "—";
  return `${n.toLocaleString("es")} ${currency ?? ""}`.trim();
}

export default async function ContractDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const [c, reports] = await Promise.all([getContract(id), listCitizenReports(id)]);
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
          <strong>Monto original:</strong> {fmtOriginal(c.amount_original, c.currency)} <br />
          {c.amount_usd !== null && (
            <>
              <strong>Monto ajustado (USD, CPI):</strong> {fmtUsd(c.amount_usd)} <br />
            </>
          )}
          {c.ocid && (
            <>
              <strong>OCID:</strong> <code>{c.ocid}</code> <br />
            </>
          )}
          {c.source_url && (
            <>
              <strong>Fuente:</strong> <a href={c.source_url} target="_blank" rel="noreferrer">ver proceso original</a>
            </>
          )}
        </p>
      </div>

      {prediction && (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>Predicción del modelo (NLP)</h2>
          <p>
            <strong>Valor predicho:</strong>{" "}
            {prediction.predicted_value_usd !== null
              ? fmtUsd(prediction.predicted_value_usd)
              : fmtOriginal(prediction.predicted_value_original, c.currency)}
            <br />
            {prediction.range_low !== null && (
              <>
                <strong>Rango de referencia:</strong> {fmtUsd(prediction.range_low)} – {fmtUsd(prediction.range_high)} <br />
              </>
            )}
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
            {anomaly.nlp_component !== null && (
              <>
                Desviación del modelo NLP respecto al valor predicho:{" "}
                <strong>{(anomaly.nlp_component * 100).toFixed(1)}%</strong>
                <br />
              </>
            )}
            {anomaly.stat_component !== null && (
              <>
                Desviación estadística (z-score modificado, robusto, contra contratos
                similares del mismo comprador/categoría/país):{" "}
                <strong>{anomaly.stat_component.toFixed(2)}</strong>
              </>
            )}
          </p>
          <div className="note">
            {anomaly.nlp_component !== null && anomaly.stat_component !== null
              ? "Ambas señales coinciden en marcar este contrato — el modelo NLP y el método estadístico son completamente independientes entre sí."
              : anomaly.nlp_component !== null
                ? "Este score viene únicamente del modelo NLP. Todavía no hay una segunda capa estadística que lo corrobore para este contrato en particular."
                : "Este score viene únicamente del método estadístico (mediana + MAD, sin ningún modelo de IA de por medio) — no hay predicción del modelo NLP para este contrato."}{" "}
            Tratar como una señal a investigar, no como una conclusión.
          </div>
        </div>
      )}

      <CitizenReports contractId={c.id} initialReports={reports} />
    </>
  );
}
