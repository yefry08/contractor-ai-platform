import "./globals.css";
import type { ReactNode } from "react";
import { Navbar } from "@/components/navbar";

export const metadata = {
  title: "Contractor AI — Transparencia en contratación pública",
  description:
    "Búsqueda y detección de anomalías en contratos públicos (Fase 1: Paraguay).",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es">
      <body>
        <Navbar />
        <main className="container">{children}</main>

        <footer className="site">
          <div className="footer-bottom">
            <span>Contractor AI — Desafío de Transparencia PIDA (OEA)</span>
            <nav className="footer-links">
              <a href="/">Contratos</a>
              <a href="/anomalies">Anomalías</a>
              <a href="https://hackcorruption.org" target="_blank" rel="noopener noreferrer">
                Hackcorruption
              </a>
            </nav>
          </div>
        </footer>
      </body>
    </html>
  );
}
