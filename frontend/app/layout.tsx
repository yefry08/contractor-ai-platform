import "./globals.css";
import type { ReactNode } from "react";
import { Inter_Tight } from "next/font/google";
import { Navbar } from "@/components/navbar";
import { LanguageProvider } from "@/lib/language-context";
import { COUNTRIES } from "@/lib/countries";
import { translate } from "@/lib/i18n";
import { getServerLanguage } from "@/lib/i18n-server";

export const metadata = {
  title: "Contractor AI — Transparencia en contratación pública",
  description: `Búsqueda y detección de anomalías en contratos públicos. Cubre ${COUNTRIES.length} países: ${COUNTRIES.map((c) => c.name).join(", ")}.`,
};

const THEME_INIT_SCRIPT = `try{const theme=localStorage.getItem('theme-v2')==='dark'?'dark':'light';document.documentElement.setAttribute('data-theme',theme)}catch(e){}`;

// The closest free match for Söhne, the grotesque humata.ai sets everything in.
const sans = Inter_Tight({ subsets: ["latin"], weight: ["400", "500", "600", "700"], variable: "--font-sans", display: "swap" });

export default async function RootLayout({ children }: { children: ReactNode }) {
  const language = await getServerLanguage();

  return (
    // Day by default; THEME_INIT_SCRIPT restores night before the first
    // paint when the visitor chose it, so the page never flashes light first.
    <html lang={language} data-theme="light" className={sans.variable} suppressHydrationWarning>
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
