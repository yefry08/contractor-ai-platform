import { COUNTRIES } from "@/lib/countries";
import { listAnomalies, ContractSummary, AnomalyWithContract } from "@/lib/api";
import { isSafeExternalUrl } from "@/lib/safe-url";
import { getServerT } from "@/lib/i18n-server";
import { fmtDeviation } from "@/lib/format";

function fmtUsd(n: number | null, locale: string) {
  if (n === null) return "—";
  return n.toLocaleString(locale, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

function fmtAmount(c: ContractSummary, locale: string) {
  if (c.amount_usd !== null) return fmtUsd(c.amount_usd, locale);
  if (c.amount_original !== null && c.currency) {
    return `${c.amount_original.toLocaleString(locale)} ${c.currency}`;
  }
  return "—";
}

// The NLP signal is already relative to its predicted price; the statistical
// one is relative to comparable contracts. Both are fractions, so both go
// through the same formatter — no z-scores on screen, they mean nothing to a
// reader and saturate at 50.
function deviationOf(a: AnomalyWithContract) {
  if (a.nlp_component !== null) return a.nlp_component;
  return a.stat_deviation ?? null;
}

export default async function AnomaliesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const limit = 25;
  const offset = Number(sp.offset ?? 0);

  const country = sp.country ?? "";
  const [data, { t, locale }] = await Promise.all([
    listAnomalies({
      country: country || undefined,
      anomaly_type: sp.anomaly_type,
      min_score: sp.min_score,
      status: "open",
      limit,
      offset,
    }),
    getServerT(),
  ]);

  function signalLabel(nlp: number | null, stat: number | null) {
    if (nlp !== null && stat !== null) return t("anomalies.signalBoth");
    if (nlp !== null) return t("anomalies.signalNlp");
    if (stat !== null) return t("anomalies.signalStat");
    return "—";
  }

  return (
    <>
      <h1>{t("anomalies.title")}</h1>
      <p className="subtitle">
        {t("anomalies.subtitle", { n: data.total.toLocaleString(locale) })}
      </p>

      <div className="note">{t("anomalies.note")}</div>

      <form className="filters" method="get">
        <select name="country" defaultValue={country}>
          <option value="">{t("home.allCountries")}</option>
          {COUNTRIES.map((c) => (
            <option key={c.code} value={c.code}>
              {c.name}
            </option>
          ))}
        </select>
        <select name="anomaly_type" defaultValue={sp.anomaly_type ?? ""}>
          <option value="">{t("anomalies.allTypes")}</option>
          <option value="overcost">{t("anomalies.overcost")}</option>
          <option value="undercost">{t("anomalies.undercost")}</option>
        </select>
        <input
          type="number"
          step="0.1"
          name="min_score"
          placeholder={t("anomalies.minScore")}
          defaultValue={sp.min_score ?? ""}
        />
        <button type="submit">{t("home.filter")}</button>
      </form>

      <table>
        <thead>
          <tr>
            <th>{t("anomalies.colContract")}</th>
            <th>{t("home.colCountry")}</th>
            <th>{t("home.colBuyer")}</th>
            <th>{t("anomalies.colType")}</th>
            <th>{t("anomalies.colSignal")}</th>
            <th>{t("anomalies.colDeviation")}</th>
            <th>{t("home.colAmount")}</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((a) => {
            const deviation = fmtDeviation(deviationOf(a), locale);
            return (
              <tr key={a.id}>
                <td>
                  <a href={`/contracts/${a.contract.id}`}>{a.contract.title ?? t("common.untitled")}</a>
                  {/* "Fuente oficial", not "ver contrato": for some countries the
                      source is the portal's home page, not this contract's page. */}
                  {isSafeExternalUrl(a.contract.source_url) && (
                    <div style={{ fontSize: "0.8rem", marginTop: "0.2rem" }}>
                      <a
                        href={a.contract.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        title={t("anomalies.sourceTitle", { country: a.contract.country_code })}
                      >
                        {t("anomalies.sourceLink")} ↗
                      </a>
                    </div>
                  )}
                </td>
                <td>{a.contract.country_code}</td>
                <td>{a.contract.buyer?.name ?? "—"}</td>
                <td>
                  <span className={`badge ${a.anomaly_type}`}>
                    {a.anomaly_type === "overcost" ? t("anomalies.overcost") : t("anomalies.undercost")}
                  </span>
                </td>
                <td>{signalLabel(a.nlp_component, a.stat_component)}</td>
                <td title={deviation?.title ?? undefined}>{deviation?.label ?? "—"}</td>
                <td>{fmtAmount(a.contract, locale)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div className="pagination">
        {offset > 0 && (
          <a href={`?${new URLSearchParams({ ...sp, offset: String(Math.max(0, offset - limit)) } as Record<string, string>)}`}>
            ← {t("common.previous")}
          </a>
        )}
        <span>
          {offset + 1}–{Math.min(offset + limit, data.total)} {t("common.of")} {data.total.toLocaleString(locale)}
        </span>
        {offset + limit < data.total && (
          <a href={`?${new URLSearchParams({ ...sp, offset: String(offset + limit) } as Record<string, string>)}`}>
            {t("common.next")} →
          </a>
        )}
      </div>
    </>
  );
}
