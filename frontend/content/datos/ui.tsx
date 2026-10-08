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

export const es = (n: number, digits = 0) => n.toLocaleString("es", { maximumFractionDigits: digits, minimumFractionDigits: digits });
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
