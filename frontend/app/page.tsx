import { listContracts } from "@/lib/api";

function fmtUsd(n: number | null) {
  if (n === null) return "—";
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

export default async function ContractsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const limit = 25;
  const offset = Number(sp.offset ?? 0);

  const data = await listContracts({
    country: sp.country ?? "PY",
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
        {data.total.toLocaleString("es")} contratos — Fase 1: dataset histórico de Paraguay (DNCP).
      </p>

      <div className="note">
        Los montos en USD están ajustados por inflación (CPI) al año de referencia usado
        por el modelo original, no son el monto nominal al momento del contrato — se usan
        así para que sean comparables contra el valor predicho. Ver
        docs/architecture/PLANNING.md en el repo para el detalle metodológico.
      </div>

      <form className="filters" method="get">
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
            <th>Comprador</th>
            <th>Categoría</th>
            <th>Monto (USD, ajustado)</th>
            <th>Fecha</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((c) => (
            <tr key={c.id}>
              <td>
                <a href={`/contracts/${c.id}`}>{c.title ?? "(sin título)"}</a>
              </td>
              <td>{c.buyer?.name ?? "—"}</td>
              <td>{c.category_code ?? "—"}</td>
              <td>{fmtUsd(c.amount_usd)}</td>
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
