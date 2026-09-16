"use client";

import { useState, type FormEvent } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Bell, KeyRound, Languages, LogOut, Menu } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { NameAvatar, SearchInput, DataText } from "@/components/kayan/primitives";
import { useI18n } from "@/components/providers/i18n-provider";
import { api } from "@/lib/api/client";
import { useHealth, useNotifications } from "@/lib/api/hooks";
import { ChangePasswordDialog } from "@/components/details/change-password-dialog";
import { useRuntime } from "@/components/providers/runtime-provider";
import { useSession } from "@/components/providers/session-provider";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { LOCALE_COOKIE, swapLocaleInPath, type Locale } from "@/lib/i18n/config";
import { cn } from "@/lib/utils";
import { AgentsCard, Logo, SidebarNav } from "./sidebar";
import { REQUEST_PARAM, TICKET_PARAM } from "./use-detail-nav";

function ConnectionBadge() {
  const { t, format } = useI18n();
  const { data, error, isLoading } = useHealth();
  const state = error ? "offline" : data ? "connected" : isLoading ? "checking" : "offline";
  const { backendUrl, isLocal } = useRuntime();
  const source = { url: backendUrl, local: isLocal };
  const badge = (
    <span
      role="status"
      className={cn(
        "hidden items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11.5px] font-medium ring-1 ring-inset sm:inline-flex",
        state === "connected" && "bg-emerald-50 text-emerald-700 ring-emerald-100",
        state === "offline" && "bg-rose-50 text-rose-700 ring-rose-100",
        state === "checking" && "bg-amber-50 text-amber-700 ring-amber-100",
      )}
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          state === "connected" && "animate-pulse bg-emerald-500",
          state === "offline" && "bg-rose-500",
          state === "checking" && "bg-amber-500",
        )}
      />
      {state === "connected" ? t.topbar.connected : state === "offline" ? t.topbar.offline : t.topbar.checking}
      {source && (
        <span className={cn("border-s border-current/30 ps-1.5", !source.local && "font-semibold")}>
          {source.local ? t.topbar.sourceLocal : t.topbar.sourceProduction}
        </span>
      )}
    </span>
  );
  if (!source) return badge;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{badge}</TooltipTrigger>
      <TooltipContent dir="ltr">{format(t.topbar.dataSource, { url: source.url })}</TooltipContent>
    </Tooltip>
  );
}

function Notifications() {
  const { t, fmt, dir } = useI18n();
  const { data } = useNotifications();
  const items = data?.notifications ?? [];
  return (
    <DropdownMenu dir={dir}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" className="relative" aria-label={t.topbar.notifications}>
          <Bell className="size-[18px]" />
          {items.length > 0 && (
            <span className="absolute end-1.5 top-1.5 size-1.5 rounded-full bg-rose-500 ring-2 ring-canvas" />
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 p-0">
        <DropdownMenuLabel className="px-3 py-2.5 text-[13px] font-semibold text-ink">{t.topbar.notifications}</DropdownMenuLabel>
        <DropdownMenuSeparator className="m-0" />
        {items.length === 0 ? (
          <p className="px-3 py-8 text-center text-[12.5px] text-ink-soft">{t.topbar.noNotifications}</p>
        ) : (
          <ul className="max-h-80 divide-y divide-line-soft overflow-y-auto">
            {items.slice(0, 20).map((n) => (
              <li key={n.id} className="px-3 py-2.5">
                <p className="line-clamp-2 text-[12.5px] leading-relaxed text-ink">
                  <DataText>{n.body_ar ?? n.body ?? "—"}</DataText>
                </p>
                <p className="mt-1 text-[11px] text-ink-soft tabular">
                  <DataText>{n.to ?? ""}</DataText> · {fmt.relative(n.sent_at ?? n.created_at)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function Topbar() {
  const { t, locale } = useI18n();
  const router = useRouter();
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const [query, setQuery] = useState("");
  const base = `/${locale}`;
  const other: Locale = locale === "ar" ? "en" : "ar";

  const switchLanguage = () => {
    document.cookie = `${LOCALE_COOKIE}=${other}; path=/; max-age=31536000; samesite=lax`;
    router.push(swapLocaleInPath(pathname, other) + window.location.search);
  };

  const onSearch = (e: FormEvent) => {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    if (/^TK-/i.test(q)) router.push(`${base}/tickets?${TICKET_PARAM}=${encodeURIComponent(q.toUpperCase())}`);
    else if (/^SR-/i.test(q)) router.push(`${base}/requests?${REQUEST_PARAM}=${encodeURIComponent(q.toUpperCase())}`);
    else router.push(`${base}/beneficiaries?q=${encodeURIComponent(q)}`);
    setQuery("");
  };

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-line bg-canvas/85 px-4 backdrop-blur sm:px-6">
      <Button
        variant="ghost"
        size="icon-sm"
        className="lg:hidden"
        onClick={() => setMenuOpen(true)}
        aria-label={t.topbar.openMenu}
      >
        <Menu className="size-5" />
      </Button>
      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent side="start" className="max-w-[280px] bg-white" closeLabel={t.topbar.closeMenu}>
          <SheetTitle className="sr-only">{t.nav.label}</SheetTitle>
          <div className="flex h-16 items-center border-b border-line-soft px-5">
            <Logo />
          </div>
          <SidebarNav onNavigate={() => setMenuOpen(false)} />
          <AgentsCard />
        </SheetContent>
      </Sheet>

      <form role="search" onSubmit={onSearch} className="hidden max-w-md flex-1 sm:block">
        <SearchInput
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t.topbar.searchPlaceholder}
          aria-label={t.topbar.searchLabel}
        />
      </form>

      <div className="ms-auto flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={switchLanguage}
          aria-label={t.topbar.switchLanguageLabel}
          lang={other}
          className="px-2.5 text-[12px]"
        >
          <Languages className="size-4" />
          {t.topbar.switchLanguage}
        </Button>
        <ConnectionBadge />
        <Notifications />
        <UserMenu />
      </div>
    </header>
  );
}


function UserMenu() {
  const { t, dir, label, locale } = useI18n();
  const { user, refresh } = useSession();
  const router = useRouter();
  const [changeOpen, setChangeOpen] = useState(false);
  if (!user) return null;

  const name = (dir === "rtl" ? user.name_ar : user.name_en || user.name_ar) || user.email || "";
  const signOut = async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      /* the cookie is cleared regardless */
    }
    toast.success(t.auth.signedOut);
    refresh();
    router.replace(`/${locale}/login`);
  };

  return (
    <>
      <DropdownMenu dir={dir}>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className="flex cursor-pointer items-center gap-2.5 rounded-lg border-s border-line ps-3 outline-none focus-visible:ring-2 focus-visible:ring-brand-300"
            aria-label={t.auth.myAccount}
          >
            <span className="hidden text-end leading-tight sm:block">
              <span className="block text-[12.5px] font-medium text-ink">{name}</span>
              <span className="block text-[10.5px] text-ink-soft">{label("role", user.role)}</span>
            </span>
            <NameAvatar name={name} size={34} />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-60">
          <DropdownMenuLabel className="px-3 py-2">
            <span className="block text-[13px] font-semibold text-ink">{name}</span>
            <span className="block text-[11.5px] text-ink-soft" dir="ltr">
              {user.email}
            </span>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => setChangeOpen(true)}>
            <KeyRound className="size-4" /> {t.auth.changePassword}
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => void signOut()}>
            <LogOut className="size-4" /> {t.auth.signOut}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <ChangePasswordDialog open={changeOpen} onOpenChange={setChangeOpen} />
    </>
  );
}
