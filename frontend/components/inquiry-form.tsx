"use client";

import { useState } from "react";
import { ApiError, submitInquiry, type InquiryKind, type InquiryReceipt } from "@/lib/api";
import { COUNTRIES } from "@/lib/countries";
import { useLanguage } from "@/lib/language-context";
import { Turnstile, turnstileEnabled } from "@/components/turnstile";
import { ChannelList } from "@/components/inquiry-lookup";

const KINDS: InquiryKind[] = ["consulta", "reclamo", "alerta"];

export function InquiryForm({
  initial,
}: {
  initial: { kind?: string; country?: string; process?: string; institution?: string; opportunityId?: string; contractId?: string };
}) {
  const { t } = useLanguage();
  const [kind, setKind] = useState<InquiryKind>(KINDS.includes(initial.kind as InquiryKind) ? (initial.kind as InquiryKind) : "consulta");
  const [country, setCountry] = useState(COUNTRIES.some((c) => c.code === initial.country) ? initial.country! : "");
  const [processRef, setProcessRef] = useState(initial.process ?? "");
  const [institution, setInstitution] = useState(initial.institution ?? "");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [email, setEmail] = useState("");
  const [consent, setConsent] = useState(false);
  const [website, setWebsite] = useState(""); // honeypot
  const [token, setToken] = useState<string | null>(null);
  const [resetKey, setResetKey] = useState(0);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<InquiryReceipt | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!country) return setError(t("inq.errorCountry"));
    if (subject.trim().length < 5) return setError(t("inq.errorSubject"));
    if (body.trim().length < 20) return setError(t("inq.errorBody"));
    if (!consent) return setError(t("inq.errorConsent"));
    setSending(true);
    try {
      const r = await submitInquiry({
        kind,
        country_code: country,
        process_reference: processRef.trim() || undefined,
        institution: institution.trim() || undefined,
        opportunity_id: initial.opportunityId,
        contract_id: initial.contractId,
        subject: subject.trim(),
        body: body.trim(),
        contact_email: email.trim() || undefined,
        website,
        turnstile_token: token,
      });
      setReceipt(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("inq.errorSend"));
    } finally {
      setSending(false);
      setResetKey((k) => k + 1);
    }
  }

  if (receipt) {
    return (
      <div className="card inq-receipt" role="status">
        <p className="inq-receipt-eyebrow">{t("inq.receivedTitle")}</p>
        <p className="inq-code">{receipt.code}</p>
        <p className="wizard-note">{t("inq.receivedLead")}</p>
        <h3>{t("inq.officialTitle")}</h3>
        <p className="wizard-note">{t("inq.officialLead")}</p>
        <ChannelList channels={receipt.channels} />
        <button type="button" className="wizard-btn-secondary" onClick={() => window.location.assign("/reclamos")}>
          {t("inq.another")}
        </button>
      </div>
    );
  }

  return (
    <form className="card inq-form" onSubmit={onSubmit} noValidate>
      <fieldset className="inq-kinds">
        <legend>{t("inq.kindLegend")}</legend>
        {KINDS.map((k) => (
          <label key={k} className={`inq-kind${kind === k ? " inq-kind-on" : ""}`}>
            <input type="radio" name="kind" value={k} checked={kind === k} onChange={() => setKind(k)} />
            <strong>{t(`inq.kind.${k}`)}</strong>
            <span>{t(`inq.kindHelp.${k}`)}</span>
          </label>
        ))}
      </fieldset>

      <div className="inq-grid">
        <label>
          {t("inq.country")}
          <select value={country} onChange={(e) => setCountry(e.target.value)} required>
            <option value="">{t("inq.choose")}</option>
            {COUNTRIES.map((c) => (
              <option key={c.code} value={c.code}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("inq.institution")}
          <input value={institution} onChange={(e) => setInstitution(e.target.value)} maxLength={300} placeholder={t("inq.optional")} />
        </label>
        <label className="inq-wide">
          {t("inq.process")}
          <input value={processRef} onChange={(e) => setProcessRef(e.target.value)} maxLength={600} placeholder={t("inq.processPlaceholder")} />
        </label>
        <label className="inq-wide">
          {t("inq.subject")}
          <input value={subject} onChange={(e) => setSubject(e.target.value)} maxLength={200} required />
        </label>
        <label className="inq-wide">
          {t("inq.body")}
          <textarea value={body} onChange={(e) => setBody(e.target.value)} maxLength={5000} rows={6} required placeholder={t("inq.bodyPlaceholder")} />
          <small className="inq-counter">{body.length.toLocaleString()} / 5.000</small>
        </label>
        <label className="inq-wide">
          {t("inq.email")}
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} maxLength={200} placeholder={t("inq.emailPlaceholder")} autoComplete="email" />
        </label>
      </div>

      <input
        type="text"
        name="website"
        value={website}
        onChange={(e) => setWebsite(e.target.value)}
        className="citizen-report-honeypot"
        tabIndex={-1}
        autoComplete="off"
        aria-hidden="true"
      />

      <label className="inq-consent">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>{t("inq.consent")}</span>
      </label>

      <Turnstile onToken={setToken} resetKey={resetKey} />

      {error && <div className="wizard-warning">{error}</div>}

      <button type="submit" className="wizard-btn-primary" disabled={sending || (turnstileEnabled && !token)}>
        {sending ? t("inq.sending") : t("inq.send")}
      </button>
      <p className="inq-privacy">{t("inq.privacy")}</p>
    </form>
  );
}
