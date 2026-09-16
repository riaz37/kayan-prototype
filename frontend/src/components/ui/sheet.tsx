"use client"

import * as React from "react"
import { XIcon } from "lucide-react"
import { Dialog as SheetPrimitive } from "radix-ui"

import { cn } from "@/lib/utils"

function Sheet({ ...props }: React.ComponentProps<typeof SheetPrimitive.Root>) {
  return <SheetPrimitive.Root data-slot="sheet" {...props} />
}

function SheetTrigger({ ...props }: React.ComponentProps<typeof SheetPrimitive.Trigger>) {
  return <SheetPrimitive.Trigger data-slot="sheet-trigger" {...props} />
}

function SheetClose({ ...props }: React.ComponentProps<typeof SheetPrimitive.Close>) {
  return <SheetPrimitive.Close data-slot="sheet-close" {...props} />
}

function SheetPortal({ ...props }: React.ComponentProps<typeof SheetPrimitive.Portal>) {
  return <SheetPrimitive.Portal data-slot="sheet-portal" {...props} />
}

function SheetOverlay({ className, ...props }: React.ComponentProps<typeof SheetPrimitive.Overlay>) {
  return (
    <SheetPrimitive.Overlay
      data-slot="sheet-overlay"
      className={cn(
        "fixed inset-0 z-50 bg-slate-900/20 backdrop-blur-[2px] data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0",
        className
      )}
      {...props}
    />
  )
}

/**
 * `side` is logical: "end" opens from the inline-end edge (left in RTL, right
 * in LTR) — matching where the original console slid its detail panels in.
 */
function SheetContent({
  className,
  children,
  side = "end",
  showCloseButton = true,
  closeLabel = "Close",
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Content> & {
  side?: "start" | "end"
  showCloseButton?: boolean
  closeLabel?: string
}) {
  return (
    <SheetPortal>
      <SheetOverlay />
      <SheetPrimitive.Content
        data-slot="sheet-content"
        data-side={side}
        className={cn(
          "fixed inset-y-0 z-50 flex h-full w-full flex-col bg-canvas shadow-pop outline-none duration-300 ease-[cubic-bezier(.16,1,.3,1)] data-open:animate-in data-closed:animate-out data-closed:duration-200",
          side === "end" &&
            "end-0 border-s border-line ltr:data-open:slide-in-from-right ltr:data-closed:slide-out-to-right rtl:data-open:slide-in-from-left rtl:data-closed:slide-out-to-left",
          side === "start" &&
            "start-0 border-e border-line ltr:data-open:slide-in-from-left ltr:data-closed:slide-out-to-left rtl:data-open:slide-in-from-right rtl:data-closed:slide-out-to-right",
          className
        )}
        {...props}
      >
        {children}
        {showCloseButton && (
          <SheetPrimitive.Close
            data-slot="sheet-close"
            className="absolute end-4 top-4 z-20 inline-flex size-8 cursor-pointer items-center justify-center rounded-lg text-ink-muted transition-colors outline-none hover:bg-line-soft hover:text-ink focus-visible:ring-2 focus-visible:ring-brand-300"
          >
            <XIcon className="size-4" />
            <span className="sr-only">{closeLabel}</span>
          </SheetPrimitive.Close>
        )}
      </SheetPrimitive.Content>
    </SheetPortal>
  )
}

function SheetHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sheet-header"
      className={cn(
        "sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-line bg-white/85 px-6 py-4 pe-14 backdrop-blur",
        className
      )}
      {...props}
    />
  )
}

function SheetFooter({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="sheet-footer" className={cn("mt-auto flex flex-col gap-2 p-4", className)} {...props} />
}

function SheetTitle({ className, ...props }: React.ComponentProps<typeof SheetPrimitive.Title>) {
  return (
    <SheetPrimitive.Title
      data-slot="sheet-title"
      className={cn("truncate text-[16px] font-semibold text-ink", className)}
      {...props}
    />
  )
}

function SheetDescription({ className, ...props }: React.ComponentProps<typeof SheetPrimitive.Description>) {
  return (
    <SheetPrimitive.Description
      data-slot="sheet-description"
      className={cn("mt-0.5 truncate text-[12.5px] text-ink-muted", className)}
      {...props}
    />
  )
}

export { Sheet, SheetTrigger, SheetClose, SheetContent, SheetHeader, SheetFooter, SheetTitle, SheetDescription }
