import * as React from "react"

import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "h-9 w-full min-w-0 rounded-lg border border-line bg-white px-3 text-[13px] text-ink transition outline-none placeholder:text-ink-soft focus-visible:border-brand-300 focus-visible:ring-2 focus-visible:ring-brand-100 disabled:cursor-not-allowed disabled:opacity-60 aria-invalid:border-rose-300 aria-invalid:ring-2 aria-invalid:ring-rose-100",
        className
      )}
      {...props}
    />
  )
}

export { Input }
