import "./globals.css";
import type { ReactNode } from "react";
import { Navbar } from "@/components/navbar";
import { LanguageProvider } from "@/lib/language-context";
import { COUNTRIES } from "@/lib/countries";
import { translate } from "@/lib/i18n";
import { getServerLanguage } from "@/lib/i18n-server";

export const metadata = {
  title: "Contractor AI — Transparencia en contratación pública",
  description: `Búsqueda y detección de anomalías en contratos públicos. Cubre ${COUNTRIES.length} países: ${COUNTRIES.map((c) => c.name).join(", ")}.`,
};

const THEME_INIT_SCRIPT = `try{if(localStorage.getItem('theme')==='dark')document.documentElement.setAttribute('data-theme','dark')}catch(e){}`;

export default async function RootLayout({ children }: { children: ReactNode }) {
  const language = await getServerLanguage();

  return (
    <html lang={language}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body>
        <LanguageProvider initialLanguage={language}>
          <Navbar />
          <main className="container">{children}</main>

          <footer className="site">
            <div className="footer-bottom">
              <span>Contractor AI — Desafío de Transparencia PIDA (OEA)</span>
              <nav className="footer-links">
                <a href="/">{translate(language, "nav.contracts")}</a>
                <a href="/anomalies">{translate(language, "nav.anomalies")}</a>
                <a href="https://hackcorruption.org" target="_blank" rel="noopener noreferrer">
                  Hackcorruption
                </a>
              </nav>
            </div>
          </footer>
        </LanguageProvider>
      </body>
    </html>
  );
}
