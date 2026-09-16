"use client"

import * as React from "react"
import { Progress as ProgressPrimitive } from "radix-ui"

import { cn } from "@/lib/utils"

const toneClass = {
  brand: "bg-brand-500",
  green: "bg-emerald-500",
  amber: "bg-amber-500",
  rose: "bg-rose-500",
} as const

/** Fills from the inline-start edge, so it reads correctly in both RTL and LTR. */
function Progress({
  className,
  value,
  tone = "brand",
  ...props
}: React.ComponentProps<typeof ProgressPrimitive.Root> & { tone?: keyof typeof toneClass }) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0))
  return (
    <ProgressPrimitive.Root
      data-slot="progress"
      value={pct}
      className={cn("relative h-1.5 w-full overflow-hidden rounded-full bg-line-soft", className)}
      {...props}
    >
      <ProgressPrimitive.Indicator
        data-slot="progress-indicator"
        className={cn("h-full rounded-full transition-[width] duration-700", toneClass[tone])}
        style={{ width: `${pct}%` }}
      />
    </ProgressPrimitive.Root>
  )
}

export { Progress }
