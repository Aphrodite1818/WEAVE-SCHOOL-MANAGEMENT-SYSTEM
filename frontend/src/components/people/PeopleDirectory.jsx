import { UserRound } from "lucide-react";

import Card from "../ui/Card";
import { cn } from "../../utils/cn";

export function DirectorySummary({ items }) {
  return (
    <dl className="grid grid-cols-2 gap-2.5 sm:gap-3 md:grid-cols-4">
      {items.map(({ label, value, detail, icon: Icon, tone = "default" }) => (
        <Card
          key={label}
          className="rounded-xl border-border/80 p-3 shadow-sm"
        >
          <div className="flex flex-col items-start gap-2">
            <span
              className={cn(
                "grid h-9 w-9 shrink-0 place-items-center rounded-full",
                tone === "success"
                  ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-950/50 dark:text-emerald-300"
                  : tone === "warning"
                    ? "bg-amber-50 text-amber-600 dark:bg-amber-950/50 dark:text-amber-300"
                    : tone === "error"
                      ? "bg-rose-50 text-rose-600 dark:bg-rose-950/50 dark:text-rose-300"
                      : tone === "primary"
                        ? "bg-violet-50 text-violet-600 dark:bg-violet-950/50 dark:text-violet-300"
                        : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
              )}
            >
              <Icon className="h-4 w-4" />
            </span>
            <div>
              <dt className="text-xs font-medium leading-4 text-text-muted">
                {label}
              </dt>
              <dd className="mt-0.5 text-xl font-semibold leading-none text-text sm:text-2xl">
                {value}
              </dd>
              {detail ? (
                <p className="mt-1.5 line-clamp-1 text-[0.68rem] leading-4 text-text-muted sm:text-xs">
                  {detail}
                </p>
              ) : null}
            </div>
          </div>
        </Card>
      ))}
    </dl>
  );
}

export function DirectoryTable({ columns, children, label }) {
  return (
    <Card className="hidden overflow-hidden p-0 md:block">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse text-left" aria-label={label}>
          <thead>
            <tr className="border-b border-border/80 bg-surface-muted/35">
              {columns.map((column) => (
                <th
                  key={column.key || column.label}
                  scope="col"
                  className={cn(
                    "px-4 py-3 text-[0.68rem] font-bold uppercase tracking-[0.08em] text-text-muted",
                    column.className,
                  )}
                >
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border/70">{children}</tbody>
        </table>
      </div>
    </Card>
  );
}

export function PersonIdentity({ name, meta, icon: Icon = UserRound }) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary">
        <Icon className="h-4 w-4" />
      </span>
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-text">{name}</p>
        <p className="mt-0.5 truncate text-xs text-text-muted">{meta}</p>
      </div>
    </div>
  );
}

export function MobilePersonCard({ children, className }) {
  return (
    <Card className={cn("p-4 md:hidden", className)}>{children}</Card>
  );
}
