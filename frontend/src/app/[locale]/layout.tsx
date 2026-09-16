import type { Metadata, Viewport } from "next";
import { notFound } from "next/navigation";
import { Providers } from "@/components/providers/providers";
import { dirOf, isLocale, locales } from "@/lib/i18n/config";
import { getDictionary } from "@/lib/i18n/dictionaries";
import "../globals.css";

export const dynamicParams = false;

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

export const viewport: Viewport = {
  themeColor: "#0F8478",
};

export async function generateMetadata({ params }: LayoutProps<"/[locale]">): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  const t = getDictionary(locale);
  return {
    title: { default: t.meta.title, template: `%s — ${t.brand.name}` },
    description: t.meta.description,
    alternates: { languages: { ar: "/ar", en: "/en" } },
    robots: { index: false, follow: false },
  };
}

export default async function LocaleLayout({ children, params }: LayoutProps<"/[locale]">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const dictionary = getDictionary(locale);
  // Shown in the topbar badge so it is obvious which database the console is reading.
  const backendUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

  return (
    <html lang={locale} dir={dirOf(locale)} className="h-full">
      <head>
        <link rel="preload" href="/fonts/plex-ar-400.woff2" as="font" type="font/woff2" crossOrigin="" />
        <link rel="preload" href="/fonts/plex-la-400.woff2" as="font" type="font/woff2" crossOrigin="" />
      </head>
      <body className="min-h-full">
        <Providers locale={locale} dictionary={dictionary} backendUrl={backendUrl}>
          {children}
        </Providers>
      </body>
    </html>
  );
}
