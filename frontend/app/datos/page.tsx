import { POSTS } from "@/content/datos/posts";
import { DATA, NAMES } from "@/content/datos/ui";
import { getServerT } from "@/lib/i18n-server";

export const metadata = {
  title: "Datos de los datos — Contractor AI",
  description: "Estudios, hallazgos y comparaciones sobre los contratos públicos de 10 países de América Latina.",
};

export default async function DatosPage() {
  const { t, language, locale } = await getServerT();
  const published = POSTS.filter((p) => p.status === "published");
  const soon = POSTS.filter((p) => p.status === "soon");
  const [lead, ...rest] = published;
  const updated = new Date(DATA.generated + "T12:00:00").toLocaleDateString(locale, {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <>
      <p className="datos-eyebrow">{t("datos.eyebrow")}</p>
      <h1 className="datos-title">{t("datos.title")}</h1>
      <p className="subtitle datos-lead">
        {t("datos.lead", { n: DATA.total_contracts.toLocaleString(locale), date: updated })}
      </p>
      {language !== "es" && <p className="note">{t("datos.spanishOnly")}</p>}

      <a href={`/datos/${lead.slug}`} className="datos-feature card">
        <span className="datos-tags">
          <span className="datos-tag datos-tag-new">{t("datos.latest")}</span>
          {lead.tags.map((tag) => (
            <span key={tag} className="datos-tag">
              {tag}
            </span>
          ))}
        </span>
        <h2>{lead.title}</h2>
        <p>{lead.summary}</p>
        <span className="datos-meta">
          {lead.countries.map((c) => NAMES[c]).join(" · ")} · {t("datos.minutes", { n: lead.minutes ?? 5 })}
        </span>
      </a>

      <div className="datos-grid">
        {rest.map((p) => (
          <a key={p.slug} href={`/datos/${p.slug}`} className="datos-card card">
            <span className="datos-tags">
              {p.tags.map((tag) => (
                <span key={tag} className="datos-tag">
                  {tag}
                </span>
              ))}
            </span>
            <h3>{p.title}</h3>
            <p>{p.summary}</p>
            <span className="datos-meta">
              {p.countries.length === 10 ? t("datos.allCountries") : p.countries.map((c) => NAMES[c]).join(" · ")} ·{" "}
              {t("datos.minutes", { n: p.minutes ?? 5 })}
            </span>
          </a>
        ))}
      </div>

      <h2 className="wizard-subtitle" style={{ marginTop: 40 }}>
        {t("datos.soonTitle")}
      </h2>
      <p className="wizard-note" style={{ marginBottom: 16 }}>
        {t("datos.soonLead")}
      </p>
      <div className="datos-grid">
        {soon.map((p) => (
          <div key={p.slug} className="datos-card datos-card-soon card" aria-disabled="true">
            <span className="datos-tags">
              <span className="datos-tag datos-tag-soon">{t("datos.soon")}</span>
              {p.tags.map((tag) => (
                <span key={tag} className="datos-tag">
                  {tag}
                </span>
              ))}
            </span>
            <h3>{p.title}</h3>
            <p>{p.summary}</p>
            {p.needs && (
              <span className="datos-meta">
                {t("datos.needs")}: {p.needs}
              </span>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
