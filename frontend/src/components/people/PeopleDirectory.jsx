import { UserRound } from "lucide-react";

import Card from "../ui/Card";
import { cn } from "../../utils/cn";

export function DirectorySummary({ items }) {
  return (
    <Card className="overflow-hidden p-0">
      <dl className="grid gap-px bg-border/70 sm:grid-cols-2 xl:grid-cols-4">
        {items.map(({ label, value, detail, icon: Icon, tone = "default" }) => (
          <div
            key={label}
            className="flex items-center gap-3 bg-surface px-4 py-3.5 sm:px-5"
          >
            <span
              className={cn(
                "grid h-10 w-10 shrink-0 place-items-center rounded-xl",
                tone === "success"
                  ? "bg-success-soft text-success"
                  : tone === "warning"
                    ? "bg-warning-soft text-warning"
                    : tone === "primary"
                      ? "bg-primary-soft text-primary"
                      : "bg-surface-muted text-text-muted",
              )}
            >
              <Icon className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <dt className="truncate text-[0.68rem] font-bold uppercase tracking-[0.08em] text-text-muted">
                {label}
              </dt>
              <dd className="mt-0.5 flex items-baseline gap-2">
                <span className="text-xl font-semibold leading-none text-text">
                  {value}
                </span>
                {detail ? (
                  <span className="truncate text-xs text-text-muted">{detail}</span>
                ) : null}
              </dd>
            </div>
          </div>
        ))}
      </dl>
    </Card>
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
