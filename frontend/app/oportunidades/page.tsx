import { listOpportunities, listTenderPortals, type Opportunity } from "@/lib/api";
import { COUNTRY_NAMES } from "@/lib/countries";
import { getServerT } from "@/lib/i18n-server";

export const metadata = {
  title: "Oportunidades para venderle al Estado — Contractor AI",
  description: "Llamados abiertos de compras públicas en América Latina, con el historial de precios y alertas de cada institución.",
};

const PAGE_SIZE = 20;
const TIME_ZONES: Record<string, string> = {
  CO: "America/Bogota",
  BR: "America/Sao_Paulo",
  DO: "America/Santo_Domingo",
};

function money(n: number, currency: string | null, locale: string) {
  try {
    return n.toLocaleString(locale, {
      style: "currency",
      currency: currency || "USD",
      maximumFractionDigits: 0,
      notation: n >= 10_000_000 ? "compact" : "standard",
    });
  } catch {
    return `${n.toLocaleString(locale)} ${currency ?? ""}`;
  }
}

function inquiryHref(o: Opportunity) {
  const qs = new URLSearchParams({ pais: o.country_code, proceso: o.url, op: o.id, tipo: "consulta" });
  if (o.buyer_name) qs.set("institucion", o.buyer_name);
  return `/reclamos?${qs.toString()}`;
}

export default async function OportunidadesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const page = Math.max(1, Number(sp.page) || 1);
  const params = {
    country: sp.country || undefined,
    q: sp.q || undefined,
    for_smes: sp.sme === "1" || undefined,
    closing_within_days: sp.closing ? Number(sp.closing) : undefined,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  };
  const [{ t, locale }, data, portals] = await Promise.all([
    getServerT(),
    listOpportunities(params).catch(() => null),
    listTenderPortals().catch(() => []),
  ]);
  const now = Date.now();
  const covered = data ? Object.keys(data.sources) : [];
  const others = portals.filter((p) => !covered.includes(p.country_code));
  const pageHref = (n: number) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(sp)) if (v && k !== "page") qs.set(k, v);
    qs.set("page", String(n));
    return `/oportunidades?${qs.toString()}`;
  };
  const totalOpen = data ? Object.values(data.counts_by_country).reduce((a, b) => a + b, 0) : 0;

  return (
    <>
      <p className="datos-eyebrow">{t("opps.eyebrow")}</p>
      <h1 className="datos-title">{t("opps.title")}</h1>
      <p className="subtitle datos-lead">
        {t("opps.lead", { n: totalOpen.toLocaleString(locale), countries: covered.map((c) => COUNTRY_NAMES[c] ?? c).join(", ") })}
      </p>

      <div className="opp-how">
        <div>
          <strong>1</strong>
          <span>{t("opps.how1")}</span>
        </div>
        <div>
          <strong>2</strong>
          <span>{t("opps.how2")}</span>
        </div>
        <div>
          <strong>3</strong>
          <span>{t("opps.how3")}</span>
        </div>
      </div>

      <form className="filters opp-filters" method="get">
        <input type="search" name="q" defaultValue={sp.q ?? ""} placeholder={t("opps.searchPlaceholder")} maxLength={200} />
        <select name="country" defaultValue={sp.country ?? ""}>
          <option value="">{t("opps.allCountries")}</option>
          {covered.map((c) => (
            <option key={c} value={c}>
              {COUNTRY_NAMES[c] ?? c} ({(data?.counts_by_country[c] ?? 0).toLocaleString(locale)})
            </option>
          ))}
        </select>
        <select name="closing" defaultValue={sp.closing ?? ""}>
          <option value="">{t("opps.anyDeadline")}</option>
          <option value="3">{t("opps.closingIn", { n: 3 })}</option>
          <option value="7">{t("opps.closingIn", { n: 7 })}</option>
          <option value="30">{t("opps.closingIn", { n: 30 })}</option>
        </select>
        <label className="opp-check">
          <input type="checkbox" name="sme" value="1" defaultChecked={sp.sme === "1"} />
          {t("opps.smeOnly")}
        </label>
        <button type="submit">{t("opps.search")}</button>
      </form>

      {!data && <div className="wizard-warning">{t("opps.error")}</div>}
      {data && data.items.length === 0 && <p className="wizard-note">{t("opps.empty")}</p>}

      {data && data.items.length > 0 && (
        <>
          <p className="opp-count">{t("opps.results", { n: data.total.toLocaleString(locale) })}</p>
          <div className="opp-list">
            {data.items.map((o) => {
              const ms = new Date(o.deadline + "Z").getTime() - now;
              const days = Math.floor(ms / 86_400_000);
              const urgent = days < 3;
              const deadlineText = new Date(o.deadline + "Z").toLocaleString(locale, {
                timeZone: TIME_ZONES[o.country_code],
                day: "numeric",
                month: "short",
                hour: "2-digit",
                minute: "2-digit",
              });
              const h = o.buyer_history;
              return (
                <article key={o.id} className="card opp-card">
                  <div className="opp-top">
                    <span className="datos-tag">{COUNTRY_NAMES[o.country_code] ?? o.country_code}</span>
                    {o.for_smes && <span className="datos-tag opp-sme">{t("opps.smeBadge")}</span>}
                    <span className={`opp-deadline${urgent ? " opp-deadline-urgent" : ""}`}>
                      {days <= 0 ? t("opps.closesToday") : days === 1 ? t("opps.closesTomorrow") : t("opps.closesInDays", { n: days })}
                      <small> · {deadlineText}</small>
                    </span>
                  </div>
                  <h3 className="opp-title">{o.title}</h3>
                  {o.description && o.description !== o.title && <p className="opp-desc">{o.description}</p>}
                  <dl className="opp-facts">
                    {o.buyer_name && (
                      <div>
                        <dt>{t("opps.buyer")}</dt>
                        <dd>
                          {o.buyer_name}
                          {o.region ? ` · ${o.region}` : ""}
                        </dd>
                      </div>
                    )}
                    <div>
                      <dt>{t("opps.estimated")}</dt>
                      <dd>{o.estimated_amount ? money(o.estimated_amount, o.currency, locale) : t("opps.notPublished")}</dd>
                    </div>
                    {o.procurement_method && (
                      <div>
                        <dt>{t("opps.method")}</dt>
                        <dd>{o.procurement_method}</dd>
                      </div>
                    )}
                  </dl>
                  <div className="opp-history">
                    {h ? (
                      <>
                        <strong>{t("opps.historyTitle")}</strong>{" "}
                        {h.contracts === 1
                          ? t("opps.historyContractsOne")
                          : t("opps.historyContracts", { n: h.contracts.toLocaleString(locale) })}
                        {h.median_amount !== null && <> · {t("opps.historyMedian", { amount: money(h.median_amount, h.currency, locale) })}</>}
                        {h.anomaly_rate !== null && (
                          <>
                            {" · "}
                            <span className={h.anomaly_rate > 0.1 ? "opp-flag-high" : undefined}>
                              {t("opps.historyFlagged", { pct: (h.anomaly_rate * 100).toLocaleString(locale, { maximumFractionDigits: 1 }) })}
                            </span>
                          </>
                        )}
                      </>
                    ) : (
                      <span>{t("opps.noHistory")}</span>
                    )}
                  </div>
                  <div className="opp-actions">
                    <a className="wizard-btn-primary opp-go" href={o.url} target="_blank" rel="noopener noreferrer">
                      {t("opps.goToPortal")} ↗
                    </a>
                    <a className="opp-inquiry" href={inquiryHref(o)}>
                      {t("opps.somethingOff")}
                    </a>
                  </div>
                </article>
              );
            })}
          </div>

          <div className="pagination">
            {page > 1 && <a href={pageHref(page - 1)}>← {t("common.previous")}</a>}
            <span>
              {page} {t("common.of")} {Math.max(1, Math.ceil(data.total / PAGE_SIZE)).toLocaleString(locale)}
            </span>
            {page * PAGE_SIZE < data.total && <a href={pageHref(page + 1)}>{t("common.next")} →</a>}
          </div>
        </>
      )}

      <section className="opp-more">
        <h2 className="wizard-subtitle">{t("opps.otherCountriesTitle")}</h2>
        <p className="wizard-note">{t("opps.otherCountriesLead")}</p>
        <div className="opp-portals">
          {others.map((p) => (
            <a key={p.country_code} className="card opp-portal" href={p.portal_url} target="_blank" rel="noopener noreferrer">
              <strong>{p.country_name}</strong>
              <span>{p.portal_name} ↗</span>
            </a>
          ))}
        </div>
        <p className="wizard-note" style={{ marginTop: 16 }}>
          {t("opps.priceToolLead")} <a href="/tenders">{t("opps.priceToolLink")}</a>
        </p>
        <p className="opp-sources">
          {t("opps.sources")}: {Object.values(data?.sources ?? {}).join(" · ")}
        </p>
      </section>
    </>
  );
}
