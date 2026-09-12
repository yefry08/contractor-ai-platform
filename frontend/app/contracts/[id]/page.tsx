import { getContract, listCitizenReports } from "@/lib/api";
import { CitizenReports } from "@/components/citizen-reports";
import { isSafeExternalUrl } from "@/lib/safe-url";
import { getServerT } from "@/lib/i18n-server";
import { fmtDeviation } from "@/lib/format";

function fmtUsd(n: number | null, locale: string) {
  if (n === null) return "—";
  return n.toLocaleString(locale, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

function fmtOriginal(n: number | null, currency: string | null, locale: string) {
  if (n === null) return "—";
  return `${n.toLocaleString(locale)} ${currency ?? ""}`.trim();
}

export default async function ContractDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const [c, reports, { t, locale }] = await Promise.all([
    getContract(id),
    listCitizenReports(id),
    getServerT(),
  ]);
  const prediction = c.predictions[0];
  const anomaly = c.anomalies[0];
  const nlpDeviation = anomaly ? fmtDeviation(anomaly.nlp_component, locale) : null;
  const statDeviation = anomaly ? fmtDeviation(anomaly.stat_deviation, locale) : null;

  return (
    <>
      <a href="/">← {t("contract.back")}</a>
      <h1>{c.title ?? t("common.untitled")}</h1>
      <p className="subtitle">
        {c.buyer?.name ?? t("contract.unknownBuyer")} · {c.country_code} ·{" "}
        {c.award_date ?? t("contract.unknownDate")}
      </p>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>{t("contract.description")}</h2>
        <p>{c.description ?? t("contract.noDescription")}</p>
        {isSafeExternalUrl(c.source_url) && (
          <p>
            <a
              href={c.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="badge"
              style={{ textDecoration: "none" }}
            >
              🔗 {t("contract.sourceLink", { country: c.country_code })}
            </a>
          </p>
        )}
        <p>
          <strong>{t("contract.method")}:</strong> {c.procurement_method ?? "—"} <br />
          <strong>{t("home.colCategory")}:</strong> {c.category_code ?? "—"} <br />
          <strong>{t("contract.amountOriginal")}:</strong>{" "}
          {fmtOriginal(c.amount_original, c.currency, locale)} <br />
          {c.amount_usd !== null && (
            <>
              <strong>{t("contract.amountUsd")}:</strong> {fmtUsd(c.amount_usd, locale)} <br />
            </>
          )}
          {c.ocid && (
            <>
              <strong>OCID:</strong> <code>{c.ocid}</code>
            </>
          )}
        </p>
      </div>

      {prediction && (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>{t("contract.predictionTitle")}</h2>
          <p>
            <strong>{t("contract.predicted")}:</strong>{" "}
            {prediction.predicted_value_usd !== null
              ? fmtUsd(prediction.predicted_value_usd, locale)
              : fmtOriginal(prediction.predicted_value_original, c.currency, locale)}
            <br />
            {prediction.range_low !== null && (
              <>
                <strong>{t("contract.range")}:</strong> {fmtUsd(prediction.range_low, locale)} –{" "}
                {fmtUsd(prediction.range_high, locale)} <br />
              </>
            )}
            <strong>{t("contract.similarity")}:</strong> {prediction.likelihood_score?.toFixed(4) ?? "—"} <br />
            <strong>{t("contract.model")}:</strong> {prediction.model_name} ({prediction.model_version})
          </p>
        </div>
      )}

      {anomaly && (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>
            <span className={`badge ${anomaly.anomaly_type}`}>
              {anomaly.anomaly_type === "overcost" ? t("anomalies.overcost") : t("anomalies.undercost")}
            </span>
          </h2>
          <p>
            {nlpDeviation && (
              <>
                {t("contract.nlpDeviation")}: <strong title={nlpDeviation.title}>{nlpDeviation.label}</strong>
                <br />
              </>
            )}
            {statDeviation && (
              <>
                {t("contract.statDeviation")}:{" "}
                <strong title={statDeviation.title}>{statDeviation.label}</strong>
              </>
            )}
          </p>
          <div className="note">
            {anomaly.nlp_component !== null && anomaly.stat_component !== null
              ? t("contract.bothSignals")
              : anomaly.nlp_component !== null
                ? t("contract.nlpOnly")
                : t("contract.statOnly")}{" "}
            {t("contract.treatAsSignal")}
          </div>
        </div>
      )}

      <CitizenReports contractId={c.id} initialReports={reports} />
    </>
  );
}
