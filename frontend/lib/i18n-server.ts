import { cookies } from "next/headers";
import {
  DEFAULT_LANGUAGE,
  LANGUAGE_COOKIE,
  isLanguage,
  numberLocale,
  translate,
  type Language,
  type Vars,
} from "./i18n";

export async function getServerLanguage(): Promise<Language> {
  const value = (await cookies()).get(LANGUAGE_COOKIE)?.value;
  return isLanguage(value) ? value : DEFAULT_LANGUAGE;
}

export async function getServerT() {
  const language = await getServerLanguage();
  return {
    language,
    locale: numberLocale(language),
    t: (key: string, vars?: Vars) => translate(language, key, vars),
  };
}
