import { notFound } from "next/navigation";
import { getInstitution } from "@/lib/api";
import { COUNTRY_NAMES } from "@/lib/countries";
import { getServerT } from "@/lib/i18n-server";
import { FailuresPanel, OpenCalls, SectorBars, money } from "@/components/territory-parts";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const p = await getInstitution((await params).id).catch(() => null);
  return {
    title: p ? `${p.name}: en qué gasta y qué está fallando — Contractor AI` : "Institución — Contractor AI",
    description: "En qué gasta una institución pública, qué alertas tienen sus contratos y qué llamados tiene abiertos.",
  };
}

export default async function InstitutionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [{ t, locale }, p] = await Promise.all([getServerT(), getInstitution(id).catch(() => undefined)]);
  if (p === null) notFound();
  if (!p) return <div className="wizard-warning">{t("terr.error")}</div>;

  const country = COUNTRY_NAMES[p.country_code] ?? p.country_code;
  const inquiryHref = `/reclamos?${new URLSearchParams({ pais: p.country_code, institucion: p.name, tipo: "consulta" })}`;

  return (
    <>
      <p className="terr-crumbs">
        <a href="/territorios">{t("nav.territories")}</a> › <a href={`/territorios?country=${p.country_code}`}>{country}</a>
      </p>
      <p className="datos-eyebrow">{p.local_government ? t("terr.localGov") : t("terr.institution")}</p>
      <h1 className="datos-title">{p.name}</h1>
      <p className="subtitle datos-lead">
        {t("terr.institutionSummary", { n: p.contracts.toLocaleString(locale) })}
        {p.median_amount !== null && <> {t("terr.medianIs", { v: money(p.median_amount, p.currency, locale) })}</>}
      </p>
      {p.territory ? (
        <p className="terr-disclaimer">
          {t("terr.seeNeeds")} <a href={`/territorios/${p.territory.id}`}>{p.territory.name} →</a>
        </p>
      ) : (
        <p className="terr-disclaimer">{t("terr.noTerritory")}</p>
      )}

      <section className="terr-section">
        <h2 className="wizard-subtitle">{t("terr.failingTitle")}</h2>
        <FailuresPanel f={p.failures} t={t} locale={locale} inquiryHref={inquiryHref} />
      </section>

      <section className="terr-section">
        <h2 className="wizard-subtitle">{t("terr.spendTitle")}</h2>
        <p className="wizard-note">{t("terr.spendLead", { n: p.contracts.toLocaleString(locale) })}</p>
        <SectorBars sectors={p.spending} t={t} locale={locale} showNational={false} />
      </section>

      {p.open_calls.length > 0 && (
        <section className="terr-section">
          <h2 className="wizard-subtitle">{t("terr.callsTitle")}</h2>
          <OpenCalls calls={p.open_calls} t={t} locale={locale} />
        </section>
      )}

      <section className="terr-section terr-method">
        <h2 className="wizard-subtitle">{t("terr.methodTitle")}</h2>
        <ul>
          <li>{t("terr.method3")}</li>
          <li>{t("terr.method4")}</li>
        </ul>
      </section>
    </>
  );
}
