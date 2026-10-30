"use client";

/**
 * Cloudflare Turnstile: tells people from bots without a puzzle for most
 * visitors and without tracking cookies. Renders only when
 * NEXT_PUBLIC_TURNSTILE_SITE_KEY is set (see docs/security/cloudflare.md);
 * without it the API skips the check too, and forms fall back to the
 * honeypot and rate limits.
 *
 * A token is single-use: bump `resetKey` after each submit to get a new one.
 */

import { useEffect, useRef } from "react";
import { useLanguage } from "@/lib/language-context";

const SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
const SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

type TurnstileApi = {
  render: (el: HTMLElement, opts: Record<string, unknown>) => string;
  remove: (id: string) => void;
};

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

let scriptPromise: Promise<void> | null = null;

function loadScript(): Promise<void> {
  if (window.turnstile) return Promise.resolve();
  scriptPromise ??= new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = SCRIPT_SRC;
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => {
      scriptPromise = null;
      reject(new Error("turnstile script failed"));
    };
    document.head.appendChild(s);
  });
  return scriptPromise;
}

export const turnstileEnabled = Boolean(SITE_KEY);

export function Turnstile({ onToken, resetKey = 0 }: { onToken: (token: string | null) => void; resetKey?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const { language } = useLanguage();
  const onTokenRef = useRef(onToken);
  onTokenRef.current = onToken;

  useEffect(() => {
    if (!SITE_KEY || !ref.current) return;
    let widgetId: string | null = null;
    let cancelled = false;
    onTokenRef.current(null);
    loadScript()
      .then(() => {
        if (cancelled || !ref.current || !window.turnstile) return;
        widgetId = window.turnstile.render(ref.current, {
          sitekey: SITE_KEY,
          theme: document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light",
          language: language === "pt" ? "pt-br" : language === "en" ? "en" : "es",
          callback: (token: string) => onTokenRef.current(token),
          "expired-callback": () => onTokenRef.current(null),
          "error-callback": () => onTokenRef.current(null),
        });
      })
      .catch(() => onTokenRef.current(null));
    return () => {
      cancelled = true;
      if (widgetId && window.turnstile) window.turnstile.remove(widgetId);
    };
  }, [resetKey, language]);

  if (!SITE_KEY) return null;
  return <div ref={ref} className="turnstile-box" />;
}
