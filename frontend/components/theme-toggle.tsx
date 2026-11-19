"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { useLanguage } from "@/lib/language-context";

type Theme = "light" | "dark";

// Day is the default; the choice is remembered per visitor. The root
// element always carries an explicit data-theme, which the charts and
// Turnstile read to pick their palette.
export function ThemeToggle() {
  const { t } = useLanguage();
  const pathname = usePathname();
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    function syncTheme() {
      let next: Theme = "light";
      try {
        next = localStorage.getItem("theme") === "dark" ? "dark" : "light";
      } catch {
        next = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
      }

      if (document.documentElement.getAttribute("data-theme") !== next) {
        document.documentElement.setAttribute("data-theme", next);
      }
      setTheme(next);
    }

    syncTheme();
    const themeObserver = new MutationObserver(syncTheme);
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    window.addEventListener("themechange", syncTheme);
    window.addEventListener("storage", syncTheme);
    return () => {
      themeObserver.disconnect();
      window.removeEventListener("themechange", syncTheme);
      window.removeEventListener("storage", syncTheme);
    };
  }, [pathname]);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("theme", next);
    } catch {
      // Private mode or blocked storage: the switch still applies to this page.
    }
    window.dispatchEvent(new CustomEvent("themechange"));
  }

  const label = theme === "dark" ? t("nav.themeDay") : t("nav.themeNight");
  return (
    <button type="button" className="theme-toggle" onClick={toggle} aria-label={label} title={label}>
      {theme === "dark" ? (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
      ) : (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
        </svg>
      )}
    </button>
  );
}
