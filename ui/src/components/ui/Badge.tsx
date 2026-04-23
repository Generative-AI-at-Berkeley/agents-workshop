import { tv, type VariantProps } from "tailwind-variants";

const badge = tv({
  base: [
    "inline-flex items-center gap-1 rounded-full",
    "px-2 py-0.5 text-xs font-500 tracking-slight",
    "whitespace-nowrap",
  ].join(" "),
  variants: {
    tone: {
      neutral: "bg-dark-100 text-dark-600 dark:bg-dark-900 dark:text-dark-200",
      success: "bg-system-light-green text-system-green",
      warning: "bg-system-light-yellow text-system-orange",
      danger: "bg-system-light-red text-system-red",
      info: "bg-blue-50 text-system-blue dark:bg-blue-950 dark:text-blue-300",
      accent:
        "bg-brand-200 text-brand-900 ring-1 ring-brand-500/10 dark:bg-brand-900/40 dark:text-brand-200 dark:ring-brand-500/30",
    },
    size: {
      sm: "h-5 text-xs",
      md: "h-6 text-sm",
    },
  },
  defaultVariants: {
    tone: "neutral",
    size: "sm",
  },
});

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badge> {}

export function Badge({ tone, size, className, ...rest }: BadgeProps) {
  return (
    <span
      {...rest}
      className={badge({ tone, size, className: className as string })}
    />
  );
}
