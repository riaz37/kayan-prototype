import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex w-fit shrink-0 items-center gap-1.5 rounded-md px-2 py-[3px] text-[11.5px] font-medium whitespace-nowrap ring-1 ring-inset [&>svg]:pointer-events-none [&>svg]:size-3",
  {
    variants: {
      tone: {
        brand: "bg-brand-50 text-brand-700 ring-brand-100",
        green: "bg-emerald-50 text-emerald-700 ring-emerald-100",
        amber: "bg-amber-50 text-amber-700 ring-amber-100",
        sky: "bg-sky-50 text-sky-700 ring-sky-100",
        rose: "bg-rose-50 text-rose-700 ring-rose-100",
        violet: "bg-violet-50 text-violet-700 ring-violet-100",
        slate: "bg-slate-50 text-slate-600 ring-slate-200/70",
      },
    },
    defaultVariants: {
      tone: "slate",
    },
  }
)

type Tone = NonNullable<VariantProps<typeof badgeVariants>["tone"]>

function Badge({
  className,
  tone = "slate",
  dot = false,
  asChild = false,
  children,
  ...props
}: React.ComponentProps<"span"> &
  VariantProps<typeof badgeVariants> & { asChild?: boolean; dot?: boolean }) {
  const Comp = asChild ? Slot.Root : "span"

  return (
    <Comp data-slot="badge" data-tone={tone} className={cn(badgeVariants({ tone }), className)} {...props}>
      {dot && <span aria-hidden className="size-1.5 rounded-full bg-current opacity-70" />}
      {children}
    </Comp>
  )
}

export { Badge, badgeVariants, type Tone }
