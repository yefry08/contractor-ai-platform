"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { LANGUAGE_COOKIE, numberLocale, translate, type Language, type Vars } from "./i18n";

export type { Language };

export interface LanguageContextType {
  language: Language;
  locale: string;
  setLanguage: (lang: Language) => void;
  t: (key: string, vars?: Vars) => string;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export function LanguageProvider({
  initialLanguage,
  children,
}: {
  initialLanguage: Language;
  children: ReactNode;
}) {
  const [language, setLanguageState] = useState<Language>(initialLanguage);
  const router = useRouter();

  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  const setLanguage = (lang: Language) => {
    setLanguageState(lang);
    document.cookie = `${LANGUAGE_COOKIE}=${lang}; path=/; max-age=31536000; samesite=lax`;
    // Server-rendered pages read the cookie, so re-render them in the new language.
    router.refresh();
  };

  const value: LanguageContextType = {
    language,
    locale: numberLocale(language),
    setLanguage,
    t: (key, vars) => translate(language, key, vars),
  };

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage(): LanguageContextType {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLanguage must be used within a LanguageProvider");
  }
  return context;
}
