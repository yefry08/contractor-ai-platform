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
        Ordenadas por score de desviación entre el valor real y el valor predicho por el
        modelo NLP (BERT + XGBoost). {data.total.toLocaleString("es")} contratos marcados.
      </p>

      <div className="note">
        Esto NO es una acusación de corrupción — es una desviación estadística respecto al
        valor de referencia predicho por un solo modelo (capa NLP). Se muestran solo
        contratos donde el valor real es al menos el doble o menos de la mitad del valor
        predicho (corte grueso y provisional, no un umbral estadísticamente validado). La
        Fase 5 del roadmap agrega una segunda capa estadística independiente para
        validación cruzada antes de confiar en un umbral formal. Ver docs/adr/0003 en el
        repo.
      </div>

      <form className="filters" method="get">
        <select name="country" defaultValue={country}>
          <option value="">Todos los países</option>
          <option value="PY">Paraguay</option>
          <option value="CO">Colombia</option>
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
              <td>{fmtPct(a.nlp_component)}</td>
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
