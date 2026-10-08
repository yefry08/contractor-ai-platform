import { ColumnsChart, RateChart, TableView, type Datum, type RatePoint } from "@/components/viz/charts";
import { MIN_RELIABLE_CONTRACTS } from "@/lib/thresholds";
import { DATA, Figure, Method, Stats, es, pct } from "../ui";

const MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const UNIFORM = 2 / 12;

export default function Article() {
  const py = DATA.calendar.PY.years as Record<string, number[]>;
  // 2022 stops on December 26 with two December contracts, so it can't say
  // anything about the end of that year.
  const years = Object.keys(py).filter((y) => y !== "2022");
  const total = (y: string) => py[y].reduce((a, b) => a + b, 0);
  const share = (y: string, ...months: number[]) => months.reduce((a, m) => a + py[y][m], 0) / total(y);

  const points: RatePoint[] = years.map((y) => ({
    label: y,
    rate: share(y, 10, 11),
    contracts: total(y),
    display: pct(share(y, 10, 11), 1),
    detail: `${es(py[y][10] + py[y][11])} de ${es(total(y))} contratos`,
  }));
  const before = years.filter((y) => +y <= 2018);
  const after = years.filter((y) => +y >= 2019);
  const range = (ys: string[]) => {
    const v = ys.map((y) => share(y, 10, 11));
    return `${pct(Math.min(...v))} a ${pct(Math.max(...v))}`;
  };
  const nov21: Datum[] = py["2021"].map((n, i) => ({ label: MONTHS[i], value: n, display: es(n) }));

  const uy = DATA.calendar.UY.years as Record<string, number[]>;
  const uyTotal = Object.values(uy).flat().reduce((a, b) => a + b, 0);
  const uyEnd = uy["2024"][11] + uy["2025"][0];

  return (
    <>
      <p className="post-lead">
        El presupuesto de muchos países se vence el 31 de diciembre: lo que no se compromete antes del cierre se pierde.
        La sospecha es conocida, que las instituciones aceleran las compras en las últimas semanas del año y compran
        rápido, con menos comparación. Paraguay, cuyo ejercicio fiscal es el año calendario, es el único país de la base con
        años completos para medirlo.
      </p>

      <Stats
        items={[
          { value: range(before), label: "de los contratos del año caen en noviembre y diciembre entre 2014 y 2018, menos que un reparto parejo (16,7%)" },
          { value: range(after), label: "entre 2019 y 2021: más de una vez y media un reparto parejo" },
          { value: es(py["2021"][10]), label: "contratos en noviembre de 2021, el mes más cargado de la serie" },
        ]}
      />

      <Figure
        title="Paraguay · parte de los contratos del año adjudicados en noviembre y diciembre"
        caption="La línea punteada es lo que pasaría si los contratos se repartieran parejo entre los 12 meses. No se muestra 2022 porque la muestra termina el 26 de diciembre con apenas dos contratos de ese mes."
      >
        <RateChart
          points={points}
          average={UNIFORM}
          averageLabel="reparto parejo 16,7%"
          minReliable={MIN_RELIABLE_CONTRACTS}
          label="Línea por año: parte de los contratos de Paraguay adjudicados en noviembre y diciembre"
        />
        <TableView
          caption="Ver como tabla"
          headers={["Año", "Contratos", "Nov + Dic", "Parte", "Noviembre", "Diciembre"]}
          rows={years.map((y) => [
            y,
            es(total(y)),
            es(py[y][10] + py[y][11]),
            pct(share(y, 10, 11), 1),
            pct(share(y, 10), 1),
            pct(share(y, 11), 1),
          ])}
        />
      </Figure>

      <h2>No hay un efecto diciembre. Hay un efecto noviembre, y es reciente</h2>
      <p>
        Entre 2014 y 2018 el cierre del año fue más tranquilo que el resto: noviembre y diciembre juntos reunían entre{" "}
        {range(before)} de los contratos del año. Desde 2019 el patrón cambia: {range(after)}. Y dentro de ese cierre, el mes
        fuerte no es diciembre. En 2021 noviembre reunió {es(py["2021"][10])} contratos ({pct(share("2021", 10), 1)} del
        año) y diciembre {es(py["2021"][11])} ({pct(share("2021", 11), 1)}).
      </p>

      <Figure title="Paraguay · contratos por mes en 2021">
        <ColumnsChart data={nov21} label="Contratos de Paraguay por mes en 2021, con un pico en noviembre" locale="es" height={220} />
        <TableView caption="Ver como tabla" headers={["Mes", "Contratos"]} rows={nov21.map((d) => [d.label, d.display])} />
      </Figure>

      <p>
        Hay dos lecturas posibles de la caída de diciembre de 2021. Puede ser que las instituciones adelanten sus compras
        a noviembre para llegar al cierre con el contrato firmado. O puede ser que los procesos de diciembre todavía no
        estén cargados al portal. Con estos datos no se puede decidir entre las dos, y por eso no afirmamos que haya una
        apuradera de fin de año: lo que se ve es un cambio de calendario, no una prueba de mala compra.
      </p>

      <h2>Lo que la muestra no deja medir</h2>
      <p>
        La base de Paraguay creció de {es(total("2014"))} contratos en 2014 a {es(total("2021"))} en 2021, así que usamos
        la parte de cada mes dentro de su año y no los conteos. Y los 9 años no son un censo: son lo que la fuente
        publicó. <strong>Uruguay</strong> no se puede leer: {es(uyEnd)} de sus {es(uyTotal)} contratos con fecha
        ({pct(uyEnd / uyTotal)}) caen entre diciembre de 2024 y enero de 2025. Eso podría ser un cierre de año real o la
        forma en que el portal publica y nosotros descargamos, y no tenemos cómo separarlo. Los demás países cubren uno o
        dos meses.
      </p>
      <p>
        Lo siguiente es cargar años completos de Colombia y Costa Rica, que publican mes a mes, y medir el cierre en
        más de un país antes de sacar conclusiones.
      </p>

      <Method>
        <p>
          Se cuenta cada contrato de Paraguay por el año y el mes de su fecha de adjudicación (fecha de inicio del periodo de
          adjudicación o, si falta, la de publicación). Se calcula qué parte de los contratos de cada año cae en noviembre
          y diciembre, y se compara con el 16,7% que resultaría de un reparto parejo entre los 12 meses.
        </p>
      </Method>
    </>
  );
}
