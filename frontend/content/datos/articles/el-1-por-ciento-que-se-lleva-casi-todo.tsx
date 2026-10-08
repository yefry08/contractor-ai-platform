import { ShareBarsChart, TableView } from "@/components/viz/charts";
import { DATA, Figure, Method, NAMES, Stats, es, pct } from "../ui";

export default function Article() {
  const rows = Object.entries(DATA.countries)
    .filter(([code]) => code !== "PE")
    .map(([code, c]) => ({ code, currency: c.main_currency, ...c.concentration }))
    .sort((a, b) => b.top1_share - a.top1_share);
  const dr = DATA.countries.DO.concentration;
  const py = DATA.countries.PY.concentration;
  const median = [...rows].sort((a, b) => a.top10_share - b.top10_share)[Math.floor(rows.length / 2)].top10_share;

  return (
    <>
      <p className="post-lead">
        Cuando se habla de «gasto público» se piensa en miles de compras. Pero el dinero se reparte de forma muy desigual:
        unos pocos contratos enormes pesan más que todo el resto junto. Para cada país medimos qué parte del monto total
        de la muestra se lleva el 1% de contratos más grandes, y qué parte el 10%.
      </p>

      <Stats
        items={[
          { value: pct(dr.largest_share), label: "del monto de República Dominicana es un solo contrato (almuerzo escolar, INABIE)" },
          { value: pct(median), label: "del monto se lo lleva el 10% de contratos más grandes, en el país típico" },
          { value: pct(py.largest_share, 1), label: "pesa el contrato más grande de Paraguay: el reparto más parejo" },
        ]}
      />

      <Figure title="Parte del monto total según el tamaño del contrato" caption="Cada barra es el monto total de la muestra del país, en su moneda principal.">
        <ShareBarsChart
          ramp
          rows={rows.map((r) => ({
            label: NAMES[r.code],
            values: [r.top1_share, r.top10_share - r.top1_share, 1 - r.top10_share],
          }))}
          names={["1% más grande", "Siguiente 9%", "Resto (90%)"]}
          label="Barras apiladas por país: parte del monto del 1% de contratos más grandes, del siguiente 9% y del resto"
        />
        <TableView
          caption="Ver como tabla"
          headers={["País", "Contratos", "Moneda", "Contrato más grande", "1% más grande", "10% más grande"]}
          rows={rows.map((r) => [NAMES[r.code], es(r.n), r.currency, pct(r.largest_share, 1), pct(r.top1_share, 1), pct(r.top10_share, 1)])}
        />
      </Figure>

      <h2>Lo que se ve</h2>
      <p>
        En <strong>República Dominicana</strong> un único contrato del Instituto Nacional de Bienestar Estudiantil, el
        suministro y distribución de raciones del almuerzo escolar por RD$47.445 millones, equivale al{" "}
        {pct(dr.largest_share)} de todo lo que suman los {es(dr.n)} contratos de la muestra. En <strong>Colombia</strong> el
        contrato más grande también es de alimentación escolar (Gobernación de Norte de Santander). En{" "}
        <strong>Brasil</strong> es una compra de vacunas contra el virus sincicial respiratorio del Ministerio de Salud,
        que sola suma el {pct(DATA.countries.BR.concentration.largest_share)}.
      </p>
      <p>
        En el otro extremo, <strong>Paraguay</strong> reparte mejor: su contrato más grande no llega al 3% y el 1% superior
        suma el {pct(py.top1_share)}.
      </p>

      <h2>Por qué importa para detectar anomalías</h2>
      <p>
        La revisión manual suele ir a los contratos más numerosos, pero el riesgo económico está en los pocos más grandes.
        Un sobreprecio del 10% en el contrato dominicano de almuerzo escolar mueve más dinero que duplicar el precio de
        todos los demás contratos de la muestra juntos. Por eso Contractor AI ordena las alertas también por monto, no solo por
        desviación.
      </p>
      <p>
        Cuidado al comparar países: cada muestra cubre un período distinto, y una sola adjudicación plurianual puede
        dominar un mes. Perú queda fuera del gráfico porque sus 84 contratos en soles no alcanzan para que el 1% sea más
        de un contrato.
      </p>

      <Method>
        <p>
          Contratos de cada país en su moneda principal (los de otras monedas no se suman, por no tener una tasa de cambio
          verificable por fecha). Se ordenan de mayor a menor monto y se suma la parte del total que representa el primer
          1% y el primer 10%.
        </p>
      </Method>
    </>
  );
}
