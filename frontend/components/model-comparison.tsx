import { getServerT } from "@/lib/i18n-server";
import { fmtDeviation } from "@/lib/format";

// Both cases are run for real against the live API (/analyze/compare) using
// contracts already ingested from Compras.gov.br for the Instituto Nacional
// de Educação de Surdos (MEC, Brazil). The test amounts (45,000 and 750,000
// BRL) are made up for this comparison; the reference group, median and
// verdict are the actual output the app produces today -- not invented for
// this page. Verified 2026-09-12:
//
//   POST /analyze/compare {country: BR, currency: BRL, amount: 45000,  category: Compras}
//     -> group_size: 43, median: 2450, zscore: 2.06, verdict: normal
//   POST /analyze/compare {country: BR, currency: BRL, amount: 750000, category: Compras}
//     -> group_size: 43, median: 2450, zscore: 4.06, verdict: revisar
//
// Case A is the interesting one: 18x the median does NOT get flagged,
// because this buyer's own real history includes purchases just as large
// (R$56,319; R$95,199) -- a generic assistant asked "is R$45,000 for 5
// printers reasonable?" has no way to know that, and the well-documented
// failure mode for that situation is a false positive from a model reasoning
// over a bare number instead of the buyer's actual spending pattern.
const CASES = [
  {
    key: "A",
    amount: 45_000,
    median: 2_450,
    n: 43,
    deviation: 1_736.73 / 100,
    verdict: "normal" as const,
  },
  {
    key: "B",
    amount: 750_000,
    median: 2_450,
    n: 43,
    deviation: 30_512.24 / 100,
    verdict: "revisar" as const,
  },
];

export async function ModelComparison() {
  const { t, locale } = await getServerT();

  const fmtBRL = (n: number) =>
    n.toLocaleString(locale, { style: "currency", currency: "BRL", maximumFractionDigits: 0 });

  return (
    <section className="model-comparison">
      <h2 className="wizard-subtitle">{t("benchmark.title")}</h2>
      <p className="wizard-note" style={{ marginBottom: 10 }}>{t("benchmark.lead")}</p>
      <div className="note" style={{ marginBottom: 20 }}>{t("benchmark.disclaimer")}</div>

      <div className="benchmark-cases">
        {CASES.map((c) => {
          const dev = fmtDeviation(c.deviation, locale)!;
          return (
            <div key={c.key} className="card benchmark-case">
              <h3 style={{ marginTop: 0 }}>{t(`benchmark.case${c.key}Title`)}</h3>
              <p className="wizard-note" style={{ marginBottom: 14 }}>{t(`benchmark.case${c.key}Desc`)}</p>

              <dl className="benchmark-figures">
                <div>
                  <dt>{t("benchmark.amount")}</dt>
                  <dd>{fmtBRL(c.amount)}</dd>
                </div>
                <div>
                  <dt>{t("benchmark.median")}</dt>
                  <dd>{fmtBRL(c.median)}</dd>
                </div>
                <div>
                  <dt>{t("benchmark.deviation")}</dt>
                  <dd title={dev.title}>{dev.label}</dd>
                </div>
              </dl>
              <p className="wizard-note" style={{ margin: "0 0 16px", fontSize: "0.8rem" }}>
                {t("benchmark.sampleSize", { n: c.n })}
              </p>

              <div className="benchmark-verdicts">
                <div className="benchmark-verdict">
                  <span className="benchmark-verdict-label">Contractor AI</span>
                  <span className={`badge wizard-verdict-${c.verdict}`}>
                    {t(c.verdict === "normal" ? "benchmark.verdictNormal" : "benchmark.verdictFlagged")}
                  </span>
                </div>
                <div className="benchmark-verdict">
                  <span className="benchmark-verdict-label">{t("benchmark.genericLabel")}</span>
                  <p className="wizard-note" style={{ margin: 0 }}>{t(`benchmark.generic${c.key}`)}</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="benchmark-table-wrap">
        <table className="benchmark-table">
          <thead>
            <tr>
              <th></th>
              <th>Contractor AI</th>
              <th>{t("benchmark.genericLabel")}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">{t("benchmark.rowSource")}</th>
              <td>{t("benchmark.rowSourceContractor")}</td>
              <td>{t("benchmark.rowSourceGeneric")}</td>
            </tr>
            <tr>
              <th scope="row">{t("benchmark.rowMethod")}</th>
              <td>{t("benchmark.rowMethodContractor")}</td>
              <td>{t("benchmark.rowMethodGeneric")}</td>
            </tr>
            <tr>
              <th scope="row">{t("benchmark.rowProof")}</th>
              <td>{t("benchmark.rowProofContractor")}</td>
              <td>{t("benchmark.rowProofGeneric")}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}
