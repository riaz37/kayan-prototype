"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Sparkles } from "lucide-react";
import { useI18n } from "@/components/providers/i18n-provider";
import { useSession } from "@/components/providers/session-provider";
import { cn } from "@/lib/utils";
import { NAV } from "./nav";

export function Logo() {
  const { t, locale } = useI18n();
  return (
    <Link href={`/${locale}`} className="flex items-center gap-2.5 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-brand-300">
      <div className="relative grid size-9 place-items-center rounded-xl bg-brand-600 shadow-sm">
        <span className="text-[15px] leading-none font-bold text-white">{t.brand.mark}</span>
        <span className="absolute -end-0.5 -bottom-0.5 size-2.5 rounded-[4px] bg-brand-300 ring-2 ring-white" />
      </div>
      <div className="leading-tight">
        <p className="text-[14px] font-semibold text-ink">{t.brand.name}</p>
        <p className="text-[10.5px] text-ink-soft">{t.brand.tagline}</p>
      </div>
    </Link>
  );
}

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const { t, locale } = useI18n();
  const pathname = usePathname();
  const { can } = useSession();
  const base = `/${locale}`;
  const groups = NAV.map((g) => ({ ...g, items: g.items.filter((i) => !i.permission || can(i.permission)) })).filter(
    (g) => g.items.length > 0,
  );

  return (
    <nav aria-label={t.nav.label} className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
      {groups.map((group) => (
        <div key={group.key}>
          <p className="mb-1.5 px-2.5 text-[10.5px] font-medium tracking-wide text-ink-soft">{t.nav.groups[group.key]}</p>
          <div className="space-y-0.5">
            {group.items.map((item) => {
              const href = base + item.href;
              const active = item.href === "" ? pathname === base || pathname === `${base}/` : pathname.startsWith(href);
              const Icon = item.icon;
              return (
                <Link
                  key={item.key}
                  href={href}
                  onClick={onNavigate}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex h-9 w-full items-center gap-2.5 rounded-lg px-2.5 text-[13px] font-medium transition-all outline-none focus-visible:ring-2 focus-visible:ring-brand-300",
                    active ? "bg-brand-50 text-brand-700" : "text-ink-muted hover:bg-line-soft hover:text-ink",
                  )}
                >
                  <Icon className={cn("size-[17px] shrink-0", active && "text-brand-600")} strokeWidth={1.8} />
                  <span className="truncate">{t.nav[item.key]}</span>
                  {active && <span className="ms-auto h-4 w-1 rounded-full bg-brand-500" />}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}

export function AgentsCard() {
  const { t } = useI18n();
  return (
    <div className="border-t border-line-soft p-3">
      <div className="rounded-xl border border-brand-100/70 from-brand-50 to-white p-3 ltr:bg-linear-to-r rtl:bg-linear-to-l">
        <div className="mb-1.5 flex items-center gap-2">
          <Sparkles className="size-3.5 text-brand-600" />
          <p className="text-[12px] font-medium text-brand-900">{t.sidebar.agentsTitle}</p>
        </div>
        <p className="text-[11px] leading-relaxed text-brand-800/80">{t.sidebar.agentsBody}</p>
      </div>
    </div>
  );
}

/** Desktop sidebar (lg and up). On smaller screens the same content opens in a sheet from the topbar. */
export function Sidebar() {
  return (
    <aside className="sticky top-0 z-30 hidden h-screen w-[248px] shrink-0 flex-col border-e border-line bg-white lg:flex">
      <div className="flex h-16 items-center border-b border-line-soft px-5">
        <Logo />
      </div>
      <SidebarNav />
      <AgentsCard />
    </aside>
  );
}
