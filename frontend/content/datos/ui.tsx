import type { ReactNode } from "react";
import snapshot from "./snapshot.json";

export type Snapshot = typeof snapshot;
export const DATA: Snapshot = snapshot;

export const NAMES: Record<string, string> = {
  PY: "Paraguay",
  CO: "Colombia",
  CR: "Costa Rica",
  DO: "República Dominicana",
  PE: "Perú",
  SV: "El Salvador",
  BR: "Brasil",
  UY: "Uruguay",
  CL: "Chile",
  GT: "Guatemala",
};

// useGrouping "always": the "es" locale skips the separator on four-digit numbers
// (3843), but the titles here write 1.082, and a post shouldn't mix both.
export const es = (n: number, digits = 0) =>
  n.toLocaleString("es", { maximumFractionDigits: digits, minimumFractionDigits: digits, useGrouping: "always" });
export const pct = (n: number, digits = 0) => `${es(n * 100, digits)}%`;

export function Stats({ items }: { items: { value: string; label: string }[] }) {
  return (
    <div className="post-stats">
      {items.map((s) => (
        <div key={s.label} className="post-stat">
          <span className="post-stat-value">{s.value}</span>
          <span className="post-stat-label">{s.label}</span>
        </div>
      ))}
    </div>
  );
}

export function Figure({ title, caption, children }: { title: string; caption?: ReactNode; children: ReactNode }) {
  return (
    <figure className="post-figure card">
      <h3>{title}</h3>
      {children}
      {caption && <figcaption>{caption}</figcaption>}
    </figure>
  );
}

export function Method({ children }: { children: ReactNode }) {
  return (
    <aside className="post-method">
      <h2>Método y datos</h2>
      {children}
      <p>
        Cifras del corpus de Contractor AI al {new Date(DATA.generated + "T12:00:00").toLocaleDateString("es", { day: "numeric", month: "long", year: "numeric" })},
        calculadas con{" "}
        <a href="https://github.com/yefry08/contractor-ai-platform/blob/main/backend/scripts/build_datos_snapshot.py" target="_blank" rel="noopener noreferrer">
          backend/scripts/build_datos_snapshot.py
        </a>
        . Cada país tiene una muestra de distinto tamaño y período: los porcentajes describen esa muestra, no todo el gasto
        público del país.
      </p>
    </aside>
  );
}

export type WeekdayStats = {
  days: number[];
  top: { date: string; n: number }[];
  methods: { method: string; n: number }[];
};

// JSON imports widen tuples to (string | number)[], so the weekday figures are
// read once here with their real types.
export const WEEKDAY: Record<string, WeekdayStats> = Object.fromEntries(
  Object.entries(DATA.weekday).map(([code, w]) => {
    const raw = w as { days: number[]; top_weekend_dates: (string | number)[][]; weekend_methods?: (string | number)[][] };
    return [
      code,
      {
        days: raw.days,
        top: raw.top_weekend_dates.map(([date, , n]) => ({ date: String(date), n: Number(n) })),
        methods: (raw.weekend_methods ?? []).map(([method, n]) => ({ method: String(method), n: Number(n) })),
      },
    ];
  }),
);
