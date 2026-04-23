import { tv } from "tailwind-variants";
import {
  Input as AriaInput,
  type InputProps as AriaInputProps,
  TextField,
  type TextFieldProps,
  Label,
} from "react-aria-components";

const input = tv({
  base: [
    "w-full rounded-md bg-surface-raised",
    "border border-outline-200",
    "px-3 py-2 text-md font-400 text-ink placeholder:text-ink-subtle",
    "outline-none transition-colors",
    "focus:border-brand-500 focus:ring-2 focus:ring-brand-500/40",
    "disabled:opacity-50",
  ].join(" "),
  variants: {
    size: {
      md: "h-10",
      lg: "h-14 text-lg px-4",
    },
  },
  defaultVariants: {
    size: "md",
  },
});

export interface InputProps extends Omit<AriaInputProps, "size"> {
  size?: "md" | "lg";
}

export function Input({ size, className, ...rest }: InputProps) {
  return (
    <AriaInput {...rest} className={input({ size, className: className as string })} />
  );
}

export function Field({
  label,
  children,
  ...rest
}: TextFieldProps & { label?: string; children: React.ReactNode }) {
  return (
    <TextField {...rest} className="flex flex-col gap-1.5">
      {label ? (
        <Label className="text-sm font-500 text-ink-muted">{label}</Label>
      ) : null}
      {children}
    </TextField>
  );
}
