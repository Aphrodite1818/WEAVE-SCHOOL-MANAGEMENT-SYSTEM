import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import Card from "../ui/Card";
import Badge from "../ui/Badge";
import { cn } from "../../utils/cn";

const toneClasses = {
  primary: "bg-primary-soft text-primary",
  success: "bg-success-soft text-emerald-700",
  warning: "bg-warning-soft text-amber-700",
  error: "bg-error-soft text-rose-700",
  accent: "bg-accent-soft text-accent",
};

function StatCard({
  label,
  value,
  change,
  trend = "up",
  icon: Icon,
  tone = "primary",
  description,
  valueBadge = null,
  className = "",
  compact = false,
}) {
  const TrendIcon = trend === "down" ? ArrowDownRight : ArrowUpRight;

  return (
    <Card
      className={cn(
        "flex h-full min-h-0 flex-col border-border/50 bg-surface shadow-sm",
        compact
          ? "p-3 sm:p-3.5 md:p-4"
          : "p-4 sm:min-h-[132px] sm:p-5 lg:min-h-[144px]",
        className
      )}
    >
      <div className="flex items-start justify-between gap-2 sm:gap-3">
        <div className="min-w-0 flex-1">
          <p className="line-clamp-1 text-[10px] font-semibold uppercase leading-snug tracking-wide text-text-muted sm:text-[11px] md:text-xs">
            {label}
          </p>
          {valueBadge ? (
            <div className="mt-1.5 max-w-full sm:mt-2">
              <Badge
                variant={valueBadge.variant || "success"}
                className={cn(
                  compact
                    ? "max-w-full whitespace-nowrap px-2 py-1 text-[9px] font-semibold leading-none sm:px-2.5 sm:text-[10px]"
                    : "max-w-full whitespace-nowrap px-2.5 py-1 text-[10px] font-semibold leading-none sm:px-3 sm:py-1.5 sm:text-[11px]",
                  valueBadge.className
                )}
              >
                {valueBadge.label}
              </Badge>
            </div>
          ) : (
            <p
              className={cn(
                "mt-1 line-clamp-2 font-semibold leading-[1.04] tracking-tight text-text sm:mt-1.5",
                compact
                  ? "text-[1.35rem] sm:text-[2rem] md:text-[2.25rem]"
                  : "text-xl sm:text-2xl md:text-3xl"
              )}
              title={typeof value === "string" ? value : undefined}
            >
              {value}
            </p>
          )}
        </div>
        {Icon && (
          <span
            className={cn(
              "flex shrink-0 items-center justify-center rounded-xl",
              compact ? "h-8 w-8" : "h-10 w-10 md:h-11 md:w-11",
              toneClasses[tone] || toneClasses.primary
            )}
          >
            <Icon className={cn(compact ? "h-4 w-4" : "h-5 w-5")} />
          </span>
        )}
      </div>
      {(change || description) && (
        <div className="mt-auto flex flex-wrap items-center gap-1 pt-2 sm:gap-2 sm:pt-3">
          {change && (
            <Badge variant={trend === "down" ? "error" : "success"}>
              <TrendIcon className="h-3 w-3 sm:h-3.5 sm:w-3.5" />
              {change}
            </Badge>
          )}
          {description && (
            <span className="min-w-0 line-clamp-1 text-[10px] font-medium leading-snug text-text-muted sm:text-xs">
              {description}
            </span>
          )}
        </div>
      )}
    </Card>
  );
}

export default StatCard;
