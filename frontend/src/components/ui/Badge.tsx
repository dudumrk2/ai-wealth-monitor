import * as React from "react"
import clsx from "clsx"

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "destructive" | "outline" | "success"
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <div
      className={clsx(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-bold transition-colors shadow-sm",
        {
          "bg-blue-600 border-transparent text-white": variant === "default",
          "bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-slate-100": variant === "secondary",
          "bg-red-500 border-transparent text-white": variant === "destructive",
          "bg-emerald-500 border-transparent text-white": variant === "success",
          "border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-slate-100": variant === "outline",
        },
        className
      )}
      {...props}
    />
  )
}

export { Badge }
