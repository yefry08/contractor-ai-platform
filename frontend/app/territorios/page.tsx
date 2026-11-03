import { getTerritoriesOverview, listInstitutions, listTerritories } from "@/lib/api";
import { COUNTRIES, COUNTRY_NAMES } from "@/lib/countries";
import { getServerT } from "@/lib/i18n-server";
import { pct, value } from "@/components/territory-parts";

export const metadata = {
  title: "Territorios: qué necesita cada lugar — Contractor AI",
  description:
    "Qué necesita cada departamento, provincia o municipio según los datos oficiales, qué está fallando en sus compras y en qué se gasta.",
};

const PAGE_SIZE = 30;
// Countries with an official needs indicator by territory, and the level to open on.
const NEEDS_LEVELS: Record<string, string[]> = { CO: ["department", "municipality"], PY: ["department", "municipality"], DO: ["region"] };

export default async function TerritoriosPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const sp = await searchParams;
  const country = (sp.country || "CO").toUpperCase();
  const levels = NEEDS_LEVELS[country] ?? [];
  const level = levels.includes(sp.level ?? "") ? sp.level! : levels[0];
  const page = Math.max(1, Number(sp.page) || 1);
  const [{ t, locale }, overview, territories, institutions] = await Promise.all([
    getServerT(),
    getTerritoriesOverview().catch(() => null),
    level
      ? listTerritories({ country, level, q: sp.q || undefined, limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE }).catch(() => null)
      : Promise.resolve(null),
    listInstitutions({ country, q: sp.iq || undefined, limit: 12 }).catch(() => null),
  ]);
  const href = (changes: Record<string, string | undefined>) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries({ ...sp, ...changes })) if (v) qs.set(k, v);
    return `/territorios?${qs.toString()}`;
  };

  return (
    <>
      <p className="datos-eyebrow">{t("terr.eyebrow")}</p>
      <h1 className="datos-title">{t("terr.title")}</h1>
      <p className="subtitle datos-lead">{t("terr.lead")}</p>

      <div className="opp-how">
        <div>
          <strong>1</strong>
          <span>{t("terr.how1")}</span>
        </div>
        <div>
          <strong>2</strong>
          <span>{t("terr.how2")}</span>
        </div>
        <div>
          <strong>3</strong>
          <span>{t("terr.how3")}</span>
        </div>
      </div>

      <p className="terr-disclaimer">{t("terr.disclaimer")}</p>

      <nav className="terr-tabs" aria-label={t("terr.countries")}>
        {COUNTRIES.map((c) => (
          <a
            key={c.code}
            href={`/territorios?country=${c.code}`}
            className={c.code === country ? "terr-tab terr-tab-on" : "terr-tab"}
            aria-current={c.code === country ? "page" : undefined}
          >
            {c.name}
            {NEEDS_LEVELS[c.code] && <span className="terr-tab-dot" title={t("terr.hasNeeds")} />}
          </a>
        ))}
      </nav>

      {!overview && <div className="wizard-warning">{t("terr.error")}</div>}

      <section className="terr-section">
        <h2 className="wizard-subtitle">{t("terr.placesTitle", { country: COUNTRY_NAMES[country] ?? country })}</h2>
        {levels.length === 0 ? (
          <p className="wizard-note">{t(country === "SV" ? "terr.noNeedsSV" : "terr.noNeeds")}</p>
        ) : (
          <>
            <form className="filters" method="get">
              <input type="hidden" name="country" value={country} />
              <input type="search" name="q" defaultValue={sp.q ?? ""} placeholder={t("terr.searchPlace")} maxLength={100} />
              {levels.length > 1 && (
                <select name="level" defaultValue={level}>
                  {levels.map((l) => (
                    <option key={l} value={l}>
                      {t(`terr.levels.${country}.${l}`)}
                    </option>
                  ))}
                </select>
              )}
              <button type="submit">{t("opps.search")}</button>
            </form>
            {territories && (
              <>
                <p className="opp-count">{t("terr.placesCount", { n: territories.total.toLocaleString(locale) })}</p>
                <div className="terr-grid">
                  {territories.items.map((p) => {
                    const h = p.headline;
                    const worse = h && h.national_value !== null && (h.worse_when === "high" ? h.value > h.national_value : h.value < h.national_value);
                    return (
                      <a key={p.id} href={`/territorios/${p.id}`} className="card terr-card">
                        <strong className="terr-card-name">{p.name}</strong>
                        {h ? (
                          <>
                            <span className={`terr-card-value${worse ? " terr-worse" : ""}`}>{value(h.value, h.unit, locale)}</span>
                            <span className="terr-card-label">{t(`terr.indicators.${h.key}`)}</span>
                            <span className="terr-meter" aria-hidden>
                              <span style={{ width: `${(h.peer_percentile ?? 0) * 100}%` }} />
                            </span>
                            <small className="terr-card-meta">
                              {h.national_value !== null
                                ? t("terr.nationalIs", { v: value(h.national_value, h.unit, locale) })
                                : t("terr.worseThan", { p: pct(h.peer_percentile, locale, 0) })}
                              {p.linked_contracts > 0 && <> · {t("terr.contractsN", { n: p.linked_contracts.toLocaleString(locale) })}</>}
                            </small>
                          </>
                        ) : (
                          <small className="terr-card-meta">{t("terr.noHeadline")}</small>
                        )}
                      </a>
                    );
                  })}
                </div>
                <div className="pagination">
                  {page > 1 && <a href={href({ page: String(page - 1) })}>← {t("common.previous")}</a>}
                  <span>
                    {page} {t("common.of")} {Math.max(1, Math.ceil(territories.total / PAGE_SIZE))}
                  </span>
                  {page * PAGE_SIZE < territories.total && <a href={href({ page: String(page + 1) })}>{t("common.next")} →</a>}
                </div>
              </>
            )}
          </>
        )}
      </section>

      <section className="terr-section">
        <h2 className="wizard-subtitle">{t("terr.institutionsTitle")}</h2>
        <p className="wizard-note">{t("terr.institutionsLead")}</p>
        <form className="filters" method="get">
          <input type="hidden" name="country" value={country} />
          <input type="search" name="iq" defaultValue={sp.iq ?? ""} placeholder={t("terr.searchInstitution")} maxLength={100} />
          <button type="submit">{t("opps.search")}</button>
        </form>
        {institutions && institutions.items.length === 0 && <p className="wizard-note">{t("terr.noInstitutions")}</p>}
        {institutions && institutions.items.length > 0 && (
          <div className="terr-grid">
            {institutions.items.map((i) => (
              <a key={i.id} href={`/territorios/institucion/${i.id}`} className="card terr-card">
                <strong className="terr-card-name">{i.name}</strong>
                {i.local_government && <span className="datos-tag terr-local">{t("terr.localGov")}</span>}
                <small className="terr-card-meta">
                  {t("terr.contractsN", { n: i.contracts.toLocaleString(locale) })} ·{" "}
                  <span className={i.anomaly_rate > 0.1 ? "opp-flag-high" : undefined}>{t("terr.alertsPct", { p: pct(i.anomaly_rate, locale) })}</span>
                </small>
              </a>
            ))}
          </div>
        )}
      </section>

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
