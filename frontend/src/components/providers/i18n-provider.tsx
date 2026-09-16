"use client";

import { createContext, useContext, useMemo, type ReactNode } from "react";
import { dirOf, type Locale } from "@/lib/i18n/config";
import { keyFromArabic, resolveLabel, type CatalogKind } from "@/lib/i18n/catalog";
import { createFormatters, format, rich, type Formatters } from "@/lib/i18n/format";
import type { Dictionary } from "@/lib/i18n/dictionaries";

type I18nValue = {
  locale: Locale;
  dir: "rtl" | "ltr";
  t: Dictionary;
  fmt: Formatters;
  format: typeof format;
  rich: typeof rich;
  /** Localised label for an API code / Arabic reference value. */
  label: (kind: CatalogKind, code?: string | null, arabic?: string | null) => string;
  /** A person's name as sent by the API, with backend placeholders ("غير مسجل") localised. */
  personName: (name?: string | null) => string;
};

const I18nContext = createContext<I18nValue | null>(null);

export function I18nProvider({
  locale,
  dictionary,
  children,
}: {
  locale: Locale;
  dictionary: Dictionary;
  children: ReactNode;
}) {
  const value = useMemo<I18nValue>(
    () => ({
      locale,
      dir: dirOf(locale),
      t: dictionary,
      fmt: createFormatters(locale, dictionary),
      format,
      rich,
      label: (kind, code, arabic) => resolveLabel(locale, kind, code, arabic) ?? "—",
      personName: (name) => {
        if (!name?.trim()) return "—";
        return keyFromArabic("personPlaceholder", name) ? (resolveLabel(locale, "personPlaceholder", null, name) ?? name) : name;
      },
    }),
    [locale, dictionary],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside <I18nProvider>");
  return ctx;
}
