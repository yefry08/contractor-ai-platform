import { ThresholdChart, TableView } from "@/components/viz/charts";
import { DATA, Figure, Method, Stats, es, pct } from "../ui";

const GT_CEILING = 90_000;
const DO_CEILING = 268_111.37;

function bins(country: "GT" | "DO", nearFrom: number) {
  const h = DATA.thresholds[country];
  return h.counts.map((value, i) => {
    const lo = h.low + i * h.step;
    return { lo, label: `${es(lo / 1000)}k`, value, near: lo >= nearFrom && lo <= (country === "GT" ? GT_CEILING : DO_CEILING) };
  });
}

export default function Article() {
  const gt = DATA.thresholds.GT;
  const gtBins = bins("GT", 88_000);
  const below = gt.counts.slice(0, 40);
  const typical = below.reduce((a, b) => a + b, 0) / below.length;
  const atCeiling = gtBins.filter((b) => b.near).reduce((a, b) => a + b.value, 0);
  const gtTotal = DATA.countries.GT.contracts;
  const peak = gt.counts[(89_000 - gt.low) / gt.step];
  const exact90 = gt.most_repeated[0][1];
  const justAbove = gt.counts.slice((91_000 - gt.low) / gt.step).reduce((a, b) => a + b, 0);

  const dr = DATA.thresholds.DO;
  const drBins = bins("DO", 260_000);
  const drTypical = dr.counts.slice(0, 15).reduce((a, b) => a + b, 0) / 15;
  const drPeak = dr.counts[(260_000 - dr.low) / dr.step];
  const drAfter = dr.counts[(270_000 - dr.low) / dr.step];
  const drMethod = dr.peak_methods.find(([m]) => String(m).startsWith("Compras por Debajo"));

  return (
    <>
      <p className="post-lead">
        Cada país fija un monto máximo para comprar sin licitar. En Guatemala, la compra directa con oferta electrónica
        (artículo 43, inciso b, de la Ley de Contrataciones del Estado) llega hasta <strong>Q90.000</strong>. Arriba de
        esa cifra hay que hacer una cotización, con más requisitos, más oferentes y más tiempo. Lo que muestran los
        datos es que miles de compras quedan pegadas justo debajo de ese techo.
      </p>

      <Stats
        items={[
          { value: es(atCeiling), label: "contratos entre Q88.000 y Q90.000" },
          { value: pct(atCeiling / gtTotal), label: `de los ${es(gtTotal)} contratos de Guatemala en la muestra` },
          { value: `×${es(peak / typical)}`, label: "más contratos en el tramo Q89.000–89.999 que el promedio de los tramos de Q40.000 a Q79.999" },
        ]}
      />

      <Figure
        title="Guatemala · contratos por tramo de Q1.000 (de Q40.000 a Q100.000)"
        caption={
          <>
            En naranja, los tramos de Q88.000 a Q90.000. Hay {es(exact90)} contratos de exactamente Q90.000 y solo{" "}
            {justAbove} entre Q91.000 y Q100.000.
          </>
        }
      >
        <ThresholdChart
          bins={gtBins}
          ceilingIndex={Math.floor((GT_CEILING - gt.low) / gt.step)}
          ceilingLabel="Techo legal: Q90.000"
          names={["Contratos por tramo", "Tramos pegados al techo"]}
          label="Histograma de contratos de Guatemala por monto, con un pico justo debajo de Q90.000"
          locale="es"
        />
        <TableView
          caption="Ver como tabla"
          headers={["Tramo (GTQ)", "Contratos"]}
          rows={gtBins.map((b) => [`${es(b.lo)} – ${es(b.lo + gt.step - 1)}`, es(b.value)])}
        />
      </Figure>

      <h2>Lo que se ve</h2>
      <p>
        Entre Q40.000 y Q79.999 cada tramo de mil quetzales reúne, en promedio, {es(typical)} contratos. Desde Q80.000 la
        cuenta sube, y en el último tramo antes del techo, de Q89.000 a Q89.999, hay <strong>{es(peak)}</strong>.
        Del lado de arriba del límite prácticamente no queda nada. El {pct(Number(gt.peak_methods[0][1]) / peak)} de ese tramo
        se hizo por compra directa con oferta electrónica, la modalidad que el techo regula.
      </p>
      <p>
        Los montos más repetidos de todo el país son Q90.000 exactos ({es(exact90)} contratos) y Q89.156 ({gt.most_repeated[1][1]}).
      </p>

      <h2>República Dominicana muestra el mismo corte</h2>
      <p>
        Desde el 1 de abril de 2026 la Dirección General de Contrataciones Públicas fija en <strong>RD$268.111,37</strong>{" "}
        el tope de la contratación directa sujeta al umbral (resolución PNP-03-2026). Los contratos dominicanos de la
        muestra son de agosto y septiembre de 2026, ya con ese tope vigente. El tramo de RD$260.000 a RD$269.999 reúne{" "}
        {drPeak} contratos, contra un promedio de {es(drTypical)} por tramo entre RD$100.000 y RD$249.999. En el tramo
        siguiente, que ya cae arriba del umbral, hay {drAfter}.
        {drMethod && <> De los {drPeak} del pico, {drMethod[1]} están registrados como «Compras por Debajo del Umbral».</>}
      </p>

      <Figure title="República Dominicana · contratos por tramo de RD$10.000 (de RD$100.000 a RD$400.000)">
        <ThresholdChart
          bins={drBins}
          ceilingIndex={Math.floor((DO_CEILING - dr.low) / dr.step)}
          ceilingLabel="Umbral: RD$268.111"
          names={["Contratos por tramo", "Tramo pegado al umbral"]}
          label="Histograma de contratos de República Dominicana por monto, con un pico justo debajo de RD$268.111"
          locale="es"
          height={260}
        />
        <TableView
          caption="Ver como tabla"
          headers={["Tramo (DOP)", "Contratos"]}
          rows={drBins.map((b) => [`${es(b.lo)} – ${es(b.lo + dr.step - 1)}`, es(b.value)])}
        />
      </Figure>

      <h2>Qué significa y qué no</h2>
      <p>
        Que las compras se acumulen debajo de un techo es esperable: si el presupuesto de una necesidad es Q95.000, quien
        compra tiene un incentivo legítimo para ajustarla y evitar un proceso largo. Pero es también el patrón exacto que
        deja el <strong>fraccionamiento</strong>, dividir una compra grande en varias pequeñas para no licitar, que la ley
        guatemalteca prohíbe. Los datos agregados no distinguen un caso del otro.
      </p>
      <p>
        El siguiente paso es mirar los contratos uno por uno. Hay que buscar al mismo comprador y al mismo proveedor con
        varias compras del mismo objeto, separadas por pocos días, que juntas superan el techo. Esa es la pieza que
        Contractor AI va a sumar.
      </p>

      <Method>
        <p>
          Contratos de Guatemala de septiembre de 2026 (descarga mensual OCDS de Guatecompras) en quetzales, y de República
          Dominicana de agosto y septiembre de 2026 (API de la DGCP) en pesos dominicanos. Tramos de Q1.000 y de RD$10.000.
          Fuentes de los techos: artículo 43 de la Ley de Contrataciones del Estado de Guatemala (Decreto 57-92 y sus
          reformas) y{" "}
          <a href="https://www.dgcp.gob.do/wp-content/uploads/page/PNP-03-2026_UMBRALES.pdf" target="_blank" rel="noopener noreferrer">
            resolución PNP-03-2026 de la DGCP
          </a>
          .
        </p>
      </Method>
    </>
  );
}
