import { ShareBarsChart, TableView } from "@/components/viz/charts";
import { DATA, Figure, Method, NAMES, Stats, es, pct } from "../ui";

export default function Article() {
  const py = DATA.signals.PY;
  const co = DATA.signals.CO;
  const flagged = (s: typeof py) => s.both + s.nlp_only + s.stat_only;
  const nlp = (s: typeof py) => s.both + s.nlp_only;
  const stat = (s: typeof py) => s.both + s.stat_only;
  const total = (s: typeof py) => flagged(s) + s.neither;

  return (
    <>
      <p className="post-lead">
        Contractor AI mira cada contrato con dos señales que no comparten nada. La primera es el modelo de IA de{" "}
        <strong>Daniel Duque Lozano</strong>: una red BERT lee la descripción del contrato y un XGBoost predice cuánto
        debería costar. La segunda es puramente estadística: compara el monto con la mediana del mismo comprador,
        categoría o país. Cuando las dos marcan el mismo contrato, la alerta es mucho más fuerte. ¿Cuántas veces pasa?
      </p>

      <Stats
        items={[
          { value: es(nlp(py)), label: "contratos de Paraguay marcados por el modelo de IA" },
          { value: es(stat(py)), label: "marcados por la capa estadística" },
          { value: es(py.both), label: "marcados por las dos a la vez" },
        ]}
      />

      <Figure title="Contratos marcados, según qué señal los marca" caption="Solo los contratos que tienen predicción del modelo de IA y al menos una alerta.">
        <ShareBarsChart
          rows={[
            { label: NAMES.PY, values: [py.nlp_only, py.both, py.stat_only] },
            { label: NAMES.CO, values: [co.nlp_only, co.both, co.stat_only] },
          ]}
          names={["Solo el modelo de IA", "Las dos señales", "Solo la estadística"]}
          label="Barras apiladas al 100%: contratos marcados solo por la IA, por las dos señales y solo por la estadística, en Paraguay y Colombia"
        />
        <TableView
          caption="Ver como tabla"
          headers={["País", "Con predicción", "Solo IA", "Las dos", "Solo estadística", "Ninguna"]}
          rows={(["PY", "CO"] as const).map((c) => {
            const s = DATA.signals[c];
            return [NAMES[c], es(total(s)), es(s.nlp_only), es(s.both), es(s.stat_only), es(s.neither)];
          })}
        />
      </Figure>

      <h2>Poca coincidencia, y está bien</h2>
      <p>
        En Paraguay, de los {es(nlp(py))} contratos que marca el modelo de IA, solo {py.both} ({pct(py.both / nlp(py))})
        también salen marcados por la estadística. En Colombia la coincidencia es mayor: {co.both} de {nlp(co)} (
        {pct(co.both / nlp(co))}).
      </p>
      <p>
        Que coincidan poco no quiere decir que una de las dos esté mal. Miden cosas distintas. El modelo de IA pregunta
        «¿cuánto cuestan los contratos que se <em>describen</em> como este?», así que marca un servicio de limpieza que
        cuesta como una obra. La estadística pregunta «¿cuánto suele pagar <em>este comprador</em> o esta categoría?», así
        que marca a una institución que de pronto paga diez veces su promedio. Dos preguntas distintas encuentran
        contratos distintos.
      </p>

      <h2>Por dónde empezar</h2>
      <p>
        Los {py.both + co.both} contratos marcados por las dos señales en Paraguay y Colombia son la lista corta: caros
        para lo que dicen ser <em>y</em> caros para quien los compró. En la página de cada contrato se ven las dos
        señales por separado, con la predicción del modelo y la mediana del grupo.
      </p>

      <h2>El modelo, abierto</h2>
      <p>
        El XGBoost original de Daniel Duque ya está publicado en Hugging Face, con su tarjeta de modelo y sus 1.554
        variables. Junto a él está el modelo estadístico de los 10 países, que cualquiera puede correr sin internet:{" "}
        <a href="https://huggingface.co/ElDoctor/contractor-ai-latam" target="_blank" rel="noopener noreferrer">
          ElDoctor/contractor-ai-latam
        </a>
        . Para probarlo en el navegador está el{" "}
        <a href="https://huggingface.co/spaces/ElDoctor/contractor-ai-analizador" target="_blank" rel="noopener noreferrer">
          analizador en línea
        </a>
        .
      </p>

      <Method>
        <p>
          Contratos con una fila en la tabla de predicciones del modelo BERT + XGBoost ({es(total(py))} de Paraguay y{" "}
          {es(total(co))} del dataset procesado de Colombia). «Marcado por la IA»: el contrato tiene una alerta con
          componente del modelo. «Marcado por la estadística»: z-score modificado sobre el logaritmo del monto mayor a 3,5
          o fuera de las cercas de Tukey, en su grupo de referencia.
        </p>
      </Method>
    </>
  );
}
