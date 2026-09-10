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

type Dict = { [key: string]: string | Dict };

const translations: Record<Language, Dict> = { es, pt, gn, qu, en };
const STORAGE_KEY = "contractor-ai-language";

function isLanguage(value: string | null): value is Language {
  return value !== null && value in translations;
}

function lookup(dict: Dict, key: string): string | undefined {
  let node: string | Dict | undefined = dict;
  for (const part of key.split(".")) {
    if (typeof node !== "object") return undefined;
    node = node[part];
  }
  return typeof node === "string" ? node : undefined;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  // The provider must wrap children on every render, including the server
  // render: consumers throw without it. Start from Spanish (what the server
  // renders) and switch to the saved choice after mount.
  const [language, setLanguageState] = useState<Language>("es");

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (isLanguage(saved)) setLanguageState(saved);
    } catch {}
  }, []);

  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  const setLanguage = (lang: Language) => {
    setLanguageState(lang);
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch {}
  };

  const t = (key: string): string =>
    lookup(translations[language], key) ?? lookup(translations.es, key) ?? key;

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
