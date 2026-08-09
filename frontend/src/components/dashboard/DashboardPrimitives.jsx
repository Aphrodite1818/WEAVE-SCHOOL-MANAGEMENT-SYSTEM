import { Link } from "react-router-dom";
import { ArrowRight, ChevronRight } from "lucide-react";
import { useState } from "react";

import Card from "../ui/Card";
import Button from "../ui/Button";
import WeaveIcon from "../brand/WeaveIcon";
import { cn } from "../../utils/cn";
import { authSession } from "../../services/api";
import { useTenantWorkspaceBranding } from "../layout/useTenantWorkspaceName";

const toneStyles = {
  primary: {
    icon: "bg-primary-soft text-primary",
    badge: "bg-primary-subtle text-primary",
  },
  success: {
    icon: "bg-success-soft text-success",
    badge: "bg-success-soft text-success",
  },
  warning: {
    icon: "bg-warning-soft text-amber-950",
    badge: "bg-warning-soft text-amber-950",
  },
  danger: {
    icon: "bg-error-soft text-error",
    badge: "bg-error-soft text-error",
  },
  accent: {
    icon: "bg-accent-soft text-accent",
    badge: "bg-accent-soft text-accent",
  },
  neutral: {
    icon: "bg-surface-muted text-text-muted",
    badge: "bg-surface-muted text-text-soft",
  },
};

export function DashboardSectionHeader({ title, description, action, className = "" }) {
  return (
    <div className={cn("flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between", className)}>
      <div className="min-w-0">
        <h2 className="section-title">{title}</h2>
        {description ? <p className="mt-1 max-w-2xl text-sm leading-6 text-text-muted">{description}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

const isProfileIncomplete = (completion) => {
  if (completion === undefined || completion === null || completion === "") return false;
  if (typeof completion === "boolean") return !completion;

  const normalized = String(completion).trim().toLowerCase();
  return !["complete", "completed", "true"].includes(normalized);
};

export function DashboardWelcomePanel({
  eyebrow,
  title,
  description,
  chips = [],
  children,
  className = "",
  profileCompletion,
  variant = "default",
}) {
  const user = authSession.getUser() || {};
  const role = String(user?.role || authSession.getRole() || "").toLowerCase();
  const { schoolName, logoUrl } = useTenantWorkspaceBranding({ user, role });
  const [failedLogoUrl, setFailedLogoUrl] = useState("");
  const isBlueHero = variant === "student" || variant === "blue";
  const hasSchoolLogo = Boolean(logoUrl) && failedLogoUrl !== logoUrl;
  const brandLabel = hasSchoolLogo ? schoolName || "School workspace" : "Weave";
  const visibleChips = [
    isProfileIncomplete(profileCompletion)
      ? { label: "Profile incomplete", tone: "warning" }
      : null,
    ...chips,
  ].filter(Boolean);

  return (
    <Card
      className={cn(
        "overflow-hidden p-4 sm:p-6",
        isBlueHero && "dashboard-welcome-blue border-0 px-4 py-5 sm:px-7 sm:py-7 lg:px-8",
        className,
      )}
    >
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div
            className={cn(
              "mb-5 flex min-w-0 items-center gap-3 sm:inline-flex sm:max-w-full",
              isBlueHero ? "text-white" : "text-text",
            )}
          >
            {hasSchoolLogo ? (
              <img
                src={logoUrl}
                alt={`${brandLabel} logo`}
                className="h-14 w-14 shrink-0 object-contain sm:h-16 sm:w-16"
                onError={() => setFailedLogoUrl(logoUrl)}
              />
            ) : (
              <WeaveIcon className="h-12 w-12 shrink-0 sm:h-14 sm:w-14" />
            )}
            <div className="min-w-0">
              {!hasSchoolLogo ? (
                <p className={cn("text-[10px] font-bold uppercase tracking-[0.16em]", isBlueHero ? "text-white/75" : "text-text-faint")}>
                  Powered by
                </p>
              ) : null}
              <p className="mt-0.5 max-w-[min(30rem,100%)] truncate text-lg font-bold leading-tight sm:text-2xl">
                {brandLabel}
              </p>
            </div>
          </div>
          {eyebrow ? <p className={cn("text-[11px] font-bold uppercase tracking-[0.16em] text-text-muted sm:text-xs", isBlueHero && "text-white/80")}>{eyebrow}</p> : null}
          <h2 className={cn("mt-2 text-xl font-semibold leading-tight text-text sm:text-3xl", isBlueHero && "text-white")}>{title}</h2>
          {description ? <p className={cn("mt-2 max-w-3xl text-sm leading-6 text-text-muted", isBlueHero && "text-white/85")}>{description}</p> : null}
          {visibleChips.length > 0 ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {visibleChips.map((chip) => {
                const chipTone = chip.tone || "neutral";
                const chipToneStyle = toneStyles[chipTone] || toneStyles.neutral;
                return (
                  <span
                    key={`${chip.label}-${chip.value || ""}`}
                    className={cn(
                      "inline-flex max-w-full items-center gap-1 rounded-full px-3 py-1 text-[11px] font-bold sm:text-xs",
                      isBlueHero ? "border border-white/25 bg-white/15 text-white" : chipToneStyle.badge,
                    )}
                  >
                    <span className="truncate">{chip.label}</span>
                    {chip.value ? <span className="truncate opacity-80">{chip.value}</span> : null}
                  </span>
                );
              })}
            </div>
          ) : null}
        </div>
        {children ? <div className="w-full shrink-0 lg:w-auto lg:max-w-md">{children}</div> : null}
      </div>
    </Card>
  );
}

export function DashboardMetricCard({
  label,
  value,
  description,
  icon: Icon,
  tone = "primary",
  to,
  badge,
  compact = false,
  className = "",
}) {
  const Wrapper = to ? Link : "div";
  const toneStyle = toneStyles[tone] || toneStyles.primary;

  return (
    <Card
      as={Wrapper}
      to={to}
      className={cn(
        "group flex flex-col justify-between transition hover:border-primary/30 hover:shadow-premium",
        compact
          ? "min-h-[5.75rem] p-3"
          : "min-h-[7.6rem] p-3 sm:min-h-[8.25rem] sm:p-5",
        to ? "cursor-pointer" : "",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-2 sm:gap-3">
        <div
          className={cn(
            "flex shrink-0 items-center justify-center rounded-2xl",
            compact ? "h-8 w-8" : "h-10 w-10 sm:h-11 sm:w-11",
            toneStyle.icon,
          )}
        >
          {Icon ? (
            <Icon className={compact ? "h-4 w-4" : "h-4 w-4 sm:h-5 sm:w-5"} />
          ) : null}
        </div>
        {badge ? <span className={cn("rounded-full px-2 py-1 text-[10px] font-bold sm:px-2.5 sm:text-[11px]", toneStyle.badge)}>{badge}</span> : null}
      </div>
      <div className={compact ? "mt-2" : "mt-3 sm:mt-4"}>
        <p className={cn("line-clamp-2 font-semibold text-text-muted", compact ? "text-[11px] leading-4" : "text-xs leading-4 sm:text-sm")}>{label}</p>
        <p className={cn("mt-1 break-words font-semibold tracking-tight text-text", compact ? "text-lg" : "text-xl sm:text-2xl")}>{value}</p>
        {description ? <p className={cn("mt-1 line-clamp-2 text-text-muted", compact ? "text-[11px] leading-4" : "text-[11px] leading-4 sm:text-xs sm:leading-5")}>{description}</p> : null}
      </div>
    </Card>
  );
}

export function DashboardFocusCard({ title, description, icon: Icon, tone = "primary", primaryAction, secondaryAction, children, className = "" }) {
  const toneStyle = toneStyles[tone] || toneStyles.primary;

  return (
    <Card className={cn("flex h-full flex-col p-4 sm:p-6", className)}>
      <div className="flex items-start gap-3 sm:gap-4">
        {Icon ? (
          <div className={cn("flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl sm:h-12 sm:w-12", toneStyle.icon)}>
            <Icon className="h-5 w-5" />
          </div>
        ) : null}
        <div className="min-w-0">
          <h3 className="section-title">{title}</h3>
          {description ? <p className="mt-1 text-sm leading-6 text-text-muted">{description}</p> : null}
        </div>
      </div>
      {children ? <div className="mt-5 flex-1">{children}</div> : null}
      {(primaryAction || secondaryAction) ? (
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          {primaryAction ? <DashboardActionButton {...primaryAction} /> : null}
          {secondaryAction ? <DashboardActionButton variant="outline" {...secondaryAction} /> : null}
        </div>
      ) : null}
    </Card>
  );
}

export function DashboardActionButton({ to, label, icon: Icon, variant = "primary", disabled = false }) {
  const content = (
    <Button variant={variant} className="w-full" disabled={disabled}>
      {Icon ? <Icon className="h-4 w-4" /> : null}
      {label}
    </Button>
  );

  if (!to) return content;

  return (
    <Link to={to} className={disabled ? "pointer-events-none opacity-50" : "block"} aria-disabled={disabled}>
      {content}
    </Link>
  );
}

export function DashboardListCard({ title, description, items = [], emptyTitle = "Nothing needs attention", emptyDescription = "You are all caught up.", action, className = "" }) {
  return (
    <Card className={cn("flex h-full flex-col p-4 sm:p-6", className)}>
      <DashboardSectionHeader title={title} description={description} action={action} />
      <div className="mobile-scroll-list mt-4 grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(10rem, 100%), 1fr))" }}>
        {items.length > 0 ? (
          items.map((item) => <DashboardListItem key={item.key || item.title} {...item} />)
        ) : (
          <div className="rounded-2xl border border-dashed border-border bg-surface-muted/20 px-4 py-5">
            <p className="text-sm font-semibold text-text">{emptyTitle}</p>
            <p className="mt-1 text-sm leading-6 text-text-muted">{emptyDescription}</p>
          </div>
        )}
      </div>
    </Card>
  );
}

export function DashboardListItem({ title, description, meta, icon: Icon, tone = "neutral", to, value }) {
  const Wrapper = to ? Link : "div";
  const toneStyle = toneStyles[tone] || toneStyles.neutral;

  return (
    <Wrapper
      to={to}
      className={cn(
        "group flex min-h-[8rem] flex-col justify-between rounded-2xl border border-border/70 bg-surface px-3 py-3 transition sm:px-4",
        to ? "hover:border-primary/30 hover:bg-primary-subtle/25 hover:shadow-sm" : "",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl", toneStyle.icon)}>
          {Icon ? <Icon className="h-4 w-4" /> : null}
        </div>
        {value !== undefined && value !== null ? <span className="shrink-0 text-sm font-semibold text-text">{value}</span> : null}
        {to ? <ChevronRight className="h-4 w-4 shrink-0 text-text-faint transition group-hover:translate-x-0.5" /> : null}
      </div>
      <div className="mt-3 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="min-w-0 break-words text-sm font-semibold leading-5 text-text">{title}</p>
          {meta ? <span className="rounded-full bg-surface-muted px-2 py-0.5 text-[10px] font-semibold text-text-muted">{meta}</span> : null}
        </div>
        {description ? <p className="mt-1 line-clamp-3 text-xs leading-5 text-text-muted">{description}</p> : null}
      </div>
    </Wrapper>
  );
}

export function DashboardQuickActions({
  actions = [],
  title = "Quick actions",
  description,
  showDescription = false,
  showActionDescriptions = false,
}) {
  return (
    <Card className="p-4 sm:p-6">
      <DashboardSectionHeader
        title={title}
        description={showDescription ? description : undefined}
      />
      <div className="mt-4 grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(9.25rem, 100%), 1fr))" }}>
        {actions.map((action) => {
          const ActionIcon = action.icon;
          const toneStyle = toneStyles[action.tone || "primary"] || toneStyles.primary;
          const Wrapper = action.to ? Link : "button";
          return (
            <Wrapper
              key={action.label}
              to={action.to}
              type={action.to ? undefined : "button"}
              onClick={action.onClick}
              className="group flex min-h-[7rem] flex-col rounded-2xl border border-border/70 bg-surface px-3 py-4 text-left shadow-sm transition hover:border-primary/30 hover:bg-primary-subtle/25 hover:shadow-premium sm:min-h-[7.5rem] sm:px-4"
            >
              <div className={cn("flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl", toneStyle.icon)}>
                {ActionIcon ? <ActionIcon className="h-5 w-5" /> : <ArrowRight className="h-5 w-5" />}
              </div>
              <p className="mt-3 break-words text-sm font-semibold leading-5 text-text">{action.label}</p>
              {showActionDescriptions && action.description ? (
                <p className="mt-1 break-words text-xs leading-5 text-text-muted">
                  {action.description}
                </p>
              ) : null}
            </Wrapper>
          );
        })}
      </div>
    </Card>
  );
}
