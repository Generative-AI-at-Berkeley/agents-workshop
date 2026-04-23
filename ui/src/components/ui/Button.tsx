import { tv, type VariantProps } from "tailwind-variants";
import {
  Button as AriaButton,
  type ButtonProps as AriaButtonProps,
} from "react-aria-components";

const button = tv({
  base: [
    "inline-flex items-center justify-center gap-2",
    "font-500 tracking-slight whitespace-nowrap",
    "rounded-md transition-colors outline-none",
    "focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-1",
    "disabled:opacity-50 disabled:cursor-not-allowed",
  ].join(" "),
  variants: {
    intent: {
      primary:
        "bg-brand-500 text-brand-foreground hover:bg-brand-600 active:bg-brand-700",
      secondary:
        "bg-dark-900 text-dark-50 hover:bg-dark-600 dark:bg-dark-100 dark:text-dark-1000 dark:hover:bg-dark-200",
      ghost:
        "text-ink hover:bg-dark-100 dark:hover:bg-dark-900",
      outline:
        "border border-outline-200 text-ink hover:bg-dark-50 dark:hover:bg-dark-900",
    },
    size: {
      sm: "h-8 px-3 text-sm",
      md: "h-10 px-4 text-md",
      lg: "h-12 px-6 text-lg",
    },
  },
  defaultVariants: {
    intent: "primary",
    size: "md",
  },
});

export type ButtonProps = AriaButtonProps & VariantProps<typeof button>;

export function Button({ intent, size, className, ...rest }: ButtonProps) {
  return (
    <AriaButton
      {...rest}
      className={button({ intent, size, className: className as string })}
    />
  );
}
