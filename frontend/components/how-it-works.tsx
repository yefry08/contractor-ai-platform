import { getServerT } from "@/lib/i18n-server";

export async function HowItWorks() {
  const { t } = await getServerT();
  const steps = ["1", "2", "3"];

  return (
    <section className="how-section">
      <h2 className="how-title">{t("how.title")}</h2>
      <p className="how-lead">{t("how.lead")}</p>
      <div className="how-grid">
        {steps.map((n) => (
          <div key={n} className="how-card">
            <span className="how-n">{`0${n}`}</span>
            <h3>{t(`how.s${n}Title`)}</h3>
            <p>{t(`how.s${n}Text`)}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
