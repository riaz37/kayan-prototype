import * as React from "react"

import { cn } from "@/lib/utils"

function Card({ className, hover, ...props }: React.ComponentProps<"div"> & { hover?: boolean }) {
  return (
    <div
      data-slot="card"
      className={cn(
        "rounded-xl border border-line bg-card text-card-foreground shadow-card",
        hover && "transition-shadow hover:shadow-pop",
        className
      )}
      {...props}
    />
  )
}

function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-header"
      className={cn("flex items-start justify-between gap-3 px-5 pt-4 pb-3", className)}
      {...props}
    />
  )
}

function CardTitle({ className, ...props }: React.ComponentProps<"h3">) {
  return (
    <h3
      data-slot="card-title"
      className={cn("text-[15px] font-semibold tracking-tight text-ink", className)}
      {...props}
    />
  )
}

function CardDescription({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p data-slot="card-description" className={cn("mt-0.5 text-[12.5px] text-ink-muted", className)} {...props} />
  )
}

function CardAction({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="card-action" className={cn("shrink-0", className)} {...props} />
}

function CardContent({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="card-content" className={cn("px-5 pb-5", className)} {...props} />
}

function CardFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-footer"
      className={cn("flex items-center rounded-b-xl border-t border-line bg-line-soft/40 px-5 py-3", className)}
      {...props}
    />
  )
}

export { Card, CardHeader, CardFooter, CardTitle, CardAction, CardDescription, CardContent }
