"use client";

import { useState } from "react";
import { ApiError, CitizenReport, submitCitizenReport } from "@/lib/api";

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("es", { year: "numeric", month: "short", day: "numeric" });
}

export function CitizenReports({ contractId, initialReports }: { contractId: string; initialReports: CitizenReport[] }) {
  const [reports, setReports] = useState(initialReports);
  const [comment, setComment] = useState("");
  const [stance, setStance] = useState<"flag" | "context">("flag");
  const [website, setWebsite] = useState(""); // honeypot
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (comment.trim().length < 5) {
      setError("Contá un poco más — mínimo 5 caracteres.");
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
      setError(err instanceof ApiError ? err.message : "No se pudo enviar el reporte. Probá de nuevo.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>Participación ciudadana</h2>
      <p className="wizard-note" style={{ marginBottom: 16 }}>
        Este es un espacio para que cualquier persona deje contexto sobre este contrato —
        señalando algo que parece irregular, o aportando información que lo explica. No es un
        canal de denuncia formal ni reemplaza a las autoridades competentes.
      </p>

      {reports.length > 0 && (
        <ul className="citizen-report-list">
          {reports.map((r) => (
            <li key={r.id} className="citizen-report-item">
              <span className={`badge ${r.stance === "flag" ? "wizard-verdict-revisar" : "wizard-verdict-normal"}`}>
                {r.stance === "flag" ? "Señala un problema" : "Aporta contexto"}
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
            Señalar un problema
          </label>
          <label style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
            <input type="radio" name="stance" checked={stance === "context"} onChange={() => setStance("context")} />
            Aportar contexto
          </label>
        </div>

        <textarea
          className="wizard-input citizen-report-textarea"
          placeholder="¿Qué observás sobre este contrato?"
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
        {done && !error && <div className="wizard-note">Gracias — tu aporte ya se ve en la lista de arriba.</div>}

        <button type="submit" className="wizard-btn-primary" disabled={submitting}>
          {submitting ? "Enviando…" : "Enviar"}
        </button>
      </form>
    </div>
  );
}
