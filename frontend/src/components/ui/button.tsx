import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex shrink-0 cursor-pointer items-center justify-center rounded-lg font-medium whitespace-nowrap transition-colors outline-none select-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:pointer-events-none disabled:opacity-50 aria-invalid:ring-2 aria-invalid:ring-destructive/20 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: "bg-brand-600 text-white shadow-sm hover:bg-brand-700",
        soft: "bg-brand-50 text-brand-700 hover:bg-brand-100",
        outline: "border border-line bg-white text-ink hover:bg-line-soft",
        ghost: "text-ink-muted hover:bg-line-soft hover:text-ink",
        danger: "bg-rose-50 text-rose-700 hover:bg-rose-100",
        link: "text-brand-700 underline-offset-4 hover:underline",
      },
      size: {
        sm: "h-8 gap-1.5 px-2.5 text-[12.5px]",
        default: "h-9 gap-2 px-3.5 text-[13px]",
        lg: "h-10 gap-2 px-4 text-[13.5px]",
        icon: "size-9",
        "icon-sm": "size-8",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  type,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      type={asChild ? type : (type ?? "button")}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
