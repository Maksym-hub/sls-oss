// @ts-nocheck — auto-generated shadcn/ui component
import * as React from "react"
import { cva } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary text-primary-foreground shadow hover:bg-primary/80",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive:
          "border-transparent bg-destructive text-destructive-foreground shadow hover:bg-destructive/80",
        outline: "text-foreground",
        success:
          "border-transparent bg-green-500 text-white shadow hover:bg-green-500/80",
        warning:
          "border-transparent bg-yellow-500 text-white shadow hover:bg-yellow-500/80",
        error:
          "border-transparent bg-red-500 text-white shadow hover:bg-red-500/80",
        aborted:
          "border-transparent bg-orange-500 text-white shadow hover:bg-orange-500/80",
        stopped:
          "border-transparent bg-amber-600 text-white shadow hover:bg-amber-600/80",
        skipped:
          "border-transparent bg-slate-500 text-white shadow hover:bg-slate-500/80",
        muted:
          "border-transparent bg-slate-400 text-white shadow hover:bg-slate-400/80",
        running:
          "border-transparent bg-blue-500 text-white shadow hover:bg-blue-500/80",
        info:
          "border-transparent bg-blue-400 text-white shadow hover:bg-blue-400/80",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Badge({ className, variant, ...props }) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
