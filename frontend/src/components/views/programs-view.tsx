"use client";

import { useState } from "react";
import { FileText, Gift, House, Scale, Sparkles, type LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Empty, LoadError, PageHead } from "@/components/kayan/primitives";
import { useI18n } from "@/components/providers/i18n-provider";
import { usePrograms, useRequestTypes } from "@/lib/api/hooks";
import type { Program } from "@/lib/api/types";

const ICONS: Record<string, LucideIcon> = {
  "PRG-ILM": FileText,
  "PRG-TRN": Sparkles,
  "PRG-QOL": Gift,
  "PRG-HSG": House,
  "PRG-VAL": Scale,
};

export function ProgramsView() {
  const { t, format, label } = useI18n();
  const programs = usePrograms();
  const [open, setOpen] = useState<Program | null>(null);
  const list = programs.data?.programs ?? [];
  const totalTypes = list.reduce((sum, p) => sum + (p.request_types_count ?? 0), 0);

  return (
    <div className="space-y-4">
      <PageHead
        title={t.programs.title}
        sub={list.length ? format(t.programs.sub, { programs: list.length, types: totalTypes }) : undefined}
      />
      {programs.error && !programs.data ? (
        <Card>
          <LoadError onRetry={() => programs.mutate()} />
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {programs.isLoading && Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-40 rounded-xl" />)}
          {list.map((p, i) => {
            const Icon = ICONS[p.id] ?? FileText;
            return (
              <Card key={p.id} hover className="animate-enter" style={{ animationDelay: `${i * 50}ms` }}>
                <button
                  type="button"
                  onClick={() => setOpen(p)}
                  className="block h-full w-full cursor-pointer rounded-xl p-5 text-start outline-none focus-visible:ring-2 focus-visible:ring-brand-300"
                >
                  <div className="mb-3 flex items-start justify-between">
                    <span className="inline-flex rounded-xl bg-brand-50 p-2.5 text-brand-700 ring-1 ring-brand-100 ring-inset">
                      <Icon className="size-5" />
                    </span>
                    <ProgramCount n={p.request_types_count} />
                  </div>
                  <h3 className="text-[15px] font-semibold text-ink">{label("program", p.id, p.name_ar)}</h3>
                  <p className="mt-1 text-[12.5px] leading-relaxed text-ink-muted">{label("programDescription", p.id, p.description_ar)}</p>
                </button>
              </Card>
            );
          })}
        </div>
      )}
      <Sheet open={!!open} onOpenChange={(v) => !v && setOpen(null)}>
        <SheetContent side="end" className="max-w-lg overflow-y-auto" closeLabel={t.common.close}>
          {open && <RequestTypes program={open} />}
        </SheetContent>
      </Sheet>
    </div>
  );
}

function ProgramCount({ n }: { n: number }) {
  const { t, fmt } = useI18n();
  return <Badge tone="slate">{fmt.plural(t.programs.requestTypes, n)}</Badge>;
}

function RequestTypes({ program }: { program: Program }) {
  const { t, fmt, label } = useI18n();
  const types = useRequestTypes(program.id);
  const rows = types.data?.request_types ?? [];
  return (
    <>
      <SheetHeader>
        <div className="min-w-0">
          <SheetTitle>{label("program", program.id, program.name_ar)}</SheetTitle>
          <SheetDescription>{t.programs.typesTitle}</SheetDescription>
        </div>
      </SheetHeader>
      <div className="p-6">
        {types.error && !types.data ? (
          <LoadError onRetry={() => types.mutate()} />
        ) : types.isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 6 }, (_, i) => (
              <Skeleton key={i} className="h-14" />
            ))}
          </div>
        ) : rows.length === 0 ? (
          <Empty title={t.programs.noTypes} />
        ) : (
          <ul className="space-y-2">
            {rows.map((rt) => (
              <li key={rt.id} className="rounded-xl border border-line bg-white p-3.5">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-[13px] font-medium text-ink">{label("requestType", rt.id, rt.name_ar)}</p>
                  <Badge tone={rt.recurring ? "violet" : "slate"}>{rt.recurring ? t.programs.recurring : t.programs.oneOff}</Badge>
                </div>
                <p className="mt-1.5 text-[11.5px] text-ink-muted">
                  {t.programs.ceiling}: <span className="font-medium text-ink tabular">{fmt.money(rt.ceiling_sar)}</span>
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}
