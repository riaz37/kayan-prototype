"use client";

import { Suspense, type ReactNode } from "react";
import { DetailSheets } from "@/components/details/detail-sheets";
import { useI18n } from "@/components/providers/i18n-provider";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";

const SERVICES_PHONE = "0506094154";

export function AppShell({ children }: { children: ReactNode }) {
  const { t, format } = useI18n();
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main id="main" className="mx-auto w-full max-w-[1400px] flex-1 p-4 sm:p-6">
          {children}
        </main>
        <footer className="border-t border-line-soft px-6 py-4 text-center text-[11.5px] text-ink-soft">
          {format(t.footer, { phone: SERVICES_PHONE })}
        </footer>
      </div>
      <Suspense fallback={null}>
        <DetailSheets />
      </Suspense>
    </div>
  );
}
