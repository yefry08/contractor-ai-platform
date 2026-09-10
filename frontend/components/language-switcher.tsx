"use client";

import { useLanguage } from "@/lib/language-context";
import { LANGUAGES, isLanguage } from "@/lib/i18n";
import styles from "./language-switcher.module.css";

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
        onChange={(e) => {
          if (isLanguage(e.target.value)) setLanguage(e.target.value);
        }}
        className={styles.select}
      >
        {LANGUAGES.map((lang) => (
          <option key={lang.code} value={lang.code}>
            {lang.ready ? lang.label : `${lang.label} (${t("language.pending")})`}
          </option>
        ))}
      </select>
    </div>
  );
}
