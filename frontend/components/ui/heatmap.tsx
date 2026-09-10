"use client";

import { Fragment, useRef, useState } from "react";
import type { CountryYearCell } from "@/lib/api";
import { COUNTRIES } from "@/lib/countries";
import { useLanguage } from "@/lib/language-context";

// Below this many contracts a cell's rate swings on one or two contracts.
export const MIN_RELIABLE_CONTRACTS = 20;

// Fixed bin edges, not scaled to the max, so a colour means the same rate on every filter and dataset.
const BIN_EDGES = [0, 0.025, 0.05, 0.1, 0.15, 0.2, 0.3];

function binOf(rate: number): number {
  let bin = 0;
  for (let i = 0; i < BIN_EDGES.length; i++) if (rate >= BIN_EDGES[i]) bin = i;
  return bin;
}

type Align = "start" | "center" | "end";
type Hover = { cell: CountryYearCell; x: number; y: number; align: Align };

export function Heatmap({ cells }: { cells: CountryYearCell[] }) {
  const { t, locale } = useLanguage();
  const rootRef = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<Hover | null>(null);

  if (cells.length === 0) {
    return <p className="heatmap-note">{t("heatmap.empty")}</p>;
  }

  const pct = (rate: number) =>
    `${(rate * 100).toLocaleString(locale, { maximumFractionDigits: 1 })}%`;
  const names: Record<string, string> = Object.fromEntries(COUNTRIES.map((c) => [c.code, c.name]));
  const nameOf = (code: string) => names[code] ?? code;

  const byKey = new Map(cells.map((c) => [`${c.country_code}-${c.year}`, c]));
  const present = new Set(cells.map((c) => c.country_code));
  const rows = [
    ...COUNTRIES.map((c) => c.code).filter((code) => present.has(code)),
    ...[...present].filter((code) => !(code in names)).sort(),
  ];
  const minYear = Math.min(...cells.map((c) => c.year));
  const maxYear = Math.max(...cells.map((c) => c.year));
  const years = Array.from({ length: maxYear - minYear + 1 }, (_, i) => minYear + i);

  const describe = (cell: CountryYearCell) =>
    `${nameOf(cell.country_code)} ${cell.year}: ${t("heatmap.tooltipRate")} ${pct(cell.anomaly_rate)}, ` +
    t("heatmap.tooltipCount", { a: cell.anomalies.toLocaleString(locale), n: cell.contracts.toLocaleString(locale) }) +
    (cell.contracts < MIN_RELIABLE_CONTRACTS ? `. ${t("heatmap.tooltipSmall")}` : "");

  const show = (el: HTMLElement, cell: CountryYearCell) => {
    const root = rootRef.current;
    if (!root) return;
    const r = el.getBoundingClientRect();
    const o = root.getBoundingClientRect();
    const center = r.left - o.left + r.width / 2;
    // Near an edge, pin the tooltip to the cell's outer side so it can't spill out of the card.
    const align: Align = center < o.width * 0.25 ? "start" : center > o.width * 0.75 ? "end" : "center";
    const x = align === "start" ? r.left - o.left : align === "end" ? r.right - o.left : center;
    setHover({ cell, x, y: r.top - o.top, align });
  };

  const legendLabels = BIN_EDGES.map((edge, i) =>
    i === BIN_EDGES.length - 1 ? `${pct(edge)}+` : pct(edge),
  );

  return (
    <div className="heatmap" ref={rootRef}>
      <div className="heatmap-scroll" onPointerLeave={() => setHover(null)}>
        <div
          className="heatmap-grid"
          style={{ gridTemplateColumns: `minmax(96px, auto) repeat(${years.length}, minmax(26px, 1fr))` }}
        >
          <span />
          {years.map((y) => (
            <span key={y} className="heatmap-col-label">
              {y}
            </span>
          ))}

          {rows.map((code) => (
            <Fragment key={code}>
              <span className="heatmap-row-label" title={nameOf(code)}>
                {nameOf(code)}
              </span>
              {years.map((y) => {
                const cell = byKey.get(`${code}-${y}`);
                if (!cell) {
                  return (
                    <span
                      key={y}
                      className="heatmap-cell heatmap-cell-empty"
                      aria-label={`${nameOf(code)} ${y}: ${t("heatmap.legendNoData")}`}
                    />
                  );
                }
                const small = cell.contracts < MIN_RELIABLE_CONTRACTS;
                return (
                  <span
                    key={y}
                    tabIndex={0}
                    role="img"
                    aria-label={describe(cell)}
                    className={`heatmap-cell${small ? " heatmap-cell-small" : ""}`}
                    style={{ background: `var(--heat-${binOf(cell.anomaly_rate) + 1})` }}
                    onPointerEnter={(e) => show(e.currentTarget, cell)}
                    onFocus={(e) => show(e.currentTarget, cell)}
                    onBlur={() => setHover(null)}
                  />
                );
              })}
            </Fragment>
          ))}
        </div>
      </div>

      {hover && (
        <div
          className={`heatmap-tooltip heatmap-tooltip-${hover.align}`}
          style={{ left: hover.x, top: hover.y }}
          aria-hidden="true"
        >
          <strong>
            {nameOf(hover.cell.country_code)} · {hover.cell.year}
          </strong>
          <span>
            {t("heatmap.tooltipRate")}: {pct(hover.cell.anomaly_rate)}
          </span>
          <span>
            {t("heatmap.tooltipCount", {
              a: hover.cell.anomalies.toLocaleString(locale),
              n: hover.cell.contracts.toLocaleString(locale),
            })}
          </span>
          {hover.cell.contracts < MIN_RELIABLE_CONTRACTS && <em>{t("heatmap.tooltipSmall")}</em>}
        </div>
      )}

      <div className="heatmap-legend">
        <div className="heatmap-legend-scale" aria-label={t("heatmap.tooltipRate")}>
          {legendLabels.map((label, i) => (
            <span key={label} className="heatmap-legend-step">
              <span className="heatmap-legend-swatch" style={{ background: `var(--heat-${i + 1})` }} />
              {label}
            </span>
          ))}
        </div>
        <span className="heatmap-legend-key">
          <span className="heatmap-legend-swatch heatmap-cell-small" style={{ background: "var(--heat-4)" }} />
          {t("heatmap.legendSmall", { min: MIN_RELIABLE_CONTRACTS })}
        </span>
        <span className="heatmap-legend-key">
          <span className="heatmap-legend-swatch heatmap-cell-empty" />
          {t("heatmap.legendNoData")}
        </span>
      </div>

      <details className="heatmap-table">
        <summary>{t("heatmap.tableToggle")}</summary>
        <div className="heatmap-table-scroll">
          <table>
            <thead>
              <tr>
                <th>{t("heatmap.colCountry")}</th>
                <th>{t("heatmap.colYear")}</th>
                <th>{t("heatmap.colContracts")}</th>
                <th>{t("heatmap.colAnomalies")}</th>
                <th>{t("heatmap.colRate")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.flatMap((code) =>
                years
                  .map((y) => byKey.get(`${code}-${y}`))
                  .filter((c): c is CountryYearCell => c !== undefined)
                  .map((c) => (
                    <tr key={`${c.country_code}-${c.year}`}>
                      <td>{nameOf(c.country_code)}</td>
                      <td>{c.year}</td>
                      <td>{c.contracts.toLocaleString(locale)}</td>
                      <td>{c.anomalies.toLocaleString(locale)}</td>
                      <td>
                        {pct(c.anomaly_rate)}
                        {c.contracts < MIN_RELIABLE_CONTRACTS ? " *" : ""}
                      </td>
                    </tr>
                  )),
              )}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
