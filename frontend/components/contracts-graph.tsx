"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getContractMap, type ContractMap, type MapTotals } from "@/lib/api";
import { COUNTRY_NAMES } from "@/lib/countries";
import { useLanguage } from "@/lib/language-context";
import { money, pct } from "@/components/territory-parts";

type ViewMode = "hierarchy" | "bipartite" | "anomalies";
type Metric = "contracts" | "value";

const VIEWS: ViewMode[] = ["hierarchy", "bipartite", "anomalies"];

// How many institutions the map carries. With no country the API splits them
// evenly across the ten countries, so every country appears. A phone column
// fits about half as many readable rows.
const LIMITS = {
  wide: { all: 20, one: 12, labelChars: 38 },
  // On a phone the label width truncates instead (see `levels`).
  narrow: { all: 10, one: 8, labelChars: 60 },
};

// Country, institution, sector: the first three slots of the dataviz skill's
// reference palette, validated all-pairs against this site's light and dark
// panel colours. The column headings name each layer, so colour is never the
// only cue.
const LAYER_COLORS = {
  light: ["#2a78d6", "#eb6834", "#1baf7a"],
  dark: ["#3987e5", "#d95926", "#199e70"],
};
// An institution is marked when its share of contracts with an alert is this
// many times its country's, over at least a handful of alerts.
const ALERT_RATIO = 1.5;
const MIN_ALERTS = 3;
// Sectors under this share of the drawn flow share one node.
const MIN_SECTOR_SHARE = 0.025;
const REST = "s:_rest";
const NARROW_LABEL_MARGIN = 112;

type Kind = "country" | "buyer" | "sector";
type Node = { name: string; label: string; kind: Kind; ref: string; layer: number; totals: MapTotals; highAlerts: boolean };
type Link = { source: string; target: string; value: number; totals: MapTotals };

function shorten(s: string, max: number) {
  const clean = s.trim();
  return clean.length > max ? `${clean.slice(0, max - 1)}…` : clean;
}

// The tooltip renders HTML, and institution names come straight from
// government data.
function escapeHtml(s: string) {
  return s.replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]!);
}

// ECharts draws to <canvas>, which silently ignores `var(--x)` strings, so theme
// colours have to be resolved to literals before they are handed over.
function themeColors() {
  const cs = getComputedStyle(document.documentElement);
  const read = (n: string, fb: string) => cs.getPropertyValue(n).trim() || fb;
  return {
    text: read("--text", "#1a1d23"),
    panel: read("--panel", "#ffffff"),
    danger: read("--danger", "#e5484d"),
  };
}

function alertRate(t: MapTotals) {
  return t.contracts ? t.flagged / t.contracts : 0;
}

function isHighAlert(b: MapTotals, countryTotals: MapTotals | undefined) {
  return b.flagged >= MIN_ALERTS && alertRate(b) > ALERT_RATIO * (countryTotals ? alertRate(countryTotals) : 0);
}

export function ContractsGraph({ initialCountry }: { initialCountry?: string }) {
  const { t, locale } = useLanguage();
  const chartRef = useRef<HTMLDivElement>(null);
  const [view, setView] = useState<ViewMode>("hierarchy");
  const [country, setCountry] = useState(initialCountry ?? "");
  const [metric, setMetric] = useState<Metric>("contracts");
  // Container width, 0 until measured: the row count depends on it, so the
  // map is fetched once the width is known rather than twice on a phone.
  const [width, setWidth] = useState(0);
  const [data, setData] = useState<ContractMap | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const narrow = width > 0 && width < 700;
  // Amounts are only comparable within one currency, so the value metric
  // needs a country; leaving the country empty falls back to counts.
  const activeMetric: Metric = country ? metric : "contracts";
  const limits = narrow ? LIMITS.narrow : LIMITS.wide;
  const limit = country ? limits.one : limits.all;
  const withCountries = view !== "bipartite";
  // A Sankey needs room per row; the tallest column sets the height.
  const rows = data ? Math.max(data.buyers.length, data.sectors.length) : limit;
  const height = Math.min(820, Math.max(360, rows * (narrow ? 36 : 32) + 40));

  useEffect(() => {
    if (width === 0) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    getContractMap({
      country: country || undefined,
      only_anomalous: view === "anomalies" || undefined,
      metric: activeMetric,
      limit,
    })
      .then((d) => !cancelled && setData(d))
      .catch((err) => !cancelled && setError(err instanceof Error ? err.message : t("graph.error")))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
    // `t` changes identity with the language; refetching for that is pointless.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [country, view, activeMetric, limit, width > 0]);

  const fmtValue = useCallback(
    (n: number) => (data?.currency ? money(n, data.currency, locale) : ""),
    [data, locale],
  );
  const sectorName = useCallback((key: string | null) => (key ? t(`terr.sectors.${key}`) : "—"), [t]);

  const render = useCallback(async () => {
    const el = chartRef.current;
    if (!el || !data || data.buyers.length === 0) return;
    const echarts = await import("echarts");
    const c = themeColors();
    const chart = echarts.getInstanceByDom(el) ?? echarts.init(el);

    // ECharts fixes the canvas to the container size at init. Initialising while
    // the container has no width -- a hidden tab, a collapsed pane, a
    // display:none ancestor -- yields a 2px canvas that never grows back on its
    // own, leaving the chart permanently invisible. Reconciling here makes every
    // render self-correcting; the height also changes with the row count.
    if (el.clientWidth > 0 && (Math.abs(chart.getWidth() - el.clientWidth) > 2 || chart.getHeight() !== el.clientHeight)) {
      chart.resize();
    }

    const isNarrow = el.clientWidth < 700;
    const lim = isNarrow ? LIMITS.narrow : LIMITS.wide;
    const size = (tot: MapTotals) => (data.metric === "value" ? tot.value : tot.contracts);
    const dark = document.documentElement.getAttribute("data-theme") === "dark";
    const layerColors = dark ? LAYER_COLORS.dark : LAYER_COLORS.light;
    const layerNames = [t("graph.legendCountry"), t("graph.legendInstitution"), t("graph.legendSector")];
    const countryTotals = new Map(data.countries.map((k) => [k.code, k]));

    const nodes: Node[] = [];
    const links: Link[] = [];
    const used = new Set<string>();
    for (const b of data.buyers) {
      const node: Node = {
        name: `b:${b.id}`, label: shorten(b.name, lim.labelChars), kind: "buyer", ref: b.id, layer: 1, totals: b,
        highAlerts: view !== "anomalies" && isHighAlert(b, countryTotals.get(b.country_code)),
      };
      nodes.push(node);
      if (withCountries && size(b) > 0) {
        links.push({ source: `c:${b.country_code}`, target: node.name, value: size(b), totals: b });
        used.add(`c:${b.country_code}`);
      }
    }
    // Sectors carrying a sliver of the drawn flow get a node a few pixels tall,
    // and their labels pile onto each other; they share one node instead,
    // whose tooltip names them. The table keeps every institution's detail.
    // A Sankey cannot draw a zero-width flow; with amounts, some contracts have none.
    const flows = data.links.filter((l) => size(l) > 0);
    const flowTotal = flows.reduce((sum, l) => sum + size(l), 0);
    const sectorFlow = new Map<string, number>();
    for (const l of flows) sectorFlow.set(l.sector, (sectorFlow.get(l.sector) ?? 0) + size(l));
    const small = new Set([...sectorFlow].filter(([, v]) => v < MIN_SECTOR_SHARE * flowTotal).map(([k]) => k));
    // Folding a single sector would only rename it.
    if (small.size < 2) small.clear();
    const sectorNode = (key: string) => (small.has(key) ? REST : `s:${key}`);
    const merged = new Map<string, Link>();
    for (const l of flows) {
      const target = sectorNode(l.sector);
      const key = `b:${l.buyer_id}>${target}`;
      const prev = merged.get(key);
      if (prev) {
        prev.value += size(l);
        prev.totals = { contracts: prev.totals.contracts + l.contracts, value: prev.totals.value + l.value, flagged: prev.totals.flagged + l.flagged };
      } else {
        merged.set(key, { source: `b:${l.buyer_id}`, target, value: size(l), totals: { contracts: l.contracts, value: l.value, flagged: l.flagged } });
      }
      used.add(target);
    }
    links.push(...merged.values());
    if (withCountries) {
      for (const k of data.countries) {
        if (!used.has(`c:${k.code}`)) continue;
        nodes.unshift({
          name: `c:${k.code}`, label: COUNTRY_NAMES[k.code] ?? k.code, kind: "country", ref: k.code, layer: 0,
          totals: k, highAlerts: false,
        });
      }
    }
    const rest: MapTotals = { contracts: 0, value: 0, flagged: 0 };
    for (const s of data.sectors) {
      if (small.has(s.key)) {
        rest.contracts += s.contracts;
        rest.value += s.value;
        rest.flagged += s.flagged;
      } else if (used.has(`s:${s.key}`)) {
        nodes.push({ name: `s:${s.key}`, label: sectorName(s.key), kind: "sector", ref: s.key, layer: 2, totals: s, highAlerts: false });
      }
    }
    if (used.has(REST)) {
      nodes.push({ name: REST, label: t("graph.restSectors"), kind: "sector", ref: "", layer: 2, totals: rest, highAlerts: false });
    }
    const restNames = [...small].map(sectorName).join(", ");
    const byName = new Map(nodes.map((n) => [n.name, n]));
    const lastDepth = withCountries ? 2 : 1;

    const describe = (tot: MapTotals) => {
      const parts = [t("graph.contracts", { n: tot.contracts.toLocaleString(locale) })];
      if (data.currency && tot.value > 0) parts.push(fmtValue(tot.value));
      if (view !== "anomalies") parts.push(t("graph.alertsOf", { n: tot.flagged.toLocaleString(locale), pct: pct(alertRate(tot), locale) }));
      return parts.join("<br/>");
    };

    chart.setOption(
      {
        tooltip: {
          backgroundColor: c.text,
          borderWidth: 0,
          textStyle: { color: c.panel, fontSize: 12 },
          formatter: (p: { dataType?: string; data?: unknown }) => {
            if (p.dataType === "edge") {
              const d = p.data as { source: string; target: string };
              const link = links.find((l) => l.source === d.source && l.target === d.target);
              if (!link) return "";
              const from = byName.get(link.source)?.label ?? "";
              const to = byName.get(link.target)?.label ?? "";
              return `<strong>${escapeHtml(from)} → ${escapeHtml(to)}</strong><br/>${describe(link.totals)}`;
            }
            const d = byName.get((p.data as { name: string }).name);
            if (!d) return "";
            const full = d.kind === "buyer" ? data.buyers.find((b) => b.id === d.ref)?.name ?? d.label : d.label;
            const hint =
              d.kind === "buyer" ? t("graph.clickInstitution") : d.kind === "country" && !country ? t("graph.clickCountry") : "";
            return [
              `<strong>${escapeHtml(full)}</strong> <span style="opacity:.75">· ${escapeHtml(layerNames[d.layer])}</span>`,
              describe(d.totals),
              d.name === REST ? `<span style="opacity:.75">${escapeHtml(restNames)}</span>` : "",
              d.highAlerts ? `<span style="color:${c.danger}">● ${escapeHtml(t("graph.highAlerts"))}</span>` : "",
              hint ? `<span style="opacity:.75">${escapeHtml(hint)}</span>` : "",
            ]
              .filter(Boolean)
              .join("<br/>");
          },
        },
        series: [
          {
            type: "sankey",
            data: nodes.map((n) => ({
              name: n.name,
              depth: withCountries ? n.layer : n.layer - 1,
              itemStyle: {
                color: layerColors[n.layer],
                ...(n.highAlerts ? { borderColor: c.danger, borderWidth: 3 } : { borderWidth: 0 }),
              },
              cursor: n.kind === "sector" || (n.kind === "country" && country) ? "default" : "pointer",
            })),
            links: links.map(({ source, target, value }) => ({ source, target, value })),
            top: 12,
            bottom: 12,
            left: 4,
            // On a phone the last column's labels go to its right, into this
            // margin: placed to its left they ran into the middle column's.
            right: isNarrow ? NARROW_LABEL_MARGIN : 4,
            nodeWidth: isNarrow ? 10 : 14,
            nodeGap: isNarrow ? 12 : 14,
            nodeAlign: "justify",
            layoutIterations: 64,
            draggable: false,
            label: {
              color: c.text,
              fontSize: isNarrow ? 10 : 11,
              // Readable where a label crosses the ribbons.
              textBorderColor: c.panel,
              textBorderWidth: 3,
              formatter: (p: { name: string }) => byName.get(p.name)?.label ?? "",
            },
            // Wide: the last column's labels sit to its left, inside the canvas.
            // Narrow: every label to the right, cut to the room before the next
            // column (or the margin, for the last one).
            levels: isNarrow
              ? Array.from({ length: lastDepth + 1 }, (_, depth) => ({
                  depth,
                  label: {
                    position: "right",
                    overflow: "truncate",
                    width:
                      depth === lastDepth
                        ? NARROW_LABEL_MARGIN - 14
                        : (el.clientWidth - NARROW_LABEL_MARGIN) / lastDepth - 16,
                  },
                }))
              : [{ depth: lastDepth, label: { position: "left" } }],
            lineStyle: { color: "gradient", curveness: 0.5, opacity: 0.32 },
            emphasis: { focus: "adjacency", lineStyle: { opacity: 0.7 } },
            blur: { itemStyle: { opacity: 0.25 }, lineStyle: { opacity: 0.06 } },
          },
        ],
      },
      { notMerge: true },
    );

    chart.off("click");
    chart.on("click", (p: { dataType?: string; data?: unknown }) => {
      if (p.dataType !== "node") return;
      const d = byName.get((p.data as { name: string }).name);
      if (!d) return;
      if (d.kind === "buyer") window.location.href = `/territorios/institucion/${encodeURIComponent(d.ref)}`;
      else if (d.kind === "country" && !country) setCountry(d.ref);
    });
  }, [data, view, country, withCountries, t, locale, fmtValue, sectorName]);

  useEffect(() => {
    void render();
  }, [render, height]);

  useEffect(() => {
    const el = chartRef.current;
    if (!el) return;

    // A ResizeObserver on the container, not a window resize listener: the
    // container is what ECharts sizes the canvas from, and it changes on layout
    // shifts that never fire a window resize. Missing those left a 1066px canvas
    // inside a 342px column at mobile width.
    let last = 0;
    const sync = () => {
      const w = el.clientWidth;
      if (w === 0 || w === last) return;
      last = w;
      setWidth(w);
      void (async () => {
        const echarts = await import("echarts");
        echarts.getInstanceByDom(el)?.resize();
        void render();
      })();
    };
    sync();

    // Both, deliberately. ResizeObserver is the accurate signal but is not
    // available everywhere; the window listener misses container-only layout
    // shifts but covers the common case. `sync` no-ops on an unchanged width,
    // so whichever fires first wins and the other is free.
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(sync) : null;
    observer?.observe(el);
    window.addEventListener("resize", sync);

    // Canvas pixels keep whatever colour they were painted, so a theme flip has
    // to redraw; CSS cannot restyle an already-rendered chart.
    const themeObserver = new MutationObserver(() => void render());
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", sync);
      themeObserver.disconnect();
    };
  }, [render]);

  useEffect(
    () => () => {
      const el = chartRef.current;
      if (!el) return;
      void import("echarts").then((e) => e.getInstanceByDom(el)?.dispose());
    },
    [],
  );

  const empty = !loading && !error && (!data || data.buyers.length === 0);
  const button = (active: boolean) => ({
    background: active ? "var(--text)" : "transparent",
    color: active ? "var(--bg)" : "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    padding: "6px 12px",
    cursor: "pointer",
  });
  const num = (n: number) => n.toLocaleString(locale);
  const columns = withCountries
    ? [t("graph.legendCountry"), t("graph.legendInstitution"), t("graph.legendSector")]
    : [t("graph.legendInstitution"), t("graph.legendSector")];

  return (
    <div style={{ width: "100%", marginBottom: 30 }}>
      <h2 style={{ marginTop: 0 }}>{t("graph.title")}</h2>
      <p className="wizard-note" style={{ marginBottom: 12 }}>
        {t(`graph.blurb.${view}`)} {t("graph.hint")}
      </p>

      <div className="filters" style={{ marginBottom: 8 }}>
        {VIEWS.map((v) => (
          <button key={v} type="button" onClick={() => setView(v)} aria-pressed={view === v} style={button(view === v)}>
            {t(`graph.view.${v}`)}
          </button>
        ))}
        <select value={country} onChange={(e) => setCountry(e.target.value)} aria-label={t("dashboard.colCountry")}>
          <option value="">{t("home.allCountries")}</option>
          {Object.entries(COUNTRY_NAMES).map(([code, name]) => (
            <option key={code} value={code}>
              {name}
            </option>
          ))}
        </select>
      </div>
      <div className="filters" style={{ marginBottom: 12 }} role="group" aria-label={t("graph.metricLabel")}>
        <span className="wizard-note" style={{ margin: 0 }}>
          {t("graph.metricLabel")}
        </span>
        {(["contracts", "value"] as Metric[]).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMetric(m)}
            aria-pressed={activeMetric === m}
            disabled={m === "value" && !country}
            title={m === "value" && !country ? t("graph.valueNeedsCountry") : undefined}
            style={{ ...button(activeMetric === m), opacity: m === "value" && !country ? 0.5 : 1 }}
          >
            {t(`graph.metric.${m}`)}
          </button>
        ))}
        {!country && <span className="vz-note">{t("graph.valueNeedsCountry")}</span>}
      </div>

      <div
        aria-hidden
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: "0.78rem",
          fontWeight: 600,
          color: "var(--muted)",
          padding: "0 4px 4px",
        }}
      >
        {columns.map((name, i) => (
          <span key={name} style={{ color: LAYER_COLORS.light[withCountries ? i : i + 1] }}>
            {name}
          </span>
        ))}
      </div>
      <div style={{ position: "relative" }}>
        <div
          ref={chartRef}
          role="img"
          aria-label={t("graph.title")}
          style={{
            width: "100%",
            height,
            border: "1px solid var(--border)",
            borderRadius: 6,
            background: "var(--panel)",
            opacity: loading && data ? 0.45 : 1,
            transition: "opacity .2s",
          }}
        />
        {(error || empty || (loading && !data)) && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: error ? "var(--danger)" : "var(--muted)",
              textAlign: "center",
              padding: 16,
            }}
          >
            {error ?? (loading ? t("graph.loading") : t("graph.empty"))}
          </div>
        )}
      </div>

      {data && !error && data.buyers.length > 0 && (
        <>
          <p className="wizard-note" style={{ marginTop: 10, fontSize: "0.9em" }}>
            {[
              t("graph.basis", { n: num(data.total.contracts) }),
              t("graph.coverage", {
                buyers: data.buyers.length,
                n: num(data.shown.contracts),
                pct: pct(data.total.contracts ? data.shown.contracts / data.total.contracts : 0, locale, 0),
              }),
              !country && t("graph.perCountry"),
              data.currency && t("graph.currencyNote", { currency: data.currency }),
              view !== "anomalies" && t("graph.highAlertsNote"),
            ]
              .filter(Boolean)
              .join(" ")}
          </p>

          <h3 style={{ margin: "18px 0 8px" }}>{t("graph.tableTitle")}</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>{t("dashboard.colInstitution")}</th>
                  <th>{t("dashboard.colCountry")}</th>
                  <th>{t("dashboard.colContracts")}</th>
                  {data.currency && <th>{t("graph.colValue", { currency: data.currency })}</th>}
                  {view !== "anomalies" && <th>{t("graph.colAlerts")}</th>}
                  <th>{t("graph.colSector")}</th>
                </tr>
              </thead>
              <tbody>
                {data.buyers.map((b, i) => {
                  const high = isHighAlert(b, data.countries.find((k) => k.code === b.country_code));
                  return (
                    <tr key={b.id}>
                      <td>{i + 1}</td>
                      <td>
                        <a href={`/territorios/institucion/${encodeURIComponent(b.id)}`}>{b.name}</a>
                      </td>
                      <td>{COUNTRY_NAMES[b.country_code] ?? b.country_code}</td>
                      <td>{num(b.contracts)}</td>
                      {data.currency && <td>{b.value > 0 ? fmtValue(b.value) : "—"}</td>}
                      {view !== "anomalies" && (
                        <td>
                          <span className={`badge ${high ? "wizard-verdict-alta" : b.flagged ? "wizard-verdict-revisar" : "wizard-verdict-normal"}`}>
                            {pct(alertRate(b), locale)}
                          </span>
                        </td>
                      )}
                      <td>{sectorName(b.main_sector)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
