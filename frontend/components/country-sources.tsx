import { getDashboardSummary } from "@/lib/api";
import { COUNTRIES } from "@/lib/countries";
import { getServerT } from "@/lib/i18n-server";
import { fmtPct } from "@/lib/format";

// Replaces the wall of prose that used to explain each country's source. Same
// facts, plus live counts, in a form you can scan: one card per country, and
// the note says what the amounts actually are (converted, native USD, or the
// original currency) because that differs per source and changes how the
// figures should be read.
export async function CountrySources() {
  const [summary, { t, locale }] = await Promise.all([getDashboardSummary(), getServerT()]);
  const byCountry = new Map(summary.by_country.map((c) => [c.country_code, c]));

  return (
    <section className="sources-section">
      <h2 className="sources-title">{t("sources.title")}</h2>
      <p className="sources-lead">{t("sources.lead")}</p>

      <div className="sources-grid">
        {COUNTRIES.map((country) => {
          const stats = byCountry.get(country.code);
          const rate = stats?.anomaly_rate ?? 0;
          return (
            <article key={country.code} className="sources-card">
              <header className="sources-card-head">
                <span className="sources-code">{country.code}</span>
                <h3>{country.name}</h3>
              </header>

              <p className="sources-source">{country.source}</p>
              <p className="sources-note">{t(`sources.note.${country.code}`)}</p>

              <dl className="sources-figures">
                <div>
                  <dt>{t("sources.contracts")}</dt>
                  <dd>{(stats?.contracts ?? 0).toLocaleString(locale)}</dd>
                </div>
                <div>
                  <dt>{t("sources.anomalyRate")}</dt>
                  <dd>{fmtPct(rate, locale)}</dd>
                </div>
              </dl>

              <div
                className="sources-bar"
                role="img"
                aria-label={`${t("sources.anomalyRate")}: ${fmtPct(rate, locale)}`}
              >
                {/* Scaled against 30%, not the highest country, so the bars stay
                    comparable as the data changes. */}
                <span style={{ width: `${Math.min(100, (rate / 0.3) * 100)}%` }} />
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
