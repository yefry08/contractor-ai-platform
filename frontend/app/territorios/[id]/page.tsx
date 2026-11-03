import { notFound } from "next/navigation";
import { getTerritory } from "@/lib/api";
import { COUNTRY_NAMES } from "@/lib/countries";
import { getServerT } from "@/lib/i18n-server";
import { FailuresPanel, OpenCalls, SectorBars, pct, value } from "@/components/territory-parts";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const p = await getTerritory((await params).id).catch(() => null);
  return {
    title: p ? `${p.name}: qué necesita y qué está fallando — Contractor AI` : "Territorio — Contractor AI",
    description: "Necesidades según los datos oficiales, alertas en sus compras públicas y en qué se gasta.",
  };
}

export default async function TerritoryPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [{ t, locale }, p] = await Promise.all([getServerT(), getTerritory(id).catch(() => undefined)]);
  if (p === null) notFound();
  if (!p) return <div className="wizard-warning">{t("terr.error")}</div>;

  const country = COUNTRY_NAMES[p.country_code] ?? p.country_code;
  const levelName = t(`terr.levels.${p.country_code}.${p.level}`);
  const peers = t(`terr.peers.${p.country_code}.${p.level}`);
  const hasSpend = p.spending.linked_contracts > 0;
  const inquiryHref = `/reclamos?${new URLSearchParams({ pais: p.country_code, institucion: p.name, tipo: "consulta" })}`;
  const top = p.priorities[0];

  return (
    <>
      <p className="terr-crumbs">
        <a href="/territorios">{t("nav.territories")}</a> › <a href={`/territorios?country=${p.country_code}`}>{country}</a>
        {p.parent && (
          <>
            {" "}
            › <a href={`/territorios/${p.parent.id}`}>{p.parent.name}</a>
          </>
        )}
      </p>
      <p className="datos-eyebrow">{levelName}</p>
      <h1 className="datos-title">{p.name}</h1>
      {top && (
        <p className="subtitle datos-lead">
          {t(top.peer_percentile === 1 ? "terr.summaryWorst" : "terr.summary", {
            need: t(`terr.indicators.${top.key}`).toLowerCase(),
            p: pct(top.peer_percentile, locale, 0),
            peers,
          })}
        </p>
      )}
      <p className="terr-disclaimer">{t("terr.disclaimer")}</p>

      <section className="terr-section">
        <h2 className="wizard-subtitle">1. {t("terr.needsTitle")}</h2>
        <p className="wizard-note">{t("terr.needsLead", { peers })}</p>
        {p.priorities.length === 0 && <p className="wizard-note">{t("terr.noIndicators")}</p>}
        <ol className="terr-priorities">
          {p.priorities.map((x, i) => {
            const lowSpend =
              x.local_contract_share !== null && x.national_contract_share !== null && x.local_contract_share < x.national_contract_share;
            return (
              <li key={x.key} className="card terr-priority">
                <div className="terr-priority-head">
                  <span className="terr-rank">{i + 1}</span>
                  <div>
                    <strong>{t(`terr.indicators.${x.key}`)}</strong>
                    <span className="terr-sector">{t(`terr.sectors.${x.sector}`)}</span>
                  </div>
                  <span className="terr-priority-value">{value(x.value, x.unit, locale)}</span>
                </div>
                <span className="terr-meter" aria-hidden>
                  <span style={{ width: `${(x.peer_percentile ?? 0) * 100}%` }} />
                </span>
                <p className="terr-priority-facts">
                  {x.peer_percentile === 1
                    ? t("terr.worstOfPeers", { peers })
                    : t("terr.worseThanPeers", { p: pct(x.peer_percentile, locale, 0), peers })}
                  {x.national_value !== null && <> · {t("terr.nationalIs", { v: value(x.national_value, x.unit, locale) })}</>}
                  {x.worse_when === "low" && <> · {t("terr.higherIsBetter")}</>}
                </p>
                {x.local_contract_share !== null && (
                  <p className={`terr-priority-spend${lowSpend ? " terr-worse" : ""}`}>
                    {t("terr.spendShare", {
                      local: pct(x.local_contract_share, locale),
                      national: pct(x.national_contract_share, locale),
                      sector: t(`terr.sectors.${x.sector}`).toLowerCase(),
                    })}
                    {lowSpend && <strong> · {t("terr.lowSpend")}</strong>}
                  </p>
                )}
                <a className="terr-source" href={x.source_url} target="_blank" rel="noopener noreferrer">
                  {x.source}, {x.year} ↗
                </a>
              </li>
            );
          })}
        </ol>
      </section>

      <section className="terr-section">
        <h2 className="wizard-subtitle">2. {t("terr.failingTitle")}</h2>
        {p.worsening.length > 0 && (
          <ul className="terr-worsening">
            {p.worsening.map((w) => (
              <li key={w.key}>
                <strong>{t(`terr.indicators.${w.key}`)}</strong>{" "}
                {t("terr.worsened", {
                  from: value(w.previous_value, w.unit, locale),
                  to: value(w.value, w.unit, locale),
                  y0: w.previous_year,
                  y1: w.year,
                })}
              </li>
            ))}
          </ul>
        )}
        {hasSpend ? (
          <FailuresPanel f={p.failures} t={t} locale={locale} inquiryHref={inquiryHref} />
        ) : (
          <p className="wizard-note">{t("terr.noContracts")}</p>
        )}
      </section>

      <section className="terr-section">
        <h2 className="wizard-subtitle">3. {t("terr.spendTitle")}</h2>
        {hasSpend ? (
          <>
            <p className="wizard-note">{t("terr.spendLead", { n: p.spending.linked_contracts.toLocaleString(locale) })}</p>
            <SectorBars sectors={p.spending.sectors} t={t} locale={locale} showNational />
          </>
        ) : (
          <p className="wizard-note">{t("terr.noContracts")}</p>
        )}
      </section>

      {p.open_calls.length > 0 && (
        <section className="terr-section">
          <h2 className="wizard-subtitle">{t("terr.callsTitle")}</h2>
          <OpenCalls calls={p.open_calls} t={t} locale={locale} />
          <p className="wizard-note">
            <a href={`/oportunidades?country=${p.country_code}`}>{t("terr.allCalls")}</a>
          </p>
        </section>
      )}

      {p.indicators.length > 0 && (
        <section className="terr-section">
          <h2 className="wizard-subtitle">{t("terr.allIndicators")}</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t("terr.indicator")}</th>
                  <th>{p.name}</th>
                  <th>{t("terr.national")}</th>
                  <th>{t("terr.year")}</th>
                  <th>{t("terr.source")}</th>
                </tr>
              </thead>
              <tbody>
                {p.indicators.map((x) => (
                  <tr key={x.key}>
                    <td>{t(`terr.indicators.${x.key}`)}</td>
                    <td>{value(x.value, x.unit, locale)}</td>
                    <td>{x.national_value !== null ? value(x.national_value, x.unit, locale) : "—"}</td>
                    <td>{x.year}</td>
                    <td>
                      <a href={x.source_url} target="_blank" rel="noopener noreferrer">
                        {x.source} ↗
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="terr-section terr-method">
        <h2 className="wizard-subtitle">{t("terr.methodTitle")}</h2>
        <ul>
          <li>{t("terr.method1")}</li>
          <li>{t("terr.method2")}</li>
          <li>{t("terr.method3")}</li>
          <li>{t("terr.method4")}</li>
        </ul>
      </section>
    </>
  );
}
