import { cn } from "../../utils/cn";

const variants = {
  default:
    "bg-slate-100 text-slate-700 ring-slate-200 dark:bg-slate-800/90 dark:text-slate-100 dark:ring-slate-600/60",
  info:
    "bg-blue-100 text-blue-900 ring-blue-200 dark:bg-blue-950/65 dark:text-blue-100 dark:ring-blue-500/40",
  primary:
    "bg-blue-100 text-blue-900 ring-blue-200 dark:bg-blue-950/65 dark:text-blue-100 dark:ring-blue-500/40",
  accent:
    "bg-indigo-100 text-indigo-900 ring-indigo-200 dark:bg-indigo-950/65 dark:text-indigo-100 dark:ring-indigo-500/40",
  success:
    "bg-emerald-100 text-emerald-900 ring-emerald-200 dark:bg-emerald-950/65 dark:text-emerald-100 dark:ring-emerald-500/40",
  warning:
    "bg-amber-100 text-amber-950 ring-amber-300 dark:bg-amber-950/65 dark:text-amber-100 dark:ring-amber-500/45",
  error:
    "bg-rose-100 text-rose-900 ring-rose-200 dark:bg-rose-950/65 dark:text-rose-100 dark:ring-rose-500/40",
};

function Badge({ variant = "default", children, className = "", ...props }) {
  return (
    <span
      className={cn(
        "inline-flex max-w-full min-w-0 shrink-0 items-center gap-1 truncate whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-bold leading-none ring-1 ring-inset",
        variants[variant] || variants.default,
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}

export default Badge;
