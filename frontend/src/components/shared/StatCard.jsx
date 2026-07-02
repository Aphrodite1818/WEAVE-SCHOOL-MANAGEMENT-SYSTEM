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
        "flex h-full flex-col bg-surface shadow-sm border-border/40",
        compact
          ? "min-h-0 p-3 sm:p-3.5 md:p-4"
          : "min-h-0 p-3 sm:min-h-[132px] sm:p-4 md:p-5 lg:min-h-[148px] lg:p-6",
        className
      )}
    >
      <div className="flex items-start justify-between gap-2 sm:gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase leading-snug tracking-wide text-text-muted sm:text-[11px] md:text-xs">
            {label}
          </p>
          {valueBadge ? (
            <div className="mt-2 max-w-full">
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
                "mt-1 line-clamp-2 font-semibold leading-tight tracking-tight text-text sm:mt-1.5",
                compact
                  ? "text-[1.7rem] leading-[0.95] sm:text-[2.15rem] md:text-[2.45rem]"
                  : "text-lg sm:text-2xl md:text-3xl lg:text-4xl"
              )}
              title={typeof value === 'string' ? value : undefined}
            >
              {value}
            </p>
          )}
        </div>
        {Icon && (
          <span
            className={cn(
              "flex shrink-0 items-center justify-center rounded-xl sm:rounded-[14px]",
              compact ? "h-8 w-8" : "h-8 w-8 sm:h-10 sm:w-10 md:h-11 md:w-11 lg:h-12 lg:w-12",
              toneClasses[tone] || toneClasses.primary
            )}
          >
            <Icon className={cn(compact ? "h-4 w-4" : "h-4 w-4 sm:h-5 sm:w-5 md:h-5 md:w-5 lg:h-6 lg:w-6")} />
          </span>
        )}
      </div>
      {(change || description) && (
        <div className="mt-auto flex flex-wrap items-center gap-1.5 pt-2 sm:gap-2 sm:pt-3 md:pt-4">
          {change && (
            <Badge variant={trend === "down" ? "error" : "success"}>
              <TrendIcon className="h-3 w-3 sm:h-3.5 sm:w-3.5" />
              {change}
            </Badge>
          )}
          {description && (
            <span className="min-w-0 text-[10px] font-medium leading-snug text-text-muted sm:text-xs">
              {description}
            </span>
          )}
        </div>
      )}
    </Card>
  );
}

export default StatCard;
