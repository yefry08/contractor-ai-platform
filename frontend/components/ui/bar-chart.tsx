export type BarChartDatum = { label: string; value: number; displayValue?: string };

export function BarChart({
  data,
  color = "var(--accent)",
}: {
  data: BarChartDatum[];
  color?: string;
}) {
  const max = Math.max(...data.map((d) => d.value), 1);

  return (
    <div className="bar-chart">
      <div className="bar-chart-bars">
        {data.map((d) => (
          <div key={d.label} className="bar-chart-col" title={`${d.label}: ${d.displayValue ?? d.value}`}>
            <span className="bar-chart-value">{d.displayValue ?? d.value}</span>
            <div
              className="bar-chart-bar"
              style={{ height: `${Math.max((d.value / max) * 100, 2)}%`, background: color }}
            />
          </div>
        ))}
      </div>
      <div className="bar-chart-labels">
        {data.map((d) => (
          <span key={d.label} className="bar-chart-label" title={d.label}>
            {d.label}
          </span>
        ))}
      </div>
    </div>
  );
}
