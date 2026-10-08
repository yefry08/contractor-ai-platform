"use client";

/**
 * ECharts (Apache-2.0) charts for the dashboard and "Datos de los datos".
 *
 * Colour comes from the dataviz skill's reference palette, validated against
 * this site's own panel colours (#f6f7fa light, #121b2e dark): slots 1-3
 * (blue, orange, aqua) for categories, a blue ramp for magnitude and the
 * blue <-> red pair for polarity. Orange and aqua sit just under 3:1 on the
 * light panel, so every chart also ships its numbers as a table.
 *
 * Every component takes plain data and pre-translated strings, so server
 * components can render them: functions can't cross that boundary.
 */

import { useEffect, useRef, type ReactNode } from "react";
import type { EChartsOption } from "echarts";

const PALETTE = {
  light: {
    blue: "#2a78d6",
    orange: "#eb6834",
    aqua: "#1baf7a",
    red: "#e34948",
    blueRamp: ["#9ec5f4", "#3987e5", "#1c5cab", "#0d366b"],
  },
  dark: {
    blue: "#3987e5",
    orange: "#d95926",
    aqua: "#199e70",
    red: "#e66767",
    blueRamp: ["#184f95", "#256abf", "#5598e7", "#9ec5f4"],
  },
};

type Theme = (typeof PALETTE)["light"] & { dark: boolean; text: string; muted: string; border: string; panel: string };

// ECharts paints to SVG/canvas attributes, where var(--x) means nothing, so the
// site's tokens are resolved to literals on every render (and theme flip).
function readTheme(): Theme {
  const dark = document.documentElement.getAttribute("data-theme") === "dark";
  const cs = getComputedStyle(document.documentElement);
  const v = (name: string, fallback: string) => cs.getPropertyValue(name).trim() || fallback;
  return {
    ...(dark ? PALETTE.dark : PALETTE.light),
    dark,
    text: v("--text", dark ? "#e6ecf5" : "#14181f"),
    muted: v("--muted", dark ? "#93a1b8" : "#5b6472"),
    border: v("--border", dark ? "#24314d" : "#e3e6ec"),
    panel: v("--panel", dark ? "#121b2e" : "#f6f7fa"),
  };
}

// Tooltips render HTML and labels come straight from government data.
function esc(s: string) {
  return s.replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]!);
}

function useEChart(build: (t: Theme, width: number) => EChartsOption, key: string) {
  const ref = useRef<HTMLDivElement>(null);
  const buildRef = useRef(build);
  buildRef.current = build;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let disposed = false;
    let chart: import("echarts").ECharts | undefined;

    const render = async () => {
      const echarts = await import("echarts");
      if (disposed) return;
      chart = echarts.getInstanceByDom(el) ?? echarts.init(el, undefined, { renderer: "svg" });
      chart.setOption(buildRef.current(readTheme(), el.clientWidth), true);
    };
    void render();

    // Rebuild, not just resize: legend rows and grid offsets depend on width.
    const resize = new ResizeObserver(() => {
      chart?.resize();
      void render();
    });
    resize.observe(el);
    const theme = new MutationObserver(() => void render());
    theme.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

    return () => {
      disposed = true;
      resize.disconnect();
      theme.disconnect();
      chart?.dispose();
    };
  }, [key]);

  return ref;
}

function base(t: Theme): EChartsOption {
  return {
    backgroundColor: "transparent",
    textStyle: { color: t.muted, fontFamily: "inherit" },
    animationDuration: 600,
    tooltip: {
      backgroundColor: t.dark ? "#0b1220" : "#ffffff",
      borderColor: t.border,
      textStyle: { color: t.text, fontSize: 12 },
      extraCssText: "box-shadow: 0 6px 20px rgba(0,0,0,.15); border-radius: 8px;",
    },
  };
}

// A legend of 2-3 entries fits one row from ~480px; below that it wraps to two.
const legendTop = (width: number, base: number) => (width < 480 ? base + 24 : base);

const axisLine = (t: Theme) => ({ lineStyle: { color: t.border } });
const splitLine = (t: Theme) => ({ lineStyle: { color: t.border, type: "dashed" as const } });

export function TableView({ caption, headers, rows }: { caption: string; headers: string[]; rows: ReactNode[][] }) {
  return (
    <details className="vz-table">
      <summary>{caption}</summary>
      <div className="vz-table-scroll">
        <table>
          <thead>
            <tr>
              {headers.map((h) => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {r.map((c, j) => (
                  <td key={j}>{c}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function Frame({ chartRef, height, label }: { chartRef: React.RefObject<HTMLDivElement | null>; height: number; label: string }) {
  return <div ref={chartRef} className="vz-echart" style={{ height }} role="img" aria-label={label} />;
}

export type Datum = { label: string; value: number; display: string; detail?: string };

/** Columns over time in a blue gradient, labelled at the peak and the latest bar. */
export function ColumnsChart({
  data,
  label,
  locale,
  height = 240,
}: {
  data: Datum[];
  label: string;
  locale: string;
  height?: number;
}) {
  const ref = useEChart((t) => {
    const peak = data.reduce((b, d, i) => (d.value > data[b].value ? i : b), 0);
    const show = new Set([peak, data.length - 1]);
    return {
      ...base(t),
      grid: { left: 8, right: 8, top: 28, bottom: 4, containLabel: true },
      tooltip: {
        ...base(t).tooltip,
        trigger: "item",
        formatter: (p: any) => {
          const d = data[p.dataIndex];
          return `<b>${esc(d.label)}</b><br/>${esc(d.display)}${d.detail ? `<br/><span style="opacity:.7">${esc(d.detail)}</span>` : ""}`;
        },
      },
      xAxis: { type: "category", data: data.map((d) => d.label), axisLine: axisLine(t), axisTick: { show: false } },
      yAxis: {
        type: "value",
        splitLine: splitLine(t),
        axisLabel: { formatter: (v: number) => v.toLocaleString(locale, { notation: "compact" }) },
      },
      series: [
        {
          type: "bar",
          barMaxWidth: 34,
          data: data.map((d, i) => ({
            value: d.value,
            label: { show: show.has(i), position: "top", color: t.text, fontWeight: 600, formatter: d.display },
          })),
          itemStyle: {
            borderRadius: [5, 5, 0, 0],
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: t.blueRamp[t.dark ? 3 : 2] },
                { offset: 1, color: t.blueRamp[t.dark ? 1 : 0] },
              ],
            },
          },
          emphasis: { itemStyle: { color: t.orange } },
        },
      ],
    };
  }, JSON.stringify(data));
  return <Frame chartRef={ref} height={height} label={label} />;
}

export type RatePoint = { label: string; rate: number; contracts: number; display: string; detail: string };

/** A rate over time: orange line and area, the overall average as a dashed
 *  reference, and hollow points where the year has too few contracts. */
export function RateChart({
  points,
  average,
  averageLabel,
  minReliable,
  label,
  height = 240,
}: {
  points: RatePoint[];
  average: number;
  averageLabel: string;
  minReliable: number;
  label: string;
  height?: number;
}) {
  const ref = useEChart((t) => {
    const peak = points.reduce((b, p, i) => (p.rate > points[b].rate ? i : b), 0);
    const show = new Set([peak, points.length - 1]);
    return {
      ...base(t),
      grid: { left: 8, right: 16, top: 30, bottom: 4, containLabel: true },
      tooltip: {
        ...base(t).tooltip,
        trigger: "axis",
        axisPointer: { type: "line", lineStyle: { color: t.muted } },
        formatter: (ps: any) => {
          const p = points[ps[0].dataIndex];
          const small = p.contracts < minReliable ? `<br/><i style="opacity:.7">n &lt; ${minReliable}</i>` : "";
          return `<b>${esc(p.label)}</b><br/>${esc(p.display)}<br/><span style="opacity:.7">${esc(p.detail)}</span>${small}`;
        },
      },
      xAxis: { type: "category", boundaryGap: false, data: points.map((p) => p.label), axisLine: axisLine(t), axisTick: { show: false } },
      yAxis: {
        type: "value",
        splitLine: splitLine(t),
        axisLabel: { formatter: (v: number) => `${Math.round(v * 100)}%` },
      },
      series: [
        {
          type: "line",
          // Straight segments: a smoothed curve overshoots below 0% between a
          // low year and a zero year, drawing a rate that never happened.
          symbolSize: 9,
          lineStyle: { width: 2.5, color: t.orange },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: t.orange + "55" },
                { offset: 1, color: t.orange + "05" },
              ],
            },
          },
          data: points.map((p, i) => ({
            value: p.rate,
            itemStyle:
              p.contracts < minReliable
                ? { color: t.panel, borderColor: t.orange, borderWidth: 2 }
                : { color: t.orange, borderColor: t.panel, borderWidth: 2 },
            label: { show: show.has(i), position: "top", color: t.text, fontWeight: 600, formatter: p.display },
          })),
          markLine: {
            silent: true,
            symbol: "none",
            lineStyle: { color: t.muted, type: "dashed" },
            label: { formatter: averageLabel, position: "insideStartTop", color: t.muted },
            data: [{ yAxis: average }],
          },
        },
      ],
    };
  }, JSON.stringify(points) + average);
  return <Frame chartRef={ref} height={height} label={label} />;
}

export type SplitRow = { label: string; total: number; flagged: number; detail: string };

/** Horizontal bars split into contracts without and with an open anomaly. */
export function SplitBarsChart({
  rows,
  names,
  label,
  locale,
}: {
  rows: SplitRow[];
  names: [string, string];
  label: string;
  locale: string;
}) {
  const sorted = [...rows].sort((a, b) => a.total - b.total);
  const ref = useEChart((t, w) => {
    const n = (v: number) => v.toLocaleString(locale);
    return {
      ...base(t),
      legend: { top: 0, left: 0, textStyle: { color: t.text }, itemWidth: 12, itemHeight: 12, icon: "roundRect" },
      grid: { left: 8, right: 56, top: legendTop(w, 30), bottom: 4, containLabel: true },
      tooltip: {
        ...base(t).tooltip,
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (ps: any) => {
          const r = sorted[ps[0].dataIndex];
          return `<b>${esc(r.label)}</b><br/>${esc(r.detail)}`;
        },
      },
      xAxis: { type: "value", splitLine: splitLine(t), axisLabel: { formatter: (v: number) => v.toLocaleString(locale, { notation: "compact" }) } },
      yAxis: {
        type: "category",
        data: sorted.map((r) => r.label),
        axisLine: axisLine(t),
        axisTick: { show: false },
        axisLabel: { color: t.text, width: 150, overflow: "truncate" },
      },
      series: [
        {
          name: names[0],
          type: "bar",
          stack: "s",
          barMaxWidth: 20,
          itemStyle: { color: t.blue, borderColor: t.panel, borderWidth: 1 },
          data: sorted.map((r) => r.total - r.flagged),
        },
        {
          name: names[1],
          type: "bar",
          stack: "s",
          barMaxWidth: 20,
          itemStyle: { color: t.orange, borderColor: t.panel, borderWidth: 1, borderRadius: [0, 4, 4, 0] },
          label: { show: true, position: "right", color: t.text, formatter: (p: any) => n(sorted[p.dataIndex].total) },
          data: sorted.map((r) => r.flagged),
        },
      ],
    };
  }, JSON.stringify(rows));
  return <Frame chartRef={ref} height={Math.max(160, sorted.length * 30 + 50)} label={label} />;
}

/** A histogram with the bins at a legal ceiling highlighted and the ceiling marked. */
export function ThresholdChart({
  bins,
  ceilingIndex,
  ceilingLabel,
  names,
  label,
  locale,
  height = 300,
}: {
  bins: { label: string; value: number; near: boolean }[];
  ceilingIndex: number;
  ceilingLabel: string;
  names: [string, string];
  label: string;
  locale: string;
  height?: number;
}) {
  const ref = useEChart((t, w) => ({
    ...base(t),
    legend: { top: 0, left: 0, textStyle: { color: t.text }, itemWidth: 12, itemHeight: 12, icon: "roundRect" },
    grid: { left: 8, right: 12, top: legendTop(w, 58), bottom: 4, containLabel: true },
    tooltip: {
      ...base(t).tooltip,
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (ps: any) => {
        const b = bins[ps[0].dataIndex];
        return `<b>${esc(b.label)}</b><br/>${b.value.toLocaleString(locale)}`;
      },
    },
    xAxis: {
      type: "category",
      data: bins.map((b) => b.label),
      axisLine: axisLine(t),
      axisTick: { show: false },
      axisLabel: { interval: Math.ceil(bins.length / 8) - 1, color: t.muted },
    },
    yAxis: { type: "value", splitLine: splitLine(t) },
    series: [
      {
        name: names[0],
        type: "bar",
        stack: "h",
        barCategoryGap: "12%",
        itemStyle: { color: t.blue, borderRadius: [3, 3, 0, 0] },
        data: bins.map((b) => (b.near ? 0 : b.value)),
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { color: t.red, width: 2, type: "solid" },
          label: { formatter: ceilingLabel, color: t.text, fontWeight: 600, position: "end", distance: 6 },
          data: [{ xAxis: ceilingIndex }],
        },
      },
      {
        name: names[1],
        type: "bar",
        stack: "h",
        itemStyle: { color: t.orange, borderRadius: [3, 3, 0, 0] },
        label: {
          show: true,
          position: "top",
          color: t.text,
          fontWeight: 600,
          formatter: (p: any) => (p.value > 0 && p.value === Math.max(...bins.map((b) => b.value)) ? p.value.toLocaleString(locale) : ""),
        },
        data: bins.map((b) => (b.near ? b.value : 0)),
      },
    ],
  }), JSON.stringify(bins));
  return <Frame chartRef={ref} height={height} label={label} />;
}

/** Observed first-digit shares against Benford's expected curve. */
export function BenfordChart({
  observed,
  expected,
  names,
  label,
  height = 170,
  compact = true,
}: {
  observed: number[];
  expected: number[];
  names: [string, string];
  label: string;
  height?: number;
  compact?: boolean;
}) {
  const ref = useEChart((t, w) => ({
    ...base(t),
    legend: compact ? undefined : { top: 0, left: 0, textStyle: { color: t.text }, itemWidth: 12, itemHeight: 12 },
    grid: { left: 4, right: 4, top: compact ? 8 : legendTop(w, 32), bottom: 2, containLabel: true },
    tooltip: {
      ...base(t).tooltip,
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (ps: any) =>
        `<b>${ps[0].axisValue}</b><br/>${esc(names[0])}: ${(observed[ps[0].dataIndex] * 100).toFixed(1)}%<br/>${esc(names[1])}: ${(expected[ps[0].dataIndex] * 100).toFixed(1)}%`,
    },
    xAxis: { type: "category", data: ["1", "2", "3", "4", "5", "6", "7", "8", "9"], axisLine: axisLine(t), axisTick: { show: false } },
    yAxis: {
      type: "value",
      max: (v: { max: number }) => Math.max(0.35, Math.ceil(v.max * 20) / 20),
      splitLine: splitLine(t),
      axisLabel: { show: !compact, formatter: (v: number) => `${Math.round(v * 100)}%` },
    },
    series: [
      {
        name: names[0],
        type: "bar",
        barCategoryGap: "22%",
        itemStyle: {
          borderRadius: [3, 3, 0, 0],
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: t.blue },
              { offset: 1, color: t.blueRamp[0] },
            ],
          },
        },
        data: observed,
      },
      {
        name: names[1],
        type: "line",
        smooth: true,
        symbol: "circle",
        symbolSize: 6,
        lineStyle: { color: t.orange, width: 2 },
        itemStyle: { color: t.orange, borderColor: t.panel, borderWidth: 1 },
        data: expected,
      },
    ],
  }), JSON.stringify(observed));
  return <Frame chartRef={ref} height={height} label={label} />;
}

/** Two opposite counts per row: one to the left (blue), one to the right (red). */
export function DivergingChart({
  rows,
  names,
  label,
  locale,
}: {
  rows: { label: string; left: number; right: number }[];
  names: [string, string];
  label: string;
  locale: string;
}) {
  const sorted = [...rows].sort((a, b) => a.right - a.left - (b.right - b.left));
  const ref = useEChart((t, w) => ({
    ...base(t),
    legend: { top: 0, left: 0, textStyle: { color: t.text }, itemWidth: 12, itemHeight: 12, icon: "roundRect" },
    grid: { left: 8, right: 40, top: legendTop(w, 32), bottom: 4, containLabel: true },
    tooltip: {
      ...base(t).tooltip,
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (ps: any) => {
        const r = sorted[ps[0].dataIndex];
        return `<b>${esc(r.label)}</b><br/>${esc(names[0])}: ${r.left.toLocaleString(locale)}<br/>${esc(names[1])}: ${r.right.toLocaleString(locale)}`;
      },
    },
    xAxis: {
      type: "value",
      splitLine: splitLine(t),
      axisLabel: { formatter: (v: number) => Math.abs(v).toLocaleString(locale) },
    },
    yAxis: { type: "category", data: sorted.map((r) => r.label), axisLine: axisLine(t), axisTick: { show: false }, axisLabel: { color: t.text } },
    series: [
      {
        name: names[0],
        type: "bar",
        stack: "d",
        barMaxWidth: 18,
        itemStyle: { color: t.blue, borderRadius: [4, 0, 0, 4] },
        label: { show: true, position: "left", color: t.text, formatter: (p: any) => (p.value ? Math.abs(p.value).toLocaleString(locale) : "") },
        data: sorted.map((r) => -r.left),
      },
      {
        name: names[1],
        type: "bar",
        stack: "d",
        barMaxWidth: 18,
        itemStyle: { color: t.red, borderRadius: [0, 4, 4, 0] },
        label: { show: true, position: "right", color: t.text, formatter: (p: any) => (p.value ? p.value.toLocaleString(locale) : "") },
        data: sorted.map((r) => r.right),
      },
    ],
  }), JSON.stringify(rows));
  return <Frame chartRef={ref} height={sorted.length * 30 + 60} label={label} />;
}

/** 100% stacked horizontal bars. `ramp` colours ordered parts light to dark
 *  (shares of one whole); otherwise the categorical slots in fixed order. */
export function ShareBarsChart({
  rows,
  names,
  ramp = false,
  label,
}: {
  rows: { label: string; values: number[] }[];
  names: string[];
  ramp?: boolean;
  label: string;
}) {
  const ref = useEChart((t, w) => {
    const colors = ramp ? [t.blueRamp[3], t.blueRamp[2], t.blueRamp[0]] : [t.blue, t.orange, t.aqua];
    const pct = rows.map((r) => {
      const sum = r.values.reduce((a, b) => a + b, 0) || 1;
      return r.values.map((v) => v / sum);
    });
    return {
      ...base(t),
      legend: { top: 0, left: 0, textStyle: { color: t.text }, itemWidth: 12, itemHeight: 12, icon: "roundRect" },
      grid: { left: 8, right: 12, top: legendTop(w, 34), bottom: 4, containLabel: true },
      tooltip: {
        ...base(t).tooltip,
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (ps: any) => {
          const i = ps[0].dataIndex;
          return `<b>${esc(rows[i].label)}</b><br/>${names
            .map((n, k) => `${esc(n)}: ${(pct[i][k] * 100).toFixed(1)}%`)
            .join("<br/>")}`;
        },
      },
      xAxis: { type: "value", max: 1, splitLine: splitLine(t), axisLabel: { formatter: (v: number) => `${Math.round(v * 100)}%` } },
      yAxis: { type: "category", inverse: true, data: rows.map((r) => r.label), axisLine: axisLine(t), axisTick: { show: false }, axisLabel: { color: t.text } },
      series: names.map((name, k) => ({
        name,
        type: "bar" as const,
        stack: "p",
        barMaxWidth: 22,
        itemStyle: { color: colors[k], borderColor: t.panel, borderWidth: 1 },
        label: {
          show: true,
          // The ramp's palest step sits last in light mode and first in dark.
          color: ramp && ((k === 2 && !t.dark) || (k === 0 && t.dark)) ? "#0b1220" : "#ffffff",
          fontWeight: 600,
          formatter: (p: any) => (p.value >= 0.08 ? `${Math.round(p.value * 100)}%` : ""),
        },
        data: pct.map((r) => r[k]),
      })),
    };
  }, JSON.stringify(rows));
  return <Frame chartRef={ref} height={rows.length * 34 + 60} label={label} />;
}
