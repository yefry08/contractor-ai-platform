"use client";

import { useState } from "react";
import { ThemeToggle } from "@/components/theme-toggle";

export function Navbar() {
  const [open, setOpen] = useState(false);

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
          aria-label={open ? "Cerrar menú" : "Abrir menú"}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          <span />
          <span />
          <span />
        </button>

        <nav className={`navbar-links ${open ? "navbar-links-open" : ""}`}>
          <a href="/" onClick={() => setOpen(false)}>
            Explorar contratos
          </a>
          <a href="/analyze" onClick={() => setOpen(false)}>
            Analizar un contrato
          </a>
          <a href="/anomalies" onClick={() => setOpen(false)}>
            Anomalías detectadas
          </a>
          <span className="navbar-link-muted" title="Próximamente">
            Panel institucional
          </span>
          <span className="navbar-link-muted" title="Próximamente">
            API
          </span>
          <a href="/analyze" className="navbar-cta navbar-cta-mobile" onClick={() => setOpen(false)}>
            Analizar contrato
          </a>
          <div className="navbar-theme-mobile">
            <ThemeToggle />
          </div>
        </nav>

        <div className="navbar-actions">
          <span className="navbar-tag">ES · datos abiertos OCDS</span>
          <ThemeToggle />
          <a href="/analyze" className="navbar-cta">
            Analizar contrato
          </a>
        </div>
      </div>
    </header>
  );
}
