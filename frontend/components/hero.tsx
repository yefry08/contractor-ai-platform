import { Spotlight } from "@/components/ui/spotlight";
import { SplineScene } from "@/components/ui/spline-scene";
import { COUNTRIES } from "@/lib/countries";
import { getServerT } from "@/lib/i18n-server";

export async function Hero() {
  const { t } = await getServerT();

  return (
    <section className="hero-card">
      <Spotlight className="hero-spotlight" fill="white" />

      <div className="hero-grid">
        <div className="hero-copy">
          <span className="hero-eyebrow">{t("hero.eyebrow")}</span>
          <h1 className="hero-title">Contractor AI</h1>
          <p className="hero-lead">{t("hero.lead", { count: COUNTRIES.length })}</p>
          <div className="hero-actions">
            <a href="/analyze" className="hero-btn hero-btn-primary">
              {t("nav.analyze")}
            </a>
            <a href="mailto:yefrynunez45@gmail.com" className="hero-btn hero-btn-secondary">
              {t("nav.contact")}
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
