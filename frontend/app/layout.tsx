import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "Contractor AI — Transparencia en contratación pública",
  description:
    "Búsqueda y detección de anomalías en contratos públicos (Fase 1: Paraguay).",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es">
      <body>
        <header className="site">
          <div className="container" style={{ paddingBottom: 0, marginBottom: 0 }}>
            <nav>
              <a href="/">Contratos</a>
              <a href="/anomalies">Anomalías</a>
            </nav>
          </div>
        </header>
        <main className="container">{children}</main>
      </body>
    </html>
  );
}
