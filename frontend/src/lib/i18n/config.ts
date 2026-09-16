export const locales = ["ar", "en"] as const;
export type Locale = (typeof locales)[number];

export const defaultLocale: Locale = "ar";
export const LOCALE_COOKIE = "NEXT_LOCALE";

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (locales as readonly string[]).includes(value);
}

export function dirOf(locale: Locale): "rtl" | "ltr" {
  return locale === "ar" ? "rtl" : "ltr";
}

/** BCP-47 tag used for Intl formatting. Arabic keeps Latin digits, as the original console did. */
export function intlLocale(locale: Locale): string {
  return locale === "ar" ? "ar-SA-u-nu-latn" : "en-US";
}

/** Replace a leading /ar or /en segment (or add one) so the same page opens in another locale. */
export function swapLocaleInPath(pathname: string, next: Locale): string {
  const parts = pathname.split("/");
  if (isLocale(parts[1])) parts[1] = next;
  else parts.splice(1, 0, next);
  return parts.join("/") || `/${next}`;
}
