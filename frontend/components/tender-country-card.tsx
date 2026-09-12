"use client";

import { useEffect, useState } from "react";
import { ApiError, TenderBenchmark, TenderCategory, TenderPortal, getTenderBenchmark } from "@/lib/api";
import { useLanguage } from "@/lib/language-context";

export function TenderCountryCard({ portal, categories }: { portal: TenderPortal; categories: TenderCategory[] }) {
  const { t, locale } = useLanguage();
  const [category, setCategory] = useState(categories[0]?.category_code ?? "");
  const [benchmark, setBenchmark] = useState<TenderBenchmark | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function fmtAmount(n: number, currency: string | null) {
    return `${Math.round(n).toLocaleString(locale)} ${currency ?? ""}`.trim();
  }

  // The <select> starts pre-set to the first category, but onChange only
  // fires on an actual change -- without this, a visitor who never touches
  // the dropdown would see a category selected with no benchmark ever shown.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (categories[0]?.category_code) loadBenchmark(categories[0].category_code);
  }, []);

  async function loadBenchmark(nextCategory: string) {
    setCategory(nextCategory);
    setBenchmark(null);
    setError(null);
    if (!nextCategory) return;
    setLoading(true);
    try {
      const result = await getTenderBenchmark(portal.country_code, nextCategory);
      setBenchmark(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("tenders.benchmarkError"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card tender-card">
      <h3 className="tender-card-title">{portal.country_name}</h3>

      {categories.length === 0 ? (
        <p className="wizard-note">{t("tenders.noCategories")}</p>
      ) : (
        <>
          <label className="tender-select-label">
            {t("tenders.category")}
            <select value={category} onChange={(e) => loadBenchmark(e.target.value)}>
              {categories.map((c) => (
                <option key={c.category_code} value={c.category_code}>
                  {c.category_code} ({c.contracts.toLocaleString(locale)})
                </option>
              ))}
            </select>
          </label>

          {loading && <p className="wizard-note">{t("tenders.calculating")}</p>}
          {error && <div className="wizard-warning">{error}</div>}

          {benchmark && !loading && (
            <div className="tender-benchmark">
              <div className="tender-benchmark-median">
                <span className="tender-benchmark-value">{fmtAmount(benchmark.median_amount, benchmark.currency)}</span>
                <span className="tender-benchmark-label">{t("tenders.medianPrice")}</span>
              </div>
              <p className="wizard-note">
                {t("tenders.typicalRange", {
                  low: fmtAmount(benchmark.typical_low, benchmark.currency),
                  high: fmtAmount(benchmark.typical_high, benchmark.currency),
                  n: benchmark.sample_size.toLocaleString(locale),
                })}
              </p>
            </div>
          )}
        </>
      )}

      <a
        href={portal.portal_url}
        target="_blank"
        rel="noopener noreferrer"
        className="wizard-btn-primary tender-portal-link"
      >
        {t("tenders.portalLink", { portal: portal.portal_name })} →
      </a>
    </div>
  );
}
