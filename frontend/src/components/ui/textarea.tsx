import * as React from "react"

import { cn } from "@/lib/utils"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex min-h-20 w-full rounded-lg border border-line bg-white px-3 py-2 text-[13px] text-ink transition outline-none placeholder:text-ink-soft focus-visible:border-brand-300 focus-visible:ring-2 focus-visible:ring-brand-100 disabled:cursor-not-allowed disabled:opacity-60 aria-invalid:border-rose-300 aria-invalid:ring-2 aria-invalid:ring-rose-100",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
