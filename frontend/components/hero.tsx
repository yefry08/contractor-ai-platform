import { Spotlight } from "@/components/ui/spotlight";
import { SplineScene } from "@/components/ui/spline-scene";

export function Hero() {
  return (
    <section className="hero-card">
      <Spotlight className="hero-spotlight" fill="white" />

      <div className="hero-grid">
        <div className="hero-copy">
          <span className="hero-eyebrow">Desafío de Transparencia PIDA · OEA</span>
          <h1 className="hero-title">Contractor AI</h1>
          <p className="hero-lead">
            Detectamos anomalías de precio en contratación pública comparando cada
            contrato contra miles de contratos históricos similares. Buscá, filtrá y
            revisá la evidencia detrás de cada alerta, en cuatro países y contando.
          </p>
          <div className="hero-actions">
            <a href="/" className="hero-btn hero-btn-primary">
              Explorar contratos
            </a>
            <a href="/anomalies" className="hero-btn hero-btn-secondary">
              Ver anomalías detectadas
            </a>
          </div>
        </div>

        <div className="hero-scene">
          <SplineScene
            scene="https://prod.spline.design/kZDDjO5HuC9GJUM2/scene.splinecode"
            className="hero-scene-canvas"
          />
        </div>
      </div>
    </section>
  );
}
