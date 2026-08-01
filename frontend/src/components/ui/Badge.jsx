import { cn } from "../../utils/cn";

const variants = {
  default: "bg-surface-muted text-text-soft ring-border",
  info: "bg-primary-soft text-primary ring-blue-200",
  primary: "bg-primary-soft text-primary ring-blue-200",
  accent: "bg-accent-soft text-accent ring-indigo-200",
  success: "bg-success-soft text-emerald-800 ring-emerald-200 dark:text-emerald-100 dark:ring-emerald-400/30",
  warning: "bg-warning-soft text-amber-950 ring-amber-200 dark:text-amber-100 dark:ring-amber-400/30",
  error: "bg-error-soft text-rose-800 ring-rose-200 dark:text-rose-100 dark:ring-rose-400/30",
};

function Badge({ variant = "default", children, className = "", ...props }) {
  return (
    <span
      className={cn(
        "inline-flex max-w-full min-w-0 shrink-0 items-center gap-1 truncate whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-bold leading-none ring-1 ring-inset",
        variants[variant] || variants.default,
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}

export default Badge;
