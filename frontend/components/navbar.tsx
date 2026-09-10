"use client";

import { useState } from "react";
import { ThemeToggle } from "@/components/theme-toggle";
import { LanguageSwitcher } from "@/components/language-switcher";
import { useLanguage } from "@/lib/language-context";

export function Navbar() {
  const [open, setOpen] = useState(false);
  const { t } = useLanguage();

  return (
    <header className="navbar">
      <div className="navbar-inner">
        <a href="/" className="navbar-logo">
          <span className="navbar-logo-word">Contractor</span>
          <span className="navbar-logo-badge">AI</span>
        </a>

        <button
          type="button"
          className="navbar-burger"
          aria-label={open ? t("nav.closeMenu") : t("nav.openMenu")}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          <span />
          <span />
          <span />
        </button>

        <nav className={`navbar-links ${open ? "navbar-links-open" : ""}`}>
          <a href="/analyze" onClick={() => setOpen(false)}>
            {t("nav.analyze")}
          </a>
          <a href="/anomalies" onClick={() => setOpen(false)}>
            {t("nav.anomalies")}
          </a>
          <a href="/dashboard" onClick={() => setOpen(false)}>
            {t("nav.dashboard")}
          </a>
          <a href="/tenders" onClick={() => setOpen(false)}>
            {t("nav.tenders")}
          </a>
          <a href="mailto:yefrynunez45@gmail.com" className="navbar-cta navbar-cta-mobile" onClick={() => setOpen(false)}>
            {t("nav.contact")}
          </a>
          <div className="navbar-theme-mobile">
            <ThemeToggle />
          </div>
        </nav>

        <div className="navbar-actions">
          <LanguageSwitcher />
          <ThemeToggle />
          <a href="mailto:yefrynunez45@gmail.com" className="navbar-cta">
            {t("nav.contact")}
          </a>
        </div>
      </div>
    </header>
  );
}
