"use client";

import { useId } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { useI18n } from "@/components/providers/i18n-provider";
import { cn } from "@/lib/utils";

/** "Show expired (n)" checkbox used by the ticket board, ticket list and dashboard. */
export function ShowExpiredToggle({
  checked,
  onChange,
  count,
  className,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  count: number;
  className?: string;
}) {
  const { t, format, fmt } = useI18n();
  const id = useId();
  return (
    <label
      htmlFor={id}
      className={cn(
        "inline-flex h-9 cursor-pointer items-center gap-2 rounded-lg border border-line bg-white px-3 text-[13px] text-ink select-none hover:bg-line-soft",
        className,
      )}
    >
      <Checkbox id={id} checked={checked} onCheckedChange={(v) => onChange(v === true)} />
      {format(t.common.showExpired, { n: fmt.number(count) })}
    </label>
  );
}
