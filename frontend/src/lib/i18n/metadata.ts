import type { Metadata } from "next";
import { isLocale } from "./config";
import { getDictionary, type Dictionary } from "./dictionaries";

/** Build a `generateMetadata` that sets the localised page title. */
export function pageMetadata(page: keyof Dictionary["meta"]["pages"]) {
  return async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
    const { locale } = await params;
    if (!isLocale(locale)) return {};
    return { title: getDictionary(locale).meta.pages[page] };
  };
}
