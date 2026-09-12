"use client";

import { useState } from "react";
import { ApiError, CitizenReport, submitCitizenReport } from "@/lib/api";
import { useLanguage } from "@/lib/language-context";

export function CitizenReports({ contractId, initialReports }: { contractId: string; initialReports: CitizenReport[] }) {
  const { t, locale } = useLanguage();
  const [reports, setReports] = useState(initialReports);
  const [comment, setComment] = useState("");
  const [stance, setStance] = useState<"flag" | "context">("flag");
  const [website, setWebsite] = useState(""); // honeypot
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  function fmtDate(iso: string) {
    return new Date(iso).toLocaleDateString(locale, { year: "numeric", month: "short", day: "numeric" });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (comment.trim().length < 5) {
      setError(t("citizen.tooShort"));
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const created = await submitCitizenReport(contractId, { comment: comment.trim(), stance, website });
      if (created.id !== "0") {
        setReports((prev) => [created, ...prev]);
      }
      setComment("");
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("citizen.sendError"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>{t("citizen.title")}</h2>
      <p className="wizard-note" style={{ marginBottom: 16 }}>
        {t("citizen.lead")}
      </p>

      {reports.length > 0 && (
        <ul className="citizen-report-list">
          {reports.map((r) => (
            <li key={r.id} className="citizen-report-item">
              <span className={`badge ${r.stance === "flag" ? "wizard-verdict-revisar" : "wizard-verdict-normal"}`}>
                {r.stance === "flag" ? t("citizen.flagBadge") : t("citizen.contextBadge")}
              </span>
              <p>{r.comment}</p>
              <span className="citizen-report-date">{fmtDate(r.created_at)}</span>
            </li>
          ))}
        </ul>
      )}

      <form className="citizen-report-form" onSubmit={handleSubmit}>
        <div className="wizard-row" style={{ marginBottom: 10 }}>
          <label style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
            <input type="radio" name="stance" checked={stance === "flag"} onChange={() => setStance("flag")} />
            {t("citizen.flagRadio")}
          </label>
          <label style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
            <input type="radio" name="stance" checked={stance === "context"} onChange={() => setStance("context")} />
            {t("citizen.contextRadio")}
          </label>
        </div>

        <textarea
          className="wizard-input citizen-report-textarea"
          placeholder={t("citizen.placeholder")}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          maxLength={1000}
          rows={3}
        />

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

        {error && <div className="wizard-warning">{error}</div>}
        {done && !error && <div className="wizard-note">{t("citizen.thanks")}</div>}

        <button type="submit" className="wizard-btn-primary" disabled={submitting}>
          {submitting ? t("citizen.sending") : t("citizen.send")}
        </button>
      </form>
    </div>
  );
}
