const STEPS = [
  {
    n: "01",
    title: "Explorás o filtrás",
    text: "Buscá contratos por país, comprador o categoría, o entrá directo a la lista de anomalías ya detectadas.",
  },
  {
    n: "02",
    title: "Comparamos la señal",
    text: "Cada contrato se contrasta contra el modelo NLP (BERT + XGBoost, Paraguay y Colombia) y contra una capa estadística robusta (mediana + MAD) que corre sobre todos los países.",
  },
  {
    n: "03",
    title: "Revisás la evidencia",
    text: "Cada alerta muestra el tipo de desviación, el comprador, la categoría y el detalle del contrato — nunca solo un puntaje aislado.",
  },
];

export function HowItWorks() {
  return (
    <section className="how-section">
      <h2 className="how-title">Cómo funciona</h2>
      <p className="how-lead">Sin conocimiento técnico. Todo el razonamiento queda a la vista.</p>
      <div className="how-grid">
        {STEPS.map((s) => (
          <div key={s.n} className="how-card">
            <span className="how-n">{s.n}</span>
            <h3>{s.title}</h3>
            <p>{s.text}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
