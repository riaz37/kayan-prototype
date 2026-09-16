"use client";

import type { ReactNode } from "react";
import { SWRConfig } from "swr";
import { DirectionProvider } from "@/components/ui/direction";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { fetcher } from "@/lib/api/client";
import { dirOf, type Locale } from "@/lib/i18n/config";
import type { Dictionary } from "@/lib/i18n/dictionaries";
import { I18nProvider } from "./i18n-provider";
import { SessionProvider } from "./session-provider";
import { RuntimeProvider } from "./runtime-provider";

export function Providers({
  locale,
  dictionary,
  backendUrl,
  children,
}: {
  locale: Locale;
  dictionary: Dictionary;
  backendUrl: string;
  children: ReactNode;
}) {
  const dir = dirOf(locale);
  return (
    <I18nProvider locale={locale} dictionary={dictionary}>
      <DirectionProvider dir={dir}>
        <SWRConfig
          value={{
            fetcher,
            dedupingInterval: 4000,
            errorRetryCount: 2,
            keepPreviousData: true,
          }}
        >
          <TooltipProvider delayDuration={200}>
            <RuntimeProvider backendUrl={backendUrl}>
              <SessionProvider>{children}</SessionProvider>
            </RuntimeProvider>
            <Toaster dir={dir} position={dir === "rtl" ? "bottom-left" : "bottom-right"} richColors={false} closeButton />
          </TooltipProvider>
        </SWRConfig>
      </DirectionProvider>
    </I18nProvider>
  );
}
