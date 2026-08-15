import { listContracts, ContractSummary } from "@/lib/api";

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

export default async function ContractsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const limit = 25;
  const offset = Number(sp.offset ?? 0);

  const country = sp.country ?? "";
  const data = await listContracts({
    country: country || undefined,
    buyer: sp.buyer,
    category: sp.category,
    only_anomalous: sp.only_anomalous === "1",
    limit,
    offset,
  });

  return (
    <>
      <h1>Contratos públicos</h1>
      <p className="subtitle">
        {data.total.toLocaleString("es")} contratos — Paraguay (DNCP, Fase 1) y Colombia
        (dos fuentes, ver nota abajo).
      </p>

      <div className="note">
        Paraguay: montos en USD ajustados por inflación (CPI) al año de referencia del
        modelo, no el monto nominal al momento del contrato. Colombia combina dos fuentes:
        ~5.000 contratos en vivo desde la API oficial de datos.gov.co (SECOP II, con fecha
        real, sin score de anomalía todavía — no hay modelo de predicción corriendo en
        vivo) y ~1.548 de un dataset ya procesado por un tercero (mismo autor del
        prototipo original, con predicción y anomalía pero sin fecha). Ninguna de las dos
        fuentes de Colombia tiene una tasa de cambio verificable por fecha, así que se
        muestra el monto original en pesos colombianos (COP) en vez de forzar una
        conversión a USD. Ver docs/architecture/PLANNING.md,
        backend/scripts/migrate_colombia.py y backend/scripts/ingest_colombia_live.py en
        el repo para el detalle metodológico.
      </div>

      <form className="filters" method="get">
        <select name="country" defaultValue={country}>
          <option value="">Todos los países</option>
          <option value="PY">Paraguay</option>
          <option value="CO">Colombia</option>
        </select>
        <input type="text" name="buyer" placeholder="Buscar comprador…" defaultValue={sp.buyer ?? ""} />
        <input type="text" name="category" placeholder="Categoría (ej. services)" defaultValue={sp.category ?? ""} />
        <label style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--muted)" }}>
          <input type="checkbox" name="only_anomalous" value="1" defaultChecked={sp.only_anomalous === "1"} />
          Solo con anomalías
        </label>
        <button type="submit">Filtrar</button>
      </form>

      <table>
        <thead>
          <tr>
            <th>Título</th>
            <th>País</th>
            <th>Comprador</th>
            <th>Categoría</th>
            <th>Monto</th>
            <th>Fecha</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((c) => (
            <tr key={c.id}>
              <td>
                <a href={`/contracts/${c.id}`}>{c.title ?? "(sin título)"}</a>
              </td>
              <td>{c.country_code}</td>
              <td>{c.buyer?.name ?? "—"}</td>
              <td>{c.category_code ?? "—"}</td>
              <td>{fmtAmount(c)}</td>
              <td>{c.award_date ?? "—"}</td>
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
