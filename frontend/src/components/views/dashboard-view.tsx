"use client";

import Link from "next/link";
import { useSyncExternalStore } from "react";
import { Check, ChevronRight, House, MessageCircle, Phone, SquareKanban, Ticket, Users, Wallet } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardAction, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { DataText, Stat } from "@/components/kayan/primitives";
import { ShowExpiredToggle } from "@/components/kayan/show-expired-toggle";
import { TONE_CHIP, toneFor } from "@/components/kayan/tones";
import { useI18n } from "@/components/providers/i18n-provider";
import { useKanban, useOverview, usePrograms, useStats } from "@/lib/api/hooks";
import { keyFromArabic } from "@/lib/i18n/catalog";
import { isCardExpired } from "@/lib/tickets";
import { useShowExpired } from "@/lib/use-show-expired";
import { cn } from "@/lib/utils";

const subscribeNoop = () => () => {};

/** Time-of-day content differs between server and browser, so render it after hydration. */
function useIsClient() {
  return useSyncExternalStore(subscribeNoop, () => true, () => false);
}

export function DashboardView() {
  const { t, fmt, format, rich, label, locale } = useI18n();
  const stats = useStats();
  const kanban = useKanban();
  const overview = useOverview();
  const programs = usePrograms();
  const isClient = useIsClient();
  const [showExpired, setShowExpired] = useShowExpired();
  const allColumns = kanban.data?.columns ?? [];
  const expiredCount = allColumns.reduce((n, c) => n + c.cards.filter(isCardExpired).length, 0);
  const boardColumns = allColumns.map((c) => ({
    ...c,
    cards: showExpired ? c.cards : c.cards.filter((card) => !isCardExpired(card)),
  }));
  const base = `/${locale}`;

  const s = stats.data;
  const o = overview.data;

  const now = new Date();
  const hour = now.getHours();
  const greeting = hour < 12 ? t.dashboard.greetingMorning : hour < 17 ? t.dashboard.greetingAfternoon : t.dashboard.greetingEvening;

  const programCounts = Object.entries(o?.programs ?? {}).map(([arabic, count]) => {
    const id = programs.data?.programs.find((p) => p.name_ar === arabic)?.id ?? keyFromArabic("program", arabic);
    return { key: id ?? arabic, name: label("program", id, arabic), count };
  });
  const maxProgram = Math.max(1, ...programCounts.map((p) => p.count));

  return (
    <div className="space-y-5">
      <Card className="relative overflow-hidden border-brand-100/70 via-white to-white ltr:bg-linear-to-r ltr:from-brand-50/70 rtl:bg-linear-to-l rtl:from-brand-50/70">
        <div className="absolute -end-16 -top-20 size-72 rounded-full bg-brand-100/30 blur-3xl" />
        <div className="relative flex flex-wrap items-center justify-between gap-5 px-6 py-6">
          <div>
            <div className="mb-1.5 flex items-center gap-2 text-[12px] font-medium text-brand-700">
              <span className="size-1.5 animate-pulse rounded-full bg-emerald-500" />
              {t.dashboard.systemUp}
              {isClient && <> — {fmt.longDate(now)}</>}
            </div>
            <h1 className="text-[26px] font-semibold tracking-tight text-ink">
              {isClient ? format(t.dashboard.greeting, { greeting }) : <span className="invisible">—</span>}
            </h1>
            <p className="mt-1 text-[13px] text-ink-muted">
              {rich(t.dashboard.todaySummary, {
                today: <b className="font-semibold text-ink tabular">{fmt.number(s?.today ?? 0)}</b>,
                hours: <b className="font-semibold text-ink tabular">{fmt.hours(s?.avg_first_response_hours ?? 0)}</b>,
              })}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href={`${base}/kanban`} className={buttonVariants({ variant: "outline", size: "lg" })}>
              <SquareKanban /> {t.nav.kanban}
            </Link>
            <Link href={`${base}/beneficiaries`} className={buttonVariants({ size: "lg" })}>
              <Users /> {t.nav.beneficiaries}
            </Link>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatLink href={`${base}/tickets`}>
          <Stat
            label={t.dashboard.totalTickets}
            value={fmt.number(s?.total ?? 0)}
            icon={Ticket}
            tone="brand"
            loading={stats.isLoading}
            hint={format(t.dashboard.ticketsHint, { open: s?.by_status?.open ?? 0, closed: s?.by_status?.closed ?? 0 })}
          />
        </StatLink>
        <Stat
          label={t.dashboard.closureRate}
          value={`${fmt.decimal(s?.closure_rate_pct ?? 0)}%`}
          icon={Check}
          tone="green"
          loading={stats.isLoading}
          hint={format(t.dashboard.slaBreachedHint, { n: s?.sla_breached ?? 0 })}
        />
        <StatLink href={`${base}/beneficiaries`}>
          <Stat
            label={t.dashboard.beneficiaryFiles}
            value={fmt.number(o?.beneficiaries?.total ?? 0)}
            icon={Users}
            tone="violet"
            loading={overview.isLoading}
            hint={format(t.dashboard.filesHint, {
              approved: o?.beneficiaries?.by_status?.approved ?? 0,
              dependents: o?.beneficiaries?.dependents ?? 0,
            })}
          />
        </StatLink>
        <StatLink href={`${base}/finance`}>
          <Stat
            label={t.dashboard.totalPaid}
            value={fmt.money(o?.payments_total_sar ?? 0)}
            icon={Wallet}
            tone="amber"
            loading={overview.isLoading}
            hint={format(t.dashboard.sponsorshipsHint, { amount: fmt.money(o?.sponsorships?.monthly_sar ?? 0) })}
          />
        </StatLink>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <div>
              <CardTitle>{t.dashboard.kanbanTitle}</CardTitle>
              <CardDescription>{t.dashboard.kanbanSub}</CardDescription>
            </div>
            <CardAction className="flex flex-wrap items-center justify-end gap-2">
              <ShowExpiredToggle checked={showExpired} onChange={setShowExpired} count={expiredCount} className="h-8 text-[12.5px]" />
              <Link href={`${base}/kanban`} className={buttonVariants({ variant: "ghost", size: "sm" })}>
                {t.common.viewAll} <ChevronRight className="size-3.5 rtl:-scale-x-100" />
              </Link>
            </CardAction>
          </CardHeader>
          <div className="grid grid-cols-2 gap-3 px-5 pb-5 sm:grid-cols-4">
            {kanban.isLoading && Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
            {boardColumns.map((col) => (
              <Link
                key={col.status}
                href={`${base}/kanban`}
                className="rounded-xl border border-line bg-line-soft/40 p-3 text-start transition-all hover:bg-white hover:shadow-card"
              >
                <div className="mb-2 flex items-center justify-between gap-2">
                  <Badge tone={toneFor(col.status)} dot>
                    {label("ticketStatus", col.status, col.title_ar)}
                  </Badge>
                  <span className="text-[19px] font-semibold text-ink tabular">{col.cards.length}</span>
                </div>
                <div className="space-y-1">
                  {col.cards.slice(0, 2).map((c) => (
                    <p key={c.id} className="truncate text-[11.5px] text-ink-muted">
                      <DataText>{c.subject_ar}</DataText>
                    </p>
                  ))}
                  {!col.cards.length && (
                    <p className="text-[11.5px] text-ink-soft">{col.count ? t.common.noActiveTickets : t.dashboard.noTickets}</p>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>{t.dashboard.byProgramTitle}</CardTitle>
              <CardDescription>{t.dashboard.byProgramSub}</CardDescription>
            </div>
          </CardHeader>
          <div className="space-y-3 px-5 pb-5">
            {overview.isLoading && <Skeleton className="h-24" />}
            {programCounts.map((p) => (
              <div key={p.key}>
                <div className="mb-1.5 flex items-center justify-between text-[12.5px]">
                  <span className="text-ink">{p.name}</span>
                  <span className="text-ink-muted tabular">{fmt.number(p.count)}</span>
                </div>
                <Progress value={(p.count / maxProgram) * 100} />
              </div>
            ))}
            {!overview.isLoading && programCounts.length === 0 && (
              <p className="py-6 text-center text-[12.5px] text-ink-soft">{t.dashboard.noProgramData}</p>
            )}
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <div>
              <CardTitle>{t.dashboard.channelsTitle}</CardTitle>
              <CardDescription>{t.dashboard.channelsSub}</CardDescription>
            </div>
          </CardHeader>
          <div className="grid gap-3 px-5 pb-5 sm:grid-cols-3">
            {(
              [
                { key: "whatsapp", icon: MessageCircle, tone: "green" },
                { key: "call", icon: Phone, tone: "sky" },
                { key: "portal", icon: House, tone: "violet" },
              ] as const
            ).map((c) => (
              <div key={c.key} className="rounded-xl border border-line p-4">
                <span className={cn("mb-2.5 inline-flex rounded-lg p-2 ring-1 ring-inset", TONE_CHIP[c.tone])}>
                  <c.icon className="size-4" />
                </span>
                <p className="text-[22px] font-semibold text-ink tabular">{fmt.number(s?.by_channel?.[c.key] ?? 0)}</p>
                <p className="text-[12px] text-ink-muted">{label("channel", c.key)}</p>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>{t.dashboard.decisionsTitle}</CardTitle>
              <CardDescription>{t.dashboard.decisionsSub}</CardDescription>
            </div>
          </CardHeader>
          <div className="space-y-2.5 px-5 pb-5">
            {(["accepted", "docs_required", "declined"] as const).map((k) => (
              <div key={k} className="flex items-center justify-between rounded-lg border border-line px-3 py-2.5">
                <Badge tone={toneFor(k)} dot>
                  {label("decision", k)}
                </Badge>
                <span className="text-[15px] font-semibold text-ink tabular">
                  {fmt.number(o?.support_requests?.decisions?.[k] ?? 0)}
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

function StatLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link href={href} className="block rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-brand-300 [&>div]:h-full [&>div]:transition-shadow [&>div]:hover:shadow-pop">
      {children}
    </Link>
  );
}
