"use client";

import { useEffect, useRef, useState } from "react";

type GraphNode = { name: string; category: number; symbolSize: number };
type GraphLink = { source: string; target: string; relation: string };

// Nodes are keyed by `name`: ECharts resolves `links.source`/`links.target`
// against node names, so an `id` field alone leaves every edge unresolved.
const NODES: GraphNode[] = [
  { name: "Contractor AI", category: 0, symbolSize: 46 },
  { name: "FastAPI Backend", category: 1, symbolSize: 34 },
  { name: "Next.js Frontend", category: 1, symbolSize: 34 },
  { name: "Dashboard", category: 1, symbolSize: 24 },
  { name: "PostgreSQL", category: 2, symbolSize: 32 },
  { name: "Detección de anomalías", category: 3, symbolSize: 28 },
  { name: "Capa estadística", category: 3, symbolSize: 26 },
  { name: "Análisis de proveedores", category: 3, symbolSize: 26 },
  { name: "Modelo NLP (BERT)", category: 4, symbolSize: 26 },
  { name: "Ingesta de datos", category: 5, symbolSize: 28 },
  { name: "Render", category: 6, symbolSize: 20 },
  { name: "Vercel", category: 6, symbolSize: 20 },
];

const LINKS: GraphLink[] = [
  { source: "Contractor AI", target: "FastAPI Backend", relation: "usa" },
  { source: "Contractor AI", target: "Next.js Frontend", relation: "usa" },
  { source: "FastAPI Backend", target: "PostgreSQL", relation: "consulta" },
  { source: "FastAPI Backend", target: "Detección de anomalías", relation: "implementa" },
  { source: "FastAPI Backend", target: "Capa estadística", relation: "implementa" },
  { source: "FastAPI Backend", target: "Análisis de proveedores", relation: "implementa" },
  { source: "Detección de anomalías", target: "Modelo NLP (BERT)", relation: "usa" },
  { source: "Detección de anomalías", target: "Capa estadística", relation: "cruza con" },
  { source: "Ingesta de datos", target: "PostgreSQL", relation: "puebla" },
  { source: "Next.js Frontend", target: "Dashboard", relation: "renderiza" },
  { source: "Dashboard", target: "Análisis de proveedores", relation: "consume" },
  { source: "FastAPI Backend", target: "Render", relation: "desplegado en" },
  { source: "Next.js Frontend", target: "Vercel", relation: "desplegado en" },
];

const CATEGORIES = [
  { name: "Núcleo" },
  { name: "Aplicación" },
  { name: "Datos" },
  { name: "Analítica" },
  { name: "ML / IA" },
  { name: "Ingesta" },
  { name: "Infraestructura" },
];

// ECharts draws to <canvas>, which cannot resolve `var(--x)` strings -- passing
// them through silently keeps whatever colour was set before. Every colour handed
// to ECharts has to be resolved to a literal value here first.
function themeColors() {
  const cs = getComputedStyle(document.documentElement);
  const read = (name: string, fallback: string) => cs.getPropertyValue(name).trim() || fallback;
  return {
    text: read("--text", "#1a1d23"),
    muted: read("--muted", "#6b7280"),
    border: read("--border", "#e3e6ec"),
    accent: read("--accent", "#2f6feb"),
    panel: read("--panel", "#ffffff"),
  };
}

export function KnowledgeGraph() {
  const chartRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let chart: { setOption: (o: unknown) => void; resize: () => void; dispose: () => void } | null = null;
    let disposed = false;
    let cleanup: (() => void) | null = null;

    function buildOption() {
      const c = themeColors();
      const width = chartRef.current?.clientWidth ?? 1000;
      // Narrow viewports need a tighter cloud: the force defaults that look right
      // at desktop width push nodes (and their right-hand labels) past both edges
      // on mobile, where they are simply clipped away.
      const narrow = width < 700;
      const legendRows = narrow ? 3 : 1;

      return {
        tooltip: {
          formatter: (p: { dataType?: string; data?: Record<string, unknown>; name?: string }) => {
            if (p.dataType === "edge") {
              const d = p.data as unknown as GraphLink;
              return `${d.source} → ${d.target}<br/><em>${d.relation}</em>`;
            }
            const d = p.data as unknown as GraphNode;
            return `<strong>${d.name}</strong><br/>${CATEGORIES[d.category]?.name ?? ""}`;
          },
        },
        // Legend on top with the series box starting below it: left at the default
        // bottom placement it is painted over the graph, colliding with node labels.
        legend: [
          {
            data: CATEGORIES.map((a) => a.name),
            top: 8,
            left: "center",
            itemGap: narrow ? 8 : 16,
            textStyle: { color: c.text, fontSize: narrow ? 10 : 12 },
          },
        ],
        series: [
          {
            name: "Arquitectura",
            type: "graph",
            layout: "force",
            data: NODES,
            links: LINKS,
            categories: CATEGORIES,
            roam: true,
            draggable: true,
            // Reserve room for the legend and keep labels inside the canvas.
            top: 20 + legendRows * 22,
            bottom: 16,
            // Labels sit to the right of a node, so they need side margin to stay in
            // frame. On narrow screens that margin eats the usable width, so labels
            // move under the node instead and the margins shrink back down.
            left: narrow ? 45 : 90,
            right: narrow ? 45 : 90,
            label: {
              show: true,
              position: narrow ? "bottom" : "right",
              color: c.text,
              fontSize: narrow ? 10 : 12,
            },
            labelLayout: { hideOverlap: true },
            itemStyle: { borderColor: c.panel, borderWidth: 1.5 },
            lineStyle: { color: c.border, width: 1.5, curveness: 0.15, opacity: 0.9 },
            emphasis: { focus: "adjacency", lineStyle: { width: 3, color: c.accent } },
            scaleLimit: { min: 0.4, max: 2 },
            force: {
              repulsion: narrow ? 200 : 320,
              gravity: narrow ? 0.12 : 0.08,
              edgeLength: narrow ? 90 : 130,
            },
          },
        ],
      };
    }

    (async () => {
      try {
        const echarts = await import("echarts");
        if (disposed || !chartRef.current) return;

        chart = echarts.init(chartRef.current);
        chart.setOption(buildOption());
        setLoading(false);

        // Re-push the option, not just resize(): the force parameters and legend
        // sizing are derived from the container width, so a plain resize would
        // keep the desktop layout on a narrowed viewport.
        const onResize = () => {
          chart?.resize();
          chart?.setOption(buildOption());
        };
        window.addEventListener("resize", onResize);

        // Colours are baked into the canvas at draw time, so a theme flip has to
        // re-push the option -- CSS alone cannot restyle what is already painted.
        const themeObserver = new MutationObserver(() => chart?.setOption(buildOption()));
        themeObserver.observe(document.documentElement, {
          attributes: true,
          attributeFilter: ["data-theme"],
        });

        cleanup = () => {
          window.removeEventListener("resize", onResize);
          themeObserver.disconnect();
          chart?.dispose();
        };
      } catch (err) {
        if (!disposed) {
          setError(err instanceof Error ? err.message : "No se pudo cargar el gráfico.");
          setLoading(false);
        }
      }
    })();

    return () => {
      disposed = true;
      cleanup?.();
    };
  }, []);

  return (
    <div style={{ width: "100%", marginBottom: 30 }}>
      <h2 style={{ marginTop: 0 }}>Arquitectura del sistema</h2>
      <p className="wizard-note" style={{ marginBottom: 16 }}>
        Cómo se conectan las piezas de la plataforma. Arrastrá los nodos para reorganizar,
        usá la rueda del mouse para hacer zoom y pasá el cursor sobre un nodo para resaltar
        sus relaciones.
      </p>

      {/* position:relative anchors the loading overlay to the chart box -- without it
          the absolutely-positioned overlay escapes to the nearest positioned ancestor. */}
      <div style={{ position: "relative" }}>
        <div
          ref={chartRef}
          style={{
            width: "100%",
            height: 500,
            border: "1px solid var(--border)",
            borderRadius: 6,
            background: "var(--panel)",
          }}
        />
        {loading && !error && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--muted)",
            }}
          >
            Cargando gráfico…
          </div>
        )}
        {error && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--danger)",
            }}
          >
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
