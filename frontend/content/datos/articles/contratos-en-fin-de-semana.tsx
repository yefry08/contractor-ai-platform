import { ColumnsChart, RankBarsChart, TableView, type Datum } from "@/components/viz/charts";
import { Figure, Method, NAMES, Stats, WEEKDAY, es, pct } from "../ui";

const DAYS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

function weekdayData(code: "CO" | "CR"): Datum[] {
  return WEEKDAY[code].days.map((n, i) => ({ label: DAYS[i], value: n, display: es(n) }));
}

export default function Article() {
  const rows = Object.entries(WEEKDAY).map(([code, w]) => {
    const total = w.days.reduce((a, b) => a + b, 0);
    const weekend = w.days[5] + w.days[6];
    const top = w.top[0];
    return { code, total, weekend, share: weekend / total, topShare: top ? top.n / weekend : 0, top };
  });
  const withWeekend = rows.filter((r) => r.weekend > 0);
  const batched = withWeekend.filter((r) => r.topShare >= 0.6);

  const cr = WEEKDAY.CR.top;
  const crTwoDays = cr[0].n + cr[1].n;
  const crWeekend = rows.find((r) => r.code === "CR")!.weekend;
  const crMethods = WEEKDAY.CR.methods;
  const co = rows.find((r) => r.code === "CO")!;
  const py = rows.find((r) => r.code === "PY")!;
  const date = (iso: string) =>
    new Date(iso + "T12:00:00")
      .toLocaleDateString("es", { weekday: "long", day: "numeric", month: "long", year: "numeric" })
      .replace(", ", " ");

  return (
    <>
      <p className="post-lead">
        Las oficinas públicas no suelen adjudicar contratos un sábado o un domingo. Cuando un contrato figura firmado en
        fin de semana, hay tres explicaciones posibles: una urgencia, una carga tardía al portal o un proceso acelerado.
        Miramos la fecha de cada contrato de los 10 países y encontramos algo más simple: las adjudicaciones de fin de
        semana son pocas y casi siempre llegan <strong>todas juntas, un mismo día</strong>.
      </p>

      <Stats
        items={[
          { value: es(crWeekend), label: "adjudicaciones de Costa Rica en fin de semana" },
          { value: es(crTwoDays), label: `de esas ${crWeekend} caen en solo dos fechas: el sábado 8 y el domingo 9 de agosto de 2026` },
          { value: `${batched.length} de ${withWeekend.length}`, label: "países con fines de semana donde una sola fecha reúne el 60% o más de ellos" },
        ]}
      />

      <Figure
        title="Parte de los contratos con fecha en sábado o domingo"
        caption="En naranja, los países donde una sola fecha reúne el 60% o más de las adjudicaciones de fin de semana."
      >
        <RankBarsChart
          rows={rows.map((r) => ({
            label: NAMES[r.code],
            value: r.share,
            display: pct(r.share, 1),
            highlight: r.topShare >= 0.6,
          }))}
          label="Barras por país: porcentaje de contratos con fecha en fin de semana"
        />
        <TableView
          caption="Ver como tabla"
          headers={["País", "Contratos con fecha", "En fin de semana", "Parte", "Fecha más activa", "Parte de esa fecha"]}
          rows={rows.map((r) => [
            NAMES[r.code],
            es(r.total),
            es(r.weekend),
            pct(r.share, 1),
            r.top ? `${r.top.date} (${es(r.top.n)})` : "—",
            r.top ? pct(r.topShare) : "—",
          ])}
        />
      </Figure>

      <h2>Un domingo con 93 adjudicaciones</h2>
      <p>
        En <strong>Costa Rica</strong>, el {date(cr[0].date)} reúne {cr[0].n} adjudicaciones y el {date(cr[1].date)}{" "}
        otras {cr[1].n}. Las otras {crWeekend - crTwoDays} se reparten en una fecha más. Por método, {crMethods[0].n} de los{" "}
        {crWeekend} contratos de fin de semana son «{crMethods[0].method.toLowerCase()}» y {crMethods[1].n} «{crMethods[1].method.toLowerCase()}».
        Eso se parece más a una firma o una carga en bloque que a decisiones tomadas una por una.
      </p>
      <p>
        El patrón se repite: en Guatemala, {WEEKDAY.GT.top[0].n} de sus {rows.find((r) => r.code === "GT")!.weekend}{" "}
        contratos de fin de semana son del sábado {WEEKDAY.GT.top[0].date.slice(8)} de septiembre; en
        Brasil, {WEEKDAY.BR.top[0].n} de {rows.find((r) => r.code === "BR")!.weekend} del sábado{" "}
        {WEEKDAY.BR.top[0].date.slice(8)} de noviembre de 2025; en Chile, {WEEKDAY.CL.top[0].n}{" "}
        de {rows.find((r) => r.code === "CL")!.weekend} de un sábado de junio.
      </p>

      <h2>Colombia: el día de la semana no dice mucho</h2>
      <p>
        Colombia tiene el porcentaje más alto, {pct(co.share, 1)}, y su sábado 12 de septiembre reúne{" "}
        {WEEKDAY.CO.top[0].n} contratos. Pero la forma de toda la semana lo relativiza: la muestra
        colombiana tiene {es(WEEKDAY.CO.days[0])} contratos en lunes, {es(WEEKDAY.CO.days[3])} en jueves y
        solo uno en martes. Con una distribución así, un sábado grande no prueba que se firme más los fines de semana: la
        muestra completa se concentra en pocas fechas.
      </p>

      <Figure title="Colombia · contratos por día de la semana">
        <ColumnsChart data={weekdayData("CO")} label="Contratos de Colombia por día de la semana" locale="es" height={200} />
        <TableView caption="Ver como tabla" headers={["Día", "Contratos"]} rows={weekdayData("CO").map((d) => [d.label, d.display])} />
      </Figure>
      <Figure title="Costa Rica · contratos por día de la semana">
        <ColumnsChart data={weekdayData("CR")} label="Contratos de Costa Rica por día de la semana" locale="es" height={200} />
        <TableView caption="Ver como tabla" headers={["Día", "Contratos"]} rows={weekdayData("CR").map((d) => [d.label, d.display])} />
      </Figure>

      <h2>Paraguay: la excepción</h2>
      <p>
        <strong>Paraguay</strong> tiene {py.weekend} contratos de fin de semana ({pct(py.share, 1)}) repartidos a lo largo
        de nueve años, sin una fecha dominante: la más activa suma {py.top?.n}. Es el único país donde el fin de
        semana se comporta como una actividad dispersa, y también el único con una historia larga para comparar.
      </p>

      <h2>Qué significa y qué no</h2>
      <p>
        Un contrato fechado en domingo no es una irregularidad por sí mismo. Lo que sí vale la pena revisar es el bloque:
        cuando decenas de adjudicaciones comparten una fecha de fin de semana, lo razonable es preguntar al portal si esa
        fecha es la de adjudicación, la de publicación o la de una carga masiva. Hoy los datos no permiten distinguirlas, y
        ese es el pendiente de este estudio.
      </p>

      <Method>
        <p>
          Se cuenta el día de la semana de la fecha de adjudicación que guarda cada contrato. Cada portal llena esa fecha
          con un campo distinto: la fecha de adjudicación en firme en Costa Rica, la fecha de firma en Colombia, la fecha de
          adjudicación o, si falta, la de publicación del proceso en Paraguay y Uruguay. Por eso las cifras se comparan
          dentro de cada país y no entre países. Las muestras tienen entre uno y nueve años de datos.
        </p>
      </Method>
    </>
  );
}
