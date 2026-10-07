/**
 * Dashboard charts, server-rendered with no chart library.
 *
 * One series each, so every mark takes the accent and none needs a legend: the
 * card title names what is plotted. Values are labelled sparingly (the extreme
 * and the latest point); the rest live in a CSS hover tooltip and in the
 * table view under every chart, so no value is reachable by hover alone.
 */

export type Datum = { label: string; value: number; display: string; detail?: string };

function niceMax(max: number): number {
  if (max <= 0) return 1;
  const pow = 10 ** Math.floor(Math.log10(max));
  for (const step of [1, 2, 2.5, 5, 10]) {
    if (step * pow >= max) return step * pow;
  }
  return 10 * pow;
}

function TableView({ caption, headers, rows }: { caption: string; headers: [string, string]; rows: [string, string][] }) {
  return (
    <details className="vz-table">
      <summary>{caption}</summary>
      <table>
        <thead>
          <tr>
            <th>{headers[0]}</th>
            <th>{headers[1]}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([a, b]) => (
            <tr key={a}>
              <td>{a}</td>
              <td>{b}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

/** Vertical columns over time, labelled only at the peak and the latest year. */
export function ColumnChart({
  data,
  formatTick,
  tableCaption,
  headers,
}: {
  data: Datum[];
  formatTick: (n: number) => string;
  tableCaption: string;
  headers: [string, string];
}) {
  const top = niceMax(Math.max(0, ...data.map((d) => d.value)));
  const peak = data.reduce((best, d, i) => (d.value > data[best].value ? i : best), 0);
  const labelled = new Set([peak, data.length - 1]);
  const ticks = [top, top / 2, 0];

  return (
    <figure className="vz">
      <div className="vz-plot">
        {ticks.map((tk) => (
          <div key={tk} className="vz-grid" style={{ bottom: `${(tk / top) * 100}%` }}>
            <span>{formatTick(tk)}</span>
          </div>
        ))}
        <div className="vz-cols">
          {data.map((d, i) => (
            <div key={d.label} className="vz-col" tabIndex={0} aria-label={`${d.label}: ${d.display}`}>
              <div className="vz-col-bar" style={{ height: `${Math.max((d.value / top) * 100, d.value > 0 ? 1 : 0)}%` }}>
                {labelled.has(i) && <span className="vz-col-val">{d.display}</span>}
              </div>
              <span className="vz-tip" role="tooltip">
                <strong>{d.display}</strong> {d.label}
                {d.detail && <em>{d.detail}</em>}
              </span>
            </div>
          ))}
        </div>
      </div>
      <div className="vz-xlabels">
        {data.map((d) => (
          <span key={d.label}>{d.label}</span>
        ))}
      </div>
      <TableView caption={tableCaption} headers={headers} rows={data.map((d) => [d.label, d.display])} />
    </figure>
  );
}

/** Horizontal bars, sorted, with the full label and the value at each bar's tip. */
export function HBarChart({
  data,
  tableCaption,
  headers,
}: {
  data: Datum[];
  tableCaption: string;
  headers: [string, string];
}) {
  const sorted = [...data].sort((a, b) => b.value - a.value);
  const max = Math.max(1, ...sorted.map((d) => d.value));

  return (
    <figure className="vz">
      <div className="vz-hbars">
        {sorted.map((d) => (
          <div key={d.label} className="vz-hrow" tabIndex={0} aria-label={`${d.label}: ${d.display}`}>
            <span className="vz-hlabel" title={d.label}>
              {d.label}
            </span>
            <span className="vz-htrack">
              <span className="vz-hbar" style={{ width: `${Math.max((d.value / max) * 100, 0.5)}%` }} />
              <span className="vz-hval">{d.display}</span>
            </span>
            <span className="vz-tip" role="tooltip">
              <strong>{d.display}</strong> {d.label}
              {d.detail && <em>{d.detail}</em>}
            </span>
          </div>
        ))}
      </div>
      <TableView caption={tableCaption} headers={headers} rows={sorted.map((d) => [d.label, d.display])} />
    </figure>
  );
}

export type RatePoint = { label: string; rate: number; contracts: number; display: string; detail: string };

/**
 * A rate over time as a line, against the overall rate as a reference. Years
 * with too few contracts get a hollow point: their rate is mostly noise (one
 * flagged contract out of twelve reads as 8%), and a filled point would make it
 * look as solid as the rest.
 */
export function RateLineChart({
  points,
  average,
  averageLabel,
  minReliable,
  formatPct,
  tableCaption,
  headers,
}: {
  points: RatePoint[];
  average: number;
  averageLabel: string;
  minReliable: number;
  formatPct: (n: number) => string;
  tableCaption: string;
  headers: [string, string];
}) {
  const W = 600;
  const H = 210;
  const left = 44;
  const right = 16;
  const y0 = 18;
  const bottom = 30;
  const top = niceMax(Math.max(average, ...points.map((p) => p.rate)));
  const step = points.length > 1 ? (W - left - right) / (points.length - 1) : 0;
  const x = (i: number) => left + i * step;
  const y = (v: number) => y0 + (1 - v / top) * (H - y0 - bottom);
  const path = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(p.rate).toFixed(1)}`).join(" ");
  const peak = points.reduce((best, p, i) => (p.rate > points[best].rate ? i : best), 0);
  const labelled = new Set([peak, points.length - 1]);
  const ticks = [top, top / 2, 0];
  const everyOther = points.length > 10;

  return (
    <figure className="vz">
      <svg viewBox={`0 0 ${W} ${H}`} className="vz-svg" role="img" aria-label={tableCaption}>
        {ticks.map((tk) => (
          <g key={tk}>
            <line x1={left} x2={W - right} y1={y(tk)} y2={y(tk)} className="vz-gridline" />
            <text x={left - 8} y={y(tk) + 4} textAnchor="end" className="vz-tick">
              {formatPct(tk)}
            </text>
          </g>
        ))}
        <line x1={left} x2={W - right} y1={y(average)} y2={y(average)} className="vz-ref" />
        <text x={left + 6} y={y(average) - 6} className="vz-ref-label">
          {averageLabel}
        </text>
        <path d={path} className="vz-line" />
        {points.map((p, i) => {
          const small = p.contracts < minReliable;
          return (
            <g key={p.label} className="vz-pt" tabIndex={0}>
              <title>{`${p.label}: ${p.display} · ${p.detail}`}</title>
              <circle cx={x(i)} cy={y(p.rate)} r={12} className="vz-hit" />
              <circle cx={x(i)} cy={y(p.rate)} r={4.5} className={small ? "vz-dot vz-dot-small" : "vz-dot"} />
              {labelled.has(i) && (
                <text x={x(i)} y={y(p.rate) - 11} textAnchor="middle" className="vz-pt-label">
                  {p.display}
                </text>
              )}
              {(!everyOther || i % 2 === 0 || i === points.length - 1) && (
                <text x={x(i)} y={H - 10} textAnchor="middle" className="vz-tick">
                  {p.label}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <TableView
        caption={tableCaption}
        headers={headers}
        rows={points.map((p) => [p.label, `${p.display} (${p.detail})${p.contracts < minReliable ? " *" : ""}`])}
      />
    </figure>
  );
}
