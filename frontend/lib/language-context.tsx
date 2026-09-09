"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import es from "./translations/es.json";
import pt from "./translations/pt.json";
import gn from "./translations/gn.json";
import qu from "./translations/qu.json";
import en from "./translations/en.json";

export type Language = "es" | "pt" | "gn" | "qu" | "en";

export interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: string) => string;
}

const translations: Record<Language, Record<string, any>> = {
  es,
  pt,
  gn,
  qu,
  en,
};

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState<Language>("es");
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    // Load saved language preference from localStorage
    const saved = localStorage.getItem("contractor-ai-language") as Language | null;
    if (saved && Object.keys(translations).includes(saved)) {
      setLanguageState(saved);
    }
    setIsMounted(true);
  }, []);

  const setLanguage = (lang: Language) => {
    if (Object.keys(translations).includes(lang)) {
      setLanguageState(lang);
      localStorage.setItem("contractor-ai-language", lang);
    }
  };

  const t = (key: string): string => {
    const keys = key.split(".");
    let value: any = translations[language];

    for (const k of keys) {
      if (value && typeof value === "object") {
        value = value[k];
      } else {
        return key; // Return key if translation not found
      }
    }

    return typeof value === "string" ? value : key;
  };

  // Don't render until mounted to avoid hydration mismatch
  if (!isMounted) {
    return <>{children}</>;
  }

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage(): LanguageContextType {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLanguage must be used within a LanguageProvider");
  }
  return context;
}
