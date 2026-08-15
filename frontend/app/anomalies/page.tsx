import { listAnomalies, ContractSummary } from "@/lib/api";

function fmtUsd(n: number | null) {
  if (n === null) return "—";
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

function fmtAmount(c: ContractSummary) {
  if (c.amount_usd !== null) return fmtUsd(c.amount_usd);
  if (c.amount_original !== null && c.currency) {
    return `${c.amount_original.toLocaleString("es")} ${c.currency}`;
  }
  return "—";
}

function fmtPct(n: number | null) {
  if (n === null) return "—";
  return `${(n * 100).toFixed(0)}%`;
}

function fmtDeviation(nlpComponent: number | null, statComponent: number | null) {
  if (nlpComponent !== null) return fmtPct(nlpComponent);
  if (statComponent !== null) return `z=${statComponent.toFixed(1)}`;
  return "—";
}

function signalLabel(nlpComponent: number | null, statComponent: number | null) {
  if (nlpComponent !== null && statComponent !== null) return "NLP + estadística";
  if (nlpComponent !== null) return "NLP";
  if (statComponent !== null) return "estadística";
  return "—";
}

export default async function AnomaliesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const limit = 25;
  const offset = Number(sp.offset ?? 0);

  const country = sp.country ?? "";
  const data = await listAnomalies({
    country: country || undefined,
    anomaly_type: sp.anomaly_type,
    min_score: sp.min_score,
    status: "open",
    limit,
    offset,
  });

  return (
    <>
      <h1>Anomalías detectadas</h1>
      <p className="subtitle">
        Dos señales independientes: desviación del modelo NLP (BERT + XGBoost, solo
        Paraguay y el bulk de Colombia) y desviación estadística robusta contra
        contratos similares (todos los países, Fase 5 / ADR 0003).{" "}
        {data.total.toLocaleString("es")} contratos marcados.
      </p>

      <div className="note">
        Esto NO es una acusación de corrupción. Señal NLP: desviación respecto al valor
        de referencia predicho por el modelo (solo se muestra cuando el valor real es al
        menos el doble o menos de la mitad del predicho). Señal estadística: z-score
        modificado (mediana + MAD, sobre el logaritmo del monto para no distorsionar por
        la asimetría típica del gasto público) comparado contra el mismo comprador,
        categoría o país — independiente de cualquier modelo de IA, calculado localmente
        a partir de los datos ya ingeridos. Cuando un contrato tiene las dos señales,
        ambas se muestran por separado, no se combinan en un solo número. Ver
        docs/adr/0003 y backend/scripts/compute_statistical_anomalies.py en el repo.
      </div>

      <form className="filters" method="get">
        <select name="country" defaultValue={country}>
          <option value="">Todos los países</option>
          <option value="PY">Paraguay</option>
          <option value="CO">Colombia</option>
          <option value="CR">Costa Rica</option>
          <option value="DO">República Dominicana</option>
        </select>
        <select name="anomaly_type" defaultValue={sp.anomaly_type ?? ""}>
          <option value="">Todos los tipos</option>
          <option value="overcost">Sobrecosto</option>
          <option value="undercost">Subcosto</option>
        </select>
        <input type="number" step="0.1" name="min_score" placeholder="Score mínimo (ej. 0.5)" defaultValue={sp.min_score ?? ""} />
        <button type="submit">Filtrar</button>
      </form>

      <table>
        <thead>
          <tr>
            <th>Contrato</th>
            <th>País</th>
            <th>Comprador</th>
            <th>Tipo</th>
            <th>Señal</th>
            <th>Desviación</th>
            <th>Monto</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((a) => (
            <tr key={a.id}>
              <td>
                <a href={`/contracts/${a.contract.id}`}>{a.contract.title ?? "(sin título)"}</a>
              </td>
              <td>{a.contract.country_code}</td>
              <td>{a.contract.buyer?.name ?? "—"}</td>
              <td>
                <span className={`badge ${a.anomaly_type}`}>
                  {a.anomaly_type === "overcost" ? "Sobrecosto" : "Subcosto"}
                </span>
              </td>
              <td>{signalLabel(a.nlp_component, a.stat_component)}</td>
              <td>{fmtDeviation(a.nlp_component, a.stat_component)}</td>
              <td>{fmtAmount(a.contract)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="pagination">
        {offset > 0 && (
          <a href={`?${new URLSearchParams({ ...sp, offset: String(Math.max(0, offset - limit)) } as Record<string, string>)}`}>
            ← Anterior
          </a>
        )}
        <span>
          {offset + 1}–{Math.min(offset + limit, data.total)} de {data.total}
        </span>
        {offset + limit < data.total && (
          <a href={`?${new URLSearchParams({ ...sp, offset: String(offset + limit) } as Record<string, string>)}`}>
            Siguiente →
          </a>
        )}
      </div>
    </>
  );
}
