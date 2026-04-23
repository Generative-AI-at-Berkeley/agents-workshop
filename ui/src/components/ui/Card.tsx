import { tv, type VariantProps } from "tailwind-variants";
import { cn } from "../../lib/cn";

const card = tv({
  base: [
    "rounded-xl bg-surface-raised",
    "border border-outline-100 dark:border-outline-100",
    "transition-colors",
  ].join(" "),
  variants: {
    padding: {
      none: "",
      sm: "p-3",
      md: "p-5",
      lg: "p-6",
    },
    status: {
      idle: "",
      running: "border-l-2 border-l-brand-500",
      done: "border-l-2 border-l-system-green",
      failed: "border-l-2 border-l-system-red",
    },
    hoverable: {
      true: "hover:border-outline-200 hover:shadow-sm cursor-pointer",
      false: "",
    },
  },
  defaultVariants: {
    padding: "md",
    status: "idle",
    hoverable: false,
  },
});

export interface CardProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof card> {}

export function Card({
  padding,
  status,
  hoverable,
  className,
  ...rest
}: CardProps) {
  return (
    <div
      {...rest}
      className={card({ padding, status, hoverable, className: cn(className) })}
    />
  );
}
