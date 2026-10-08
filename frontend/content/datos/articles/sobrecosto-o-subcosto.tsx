import { DivergingChart, TableView } from "@/components/viz/charts";
import { DATA, Figure, Method, NAMES, Stats, es, pct } from "../ui";

// Counted on the live database for this post (see Method): open undercost flags
// on amounts below CLP 1,000 in Chile and at or below Q500 in Guatemala.
const CL_UNDER_1000 = 141;
const GT_UNDER_500 = 95;

export default function Article() {
  const rows = Object.entries(DATA.countries).map(([code, c]) => ({
    code,
    currency: c.main_currency,
    median: c.median_main,
    over: c.direction.overcost,
    under: c.direction.undercost,
  }));
  const totalOver = rows.reduce((a, r) => a + r.over.count, 0);
  const totalUnder = rows.reduce((a, r) => a + r.under.count, 0);
  const gt = DATA.countries.GT;
  const cl = DATA.countries.CL;
  const py = DATA.countries.PY;

  return (
    <>
      <p className="post-lead">
        Cuando se piensa en irregularidades en compras públicas se piensa en sobreprecios. Pero la capa estadística de
        Contractor AI marca los contratos que se alejan de su grupo en cualquier dirección, y en varios países la mayoría
        de las alertas son contratos anormalmente <em>baratos</em>. Separar las dos direcciones cambia la lectura de
        cada país.
      </p>

      <Stats
        items={[
          { value: es(totalOver), label: "alertas de sobrecosto abiertas en los 10 países" },
          { value: es(totalUnder), label: "alertas de subcosto abiertas" },
          { value: pct(gt.direction.undercost.count / (gt.direction.undercost.count + gt.direction.overcost.count)), label: "de las alertas de Guatemala son de subcosto" },
        ]}
      />

      <Figure title="Alertas abiertas por dirección y país" caption="A la izquierda, contratos muy por debajo de su grupo de referencia; a la derecha, muy por encima.">
        <DivergingChart
          rows={rows.map((r) => ({ label: NAMES[r.code], left: r.under.count, right: r.over.count }))}
          names={["Subcosto", "Sobrecosto"]}
          label="Barras divergentes por país: alertas de subcosto a la izquierda y de sobrecosto a la derecha"
          locale="es"
        />
        <TableView
          caption="Ver como tabla"
          headers={["País", "Moneda", "Mediana del país", "Subcosto", "Mediana del subcosto", "Sobrecosto", "Mediana del sobrecosto"]}
          rows={rows.map((r) => [
            NAMES[r.code],
            r.currency,
            es(r.median),
            es(r.under.count),
            r.under.median_main == null ? "—" : es(r.under.median_main),
            es(r.over.count),
            r.over.median_main == null ? "—" : es(r.over.median_main),
          ])}
        />
      </Figure>

      <h2>Dos grupos de países</h2>
      <p>
        <strong>Paraguay y Colombia</strong> marcan sobre todo contratos caros. En Paraguay hay {py.direction.overcost.count}{" "}
        alertas de sobrecosto contra {py.direction.undercost.count} de subcosto, y la mediana de los contratos marcados
        por sobrecosto es cinco veces la del país. Son las dos fuentes donde además corre el modelo de IA original, que
        predice el valor esperado a partir de la descripción y solo marca sobrecostos.
      </p>
      <p>
        <strong>Guatemala y Chile</strong> van al revés. Guatemala tiene {gt.direction.undercost.count} alertas de subcosto
        y {gt.direction.overcost.count} de sobrecosto. La mediana de los contratos marcados por subcosto es de Q
        {es(gt.direction.undercost.median_main ?? 0)}, frente a Q{es(gt.median_main)} del país, y {GT_UNDER_500} cuestan
        Q500 o menos. Chile tiene {cl.direction.undercost.count} alertas de subcosto, y {CL_UNDER_1000} de ellas son por menos
        de CLP 1.000, alrededor de un dólar.
      </p>

      <h2>Muchos «subcostos» son errores de carga</h2>
      <p>
        Una licitación chilena de CLP 78 no es una compra regalada: casi siempre es un precio unitario cargado en lugar del
        total, o un monto en UF o en miles tomado como pesos. Eso no hace inútil la alerta. Un portal que publica montos
        mal cargados no permite controlar ese gasto, y señalarlo es parte de la transparencia. Pero sí cambia a quién
        hay que avisar: a la entidad que publica los datos, no a un fiscal.
      </p>
      <p>
        Por eso, en la lista de anomalías de Contractor AI, cada alerta indica su dirección y el filtro por tipo permite
        separar «sobrecosto» de «subcosto».
      </p>

      <Method>
        <p>
          Alertas abiertas de la capa estadística (z-score modificado sobre el logaritmo del monto mayor a 3,5, o fuera de
          las cercas de Tukey) y del modelo de IA, agrupadas por la dirección registrada en cada alerta. Las medianas
          usan solo los contratos en la moneda principal de cada país. Los conteos de Chile por debajo de CLP 1.000 y de
          Guatemala de Q500 o menos se hicieron sobre la misma base el mismo día.
        </p>
      </Method>
    </>
  );
}
