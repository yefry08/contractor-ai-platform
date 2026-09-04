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
          <a href="/analyze" onClick={() => setOpen(false)}>
            Analizar contratos
          </a>
          <a href="/anomalies" onClick={() => setOpen(false)}>
            Anomalías detectadas
          </a>
          <a href="/dashboard" onClick={() => setOpen(false)}>
            Panel
          </a>
          <a href="/tenders" onClick={() => setOpen(false)}>
            Licitaciones
          </a>
          <a href="mailto:yefrynunez45@gmail.com" className="navbar-cta navbar-cta-mobile" onClick={() => setOpen(false)}>
            Contáctanos
          </a>
          <div className="navbar-theme-mobile">
            <ThemeToggle />
          </div>
        </nav>

        <div className="navbar-actions">
          <span className="navbar-tag">ES · datos abiertos OCDS</span>
          <ThemeToggle />
          <a href="mailto:yefrynunez45@gmail.com" className="navbar-cta">
            Contáctanos
          </a>
        </div>
      </div>
    </header>
  );
}
