"use client"

import { CircleCheckIcon, InfoIcon, Loader2Icon, OctagonXIcon, TriangleAlertIcon } from "lucide-react"
import { Toaster as Sonner, type ToasterProps } from "sonner"

const Toaster = (props: ToasterProps) => (
  <Sonner
    theme="light"
    className="toaster group"
    icons={{
      success: <CircleCheckIcon className="size-4 text-emerald-600" />,
      info: <InfoIcon className="size-4 text-sky-600" />,
      warning: <TriangleAlertIcon className="size-4 text-amber-600" />,
      error: <OctagonXIcon className="size-4 text-rose-600" />,
      loading: <Loader2Icon className="size-4 animate-spin" />,
    }}
    style={
      {
        "--normal-bg": "var(--popover)",
        "--normal-text": "var(--popover-foreground)",
        "--normal-border": "var(--border)",
        "--border-radius": "var(--radius-xl)",
        fontFamily: "var(--font-sans)",
      } as React.CSSProperties
    }
    toastOptions={{ classNames: { toast: "text-[13px] shadow-pop" } }}
    {...props}
  />
)

export { Toaster }
