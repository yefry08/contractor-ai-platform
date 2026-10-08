import { BenfordChart, TableView } from "@/components/viz/charts";
import { DATA, Figure, Method, NAMES, Stats, es, pct } from "../ui";

const CLASS: Record<string, { label: string; tone: string }> = {
  close: { label: "Conformidad estrecha", tone: "ok" },
  acceptable: { label: "Conformidad aceptable", tone: "ok" },
  marginal: { label: "Conformidad marginal", tone: "warn" },
  nonconformity: { label: "No conforme", tone: "bad" },
};

export default function Article() {
  const expected = DATA.benford_expected;
  const rows = Object.entries(DATA.countries)
    .map(([code, c]) => ({ code, ...c.benford }))
    .sort((a, b) => a.mad - b.mad);
  const conform = rows.filter((r) => r.class === "close" || r.class === "acceptable");
  const gt = DATA.countries.GT.benford;
  const co = DATA.countries.CO.benford;
  const dr = DATA.countries.DO.benford;
  const total = rows.reduce((a, r) => a + r.n, 0);

  return (
    <>
      <p className="post-lead">
        En listas de montos que abarcan varios órdenes de magnitud, el primer dígito no se reparte por igual. Un 1 aparece
        cerca del 30% de las veces y un 9 menos del 5%. Es la ley de Benford, y los auditores la usan hace décadas como
        primera prueba: cuando muchos montos se fijan a mano, cerca de un límite o por una regla de precios, la curva se
        deforma. Aplicamos la prueba a los {es(total)} contratos con monto de los 10 países.
      </p>

      <Stats
        items={[
          { value: `${conform.length} de 10`, label: "países siguen la curva (conformidad estrecha o aceptable)" },
          { value: pct(gt.observed[7]), label: "de los montos de Guatemala empiezan con 8 (Benford espera 5,1%)" },
          { value: pct(co.observed[0]), label: "de los montos de Colombia empiezan con 1 (Benford espera 30,1%)" },
        ]}
      />

      <div className="post-legend" aria-hidden="true">
        <span><i className="post-key post-key-bar" /> Observado</span>
        <span><i className="post-key post-key-line" /> Esperado por Benford</span>
      </div>
      <div className="post-multiples">
        {rows.map((r) => (
          <div key={r.code} className="card post-multiple">
            <div className="post-multiple-head">
              <strong>{NAMES[r.code]}</strong>
              <span className={`post-pill post-pill-${CLASS[r.class].tone}`}>{CLASS[r.class].label}</span>
            </div>
            <BenfordChart
              observed={r.observed}
              expected={expected}
              names={["Observado", "Benford"]}
              label={`Primer dígito de los montos de ${NAMES[r.code]} contra la ley de Benford`}
            />
            <span className="post-multiple-foot">
              MAD {es(r.mad, 4)} · {es(r.n)} contratos
            </span>
          </div>
        ))}
      </div>
      <TableView
        caption="Ver como tabla"
        headers={["País", "Contratos", "MAD", "Clasificación", ...[1, 2, 3, 4, 5, 6, 7, 8, 9].map(String)]}
        rows={rows.map((r) => [NAMES[r.code], es(r.n), es(r.mad, 4), CLASS[r.class].label, ...r.observed.map((o) => pct(o, 1))])}
      />

      <h2>Tres desvíos, tres explicaciones</h2>
      <p>
        <strong>Guatemala</strong> es el caso más extremo (MAD {es(gt.mad, 4)}). El {pct(gt.observed[7])} de sus montos
        empieza con 8, cinco veces lo esperado. No es un misterio: son las compras directas apiladas justo debajo del techo
        legal de Q90.000, que analizamos en{" "}
        <a href="/datos/el-techo-de-las-compras-directas">El techo de las compras directas</a>.
      </p>
      <p>
        <strong>Colombia</strong> tiene demasiados montos que empiezan con 1 ({pct(co.observed[0])}) y muy pocos con 3, 4 y
        5. Una parte viene de montos redondos de presupuesto, como 10.000.000 o 15.000.000: un tercio de los montos
        colombianos de la muestra se escribe con una o dos cifras significativas.
      </p>
      <p>
        <strong>República Dominicana</strong> se sale por el 2 ({pct(dr.observed[1])} contra 17,6% esperado). Es el
        mismo efecto umbral: cientos de compras entre RD$200.000 y RD$268.111, el tope de la contratación directa de 2026.
      </p>
      <p>
        <strong>Perú</strong> aparece como no conforme, pero con solo {DATA.countries.PE.benford.n} contratos la prueba no
        tiene fuerza. Hacen falta cientos de montos para que el MAD sea estable.
      </p>

      <h2>Qué significa y qué no</h2>
      <p>
        Benford no detecta corrupción, detecta montos que no se formaron «solos». Un umbral legal, una tarifa fija o un
        catálogo de precios rompen la curva sin que nadie haga nada indebido. Lo útil es que señala dónde mirar: los tres
        desvíos grandes llevaron, cada uno, a un patrón concreto y verificable.
      </p>

      <Method>
        <p>
          Primer dígito del monto original (moneda local) de cada contrato con monto de al menos 10 unidades. Desviación
          absoluta media (MAD) contra la distribución de Benford, clasificada con los umbrales de Nigrini para el primer
          dígito: menos de 0,006 es conformidad estrecha, hasta 0,012 aceptable, hasta 0,015 marginal y por encima no
          conforme.
        </p>
      </Method>
    </>
  );
}
