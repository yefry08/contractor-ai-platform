import es from "./translations/es.json";
import pt from "./translations/pt.json";
import en from "./translations/en.json";

export type Language = "es" | "pt" | "gn" | "qu" | "en";
export type Vars = Record<string, string | number>;
type Dict = { [key: string]: string | Dict };

export const DEFAULT_LANGUAGE: Language = "es";
export const LANGUAGE_COOKIE = "contractor-ai-language";

// No Guaraní/Quechua dictionaries until native speakers supply them; those fall back to Spanish.
const DICTIONARIES: Partial<Record<Language, Dict>> = { es, pt, en };

export const LANGUAGES: { code: Language; label: string; ready: boolean }[] = [
  { code: "es", label: "Español", ready: true },
  { code: "pt", label: "Português", ready: true },
  { code: "gn", label: "Guaraní", ready: false },
  { code: "qu", label: "Quechua", ready: false },
  { code: "en", label: "English", ready: true },
];

export function isLanguage(value: string | null | undefined): value is Language {
  return LANGUAGES.some((l) => l.code === value);
}

export function numberLocale(language: Language): string {
  if (language === "pt") return "pt-BR";
  if (language === "en") return "en-US";
  return "es";
}

function lookup(dict: Dict | undefined, key: string): string | undefined {
  let node: string | Dict | undefined = dict;
  for (const part of key.split(".")) {
    if (typeof node !== "object") return undefined;
    node = node[part];
  }
  return typeof node === "string" ? node : undefined;
}

export function translate(language: Language, key: string, vars?: Vars): string {
  const text = lookup(DICTIONARIES[language], key) ?? lookup(es, key) ?? key;
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (match, name: string) => (name in vars ? String(vars[name]) : match));
}
