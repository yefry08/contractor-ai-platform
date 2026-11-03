import type { Failures, OpenCall, SectorSpend } from "@/lib/api";
import type { Vars } from "@/lib/i18n";

type T = (key: string, vars?: Vars) => string;

export function pct(n: number | null | undefined, locale: string, digits = 1) {
  if (n === null || n === undefined) return "—";
  return `${(n * 100).toLocaleString(locale, { maximumFractionDigits: digits })}%`;
}

export function value(n: number, unit: string, locale: string) {
  return `${n.toLocaleString(locale, { maximumFractionDigits: 1 })}${unit === "%" ? "%" : ` ${unit}`}`;
}

export function money(n: number, currency: string | null, locale: string) {
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

/** Share of contracts per sector here, against the national share. */
export function SectorBars({ sectors, t, locale, showNational }: { sectors: SectorSpend[]; t: T; locale: string; showNational: boolean }) {
  const max = Math.max(...sectors.map((s) => Math.max(s.contract_share, s.national_contract_share ?? 0)), 0.01);
  return (
    <div className="terr-bars">
      {sectors.map((s) => (
        <div key={s.sector} className="terr-bar-row">
          <span className="terr-bar-label">{t(`terr.sectors.${s.sector}`)}</span>
          <div className="terr-bar-track">
            <div className="terr-bar terr-bar-local" style={{ width: `${(s.contract_share / max) * 100}%` }} />
            {showNational && s.national_contract_share != null && (
              <div className="terr-bar-mark" style={{ left: `${(s.national_contract_share / max) * 100}%` }} title={t("terr.nationalShare")} />
            )}
          </div>
          <span className="terr-bar-value">
            {pct(s.contract_share, locale, 0)}
            <small> · {s.contracts.toLocaleString(locale)}</small>
          </span>
        </div>
      ))}
      {showNational && (
        <p className="terr-legend">
          <span className="terr-key terr-key-local" /> {t("terr.localShare")} <span className="terr-key terr-key-mark" /> {t("terr.nationalShare")}
        </p>
      )}
    </div>
  );
}

export function FailuresPanel({ f, t, locale, inquiryHref }: { f: Failures; t: T; locale: string; inquiryHref: string }) {
  const higher = f.anomaly_rate !== null && f.national_anomaly_rate !== null && f.anomaly_rate > f.national_anomaly_rate * 1.2;
  return (
    <>
      <div className="terr-stats">
        <div className={`terr-stat${higher ? " terr-stat-bad" : ""}`}>
          <strong>{pct(f.anomaly_rate, locale)}</strong>
          <span>{t("terr.alertRate")}</span>
          <small>{t("terr.vsNational", { v: pct(f.national_anomaly_rate, locale) })}</small>
        </div>
        <div className="terr-stat">
          <strong>{f.anomalies.toLocaleString(locale)}</strong>
          <span>{t("terr.flaggedContracts")}</span>
        </div>
        <div className="terr-stat">
          <strong>{f.inquiries.toLocaleString(locale)}</strong>
          <span>{t("terr.inquiries")}</span>
          <small>
            <a href={inquiryHref}>{t("terr.fileInquiry")}</a>
          </small>
        </div>
      </div>
      {f.flagged_contracts.length > 0 && (
        <ul className="terr-flagged">
          {f.flagged_contracts.map((c) => (
            <li key={c.contract_id}>
              <a href={`/contracts/${c.contract_id}`}>{c.title || t("terr.untitled")}</a>
              <span className="terr-flag-meta">
                {c.buyer ? `${c.buyer} · ` : ""}
                {c.amount ? money(c.amount, c.currency, locale) : ""} · {t(`terr.anomaly.${c.anomaly_type}`)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

export function OpenCalls({ calls, t, locale }: { calls: OpenCall[]; t: T; locale: string }) {
  if (!calls.length) return null;
  return (
    <ul className="terr-calls">
      {calls.map((c) => (
        <li key={c.id}>
          <a href={c.url} target="_blank" rel="noopener noreferrer">
            {c.title} ↗
          </a>
          <span className="terr-flag-meta">
            {c.buyer ? `${c.buyer} · ` : ""}
            {t("terr.closes", { date: new Date(c.deadline + "Z").toLocaleDateString(locale, { day: "numeric", month: "short" }) })}
            {c.estimated_amount ? ` · ${money(c.estimated_amount, c.currency, locale)}` : ""}
          </span>
        </li>
      ))}
    </ul>
  );
}
