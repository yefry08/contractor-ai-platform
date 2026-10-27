"use client";

import { useState } from "react";
import { ApiError, getInquiry, type Channel, type InquiryStatus } from "@/lib/api";
import { useLanguage } from "@/lib/language-context";

export function ChannelList({ channels }: { channels: Channel[] }) {
  const { t } = useLanguage();
  return (
    <ul className="inq-channels">
      {channels.map((c) => (
        <li key={c.url}>
          <span className="inq-channel-role">{t(`inq.role.${c.role}`)}</span>
          <a href={c.url} target="_blank" rel="noopener noreferrer">
            {c.name} ↗
          </a>
        </li>
      ))}
    </ul>
  );
}

export function InquiryLookup() {
  const { t, locale } = useLanguage();
  const [code, setCode] = useState("");
  const [result, setResult] = useState<InquiryStatus | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!code.trim()) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await getInquiry(code));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("inq.errorSend"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card inq-lookup">
      <h2 className="wizard-subtitle" style={{ marginTop: 0 }}>
        {t("inq.lookupTitle")}
      </h2>
      <form className="filters" onSubmit={onSubmit}>
        <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="CAI-XXXXXXXX" maxLength={20} aria-label={t("inq.lookupTitle")} />
        <button type="submit" disabled={loading}>
          {t("inq.lookup")}
        </button>
      </form>
      {error && <div className="wizard-warning">{error}</div>}
      {result === null && <p className="wizard-note">{t("inq.notFound")}</p>}
      {result && (
        <div className="inq-status">
          <p>
            <strong>{result.code}</strong> · {t(`inq.kind.${result.kind}`)} ·{" "}
            <span className={`inq-badge inq-badge-${result.status}`}>{t(`inq.status.${result.status}`)}</span>
          </p>
          <p className="wizard-note">
            {t("inq.filedOn", { date: new Date(result.created_at + "Z").toLocaleDateString(locale, { dateStyle: "long" }) })}
          </p>
          {result.response && (
            <blockquote className="inq-response">
              <strong>{t("inq.teamResponse")}</strong>
              <p>{result.response}</p>
            </blockquote>
          )}
          <ChannelList channels={result.channels} />
        </div>
      )}
    </div>
  );
}
