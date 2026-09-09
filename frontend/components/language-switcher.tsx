"use client";

import { useLanguage, type Language } from "@/lib/language-context";
import styles from "./language-switcher.module.css";

const LANGUAGES: { code: Language; label: string }[] = [
  { code: "es", label: "Español" },
  { code: "pt", label: "Português" },
  { code: "gn", label: "Guaraní" },
  { code: "qu", label: "Quechua" },
  { code: "en", label: "English" },
];

export function LanguageSwitcher() {
  const { language, setLanguage, t } = useLanguage();

  return (
    <div className={styles.container}>
      <label htmlFor="language-select" className={styles.label}>
        {t("language.select")}:
      </label>
      <select
        id="language-select"
        value={language}
        onChange={(e) => setLanguage(e.target.value as Language)}
        className={styles.select}
      >
        {LANGUAGES.map((lang) => (
          <option key={lang.code} value={lang.code}>
            {lang.label}
          </option>
        ))}
      </select>
    </div>
  );
}
