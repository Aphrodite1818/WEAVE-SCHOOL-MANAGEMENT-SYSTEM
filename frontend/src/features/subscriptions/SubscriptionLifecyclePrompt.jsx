import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CalendarClock, CreditCard, ShieldAlert } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import { formatDateTime, formatPlanName } from "./subscriptionConfig";

const PROMPTABLE_STATUSES = new Set([
  "past_due",
  "grace_period",
  "expired",
  "cancelled",
]);

const STATUS_CONTENT = {
  past_due: {
    title: "Payment needs attention",
    eyebrow: "Payment issue",
    message:
      "We could not confirm your latest subscription payment. Update billing to prevent an interruption to school management actions.",
    icon: AlertTriangle,
    toneClass: "bg-error-soft text-error",
    deadlineLabel: "Billing period ended",
    primaryLabel: "Update payment",
  },
  grace_period: {
    title: "Your subscription is in grace period",
    eyebrow: "Action required",
    message:
      "Your school is temporarily still accessible, but write actions may become restricted when the grace period ends.",
    icon: CalendarClock,
    toneClass: "bg-warning-soft text-warning",
    deadlineLabel: "Grace period ends",
    primaryLabel: "Update payment",
  },
  expired: {
    title: "Your subscription has expired",
    eyebrow: "Subscription expired",
    message:
      "Some school management actions are temporarily restricted. Renew your subscription to restore full access. Your existing school data remains available.",
    icon: ShieldAlert,
    toneClass: "bg-error-soft text-error",
    deadlineLabel: "Subscription ended",
    primaryLabel: "Renew subscription",
  },
  cancelled: {
    title: "Your subscription is no longer active",
    eyebrow: "Subscription cancelled",
    message:
      "Billing access remains available, but restricted school management actions require an active subscription.",
    icon: CreditCard,
    toneClass: "bg-surface-muted text-text-soft",
    deadlineLabel: "Access ended",
    primaryLabel: "Choose a plan",
  },
};

const BILLING_PATHS = [
  "/admin/billing",
  "/admin/billing/plans",
  "/billing/subscription/verify",
];

const isBillingPath = (pathname) =>
  BILLING_PATHS.some(
    (path) => pathname === path || pathname.startsWith(`${path}/`),
  );

const getDeadline = (statusCode, subscription) => {
  if (!subscription) return null;

  if (statusCode === "grace_period") {
    return subscription.grace_ends_at || subscription.current_period_end || null;
  }

  if (statusCode === "expired" || statusCode === "cancelled") {
    return (
      subscription.expired_at ||
      subscription.grace_ends_at ||
      subscription.current_period_end ||
      null
    );
  }

  return subscription.current_period_end || null;
};

const buildDismissalKey = (statusCode, subscription) => {
  const fingerprint = [
    subscription?.id || "current",
    statusCode || "unknown",
    subscription?.current_period_end || "",
    subscription?.grace_ends_at || "",
    subscription?.expired_at || "",
  ].join(":");

  return `weave:subscription-lifecycle-prompt:${fingerprint}`;
};

function SubscriptionLifecyclePrompt({
  isTenantAdmin,
  currentSubscription,
  entitlements,
  statusCode,
  isLoading,
  isRefreshing,
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const normalizedStatus = String(statusCode || "").trim().toLowerCase();
  const content = STATUS_CONTENT[normalizedStatus] || null;
  const hasResolvedState = Boolean(currentSubscription || entitlements);
  const dismissalKey = useMemo(
    () => buildDismissalKey(normalizedStatus, currentSubscription),
    [currentSubscription, normalizedStatus],
  );
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setDismissed(window.sessionStorage.getItem(dismissalKey) === "dismissed");
  }, [dismissalKey]);

  const shouldOpen = Boolean(
    isTenantAdmin &&
      hasResolvedState &&
      PROMPTABLE_STATUSES.has(normalizedStatus) &&
      content &&
      !isLoading &&
      !isRefreshing &&
      !isBillingPath(location.pathname) &&
      !dismissed,
  );

  if (!content) return null;

  const Icon = content.icon;
  const deadline = getDeadline(normalizedStatus, currentSubscription);
  const planCode = currentSubscription?.plan_code || entitlements?.plan || null;

  const dismiss = () => {
    if (typeof window !== "undefined") {
      window.sessionStorage.setItem(dismissalKey, "dismissed");
    }
    setDismissed(true);
  };

  const goToPlans = () => {
    dismiss();
    navigate("/admin/billing/plans");
  };

  const goToBilling = () => {
    dismiss();
    navigate("/admin/billing");
  };

  return (
    <Modal
      open={shouldOpen}
      title={content.title}
      onClose={dismiss}
      closeOnOverlay
      showClose
      placement="center"
      className="max-w-[31rem] rounded-[1.75rem]"
      footer={
        <div className="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button
            type="button"
            variant="outline"
            onClick={goToBilling}
            className="w-full sm:w-auto"
          >
            View billing
          </Button>
          <Button
            type="button"
            onClick={goToPlans}
            className="w-full sm:w-auto"
          >
            <CreditCard className="h-4 w-4" />
            {content.primaryLabel}
          </Button>
        </div>
      }
    >
      <div className="space-y-5">
        <div className="flex items-start gap-4">
          <div
            className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl ${content.toneClass}`}
          >
            <Icon className="h-6 w-6" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
              {content.eyebrow}
            </p>
            <p className="mt-2 text-sm leading-6 text-text-soft">
              {content.message}
            </p>
          </div>
        </div>

        <div className="grid gap-3 rounded-2xl border border-border/80 bg-surface-muted/35 p-4 sm:grid-cols-2">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-text-muted">
              Current plan
            </p>
            <p className="mt-1 text-sm font-semibold text-text">
              {planCode ? formatPlanName(planCode) : "Subscription"}
            </p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-text-muted">
              {content.deadlineLabel}
            </p>
            <p className="mt-1 text-sm font-semibold text-text">
              {deadline ? formatDateTime(deadline) : "Payment required"}
            </p>
          </div>
        </div>

        <p className="text-xs leading-5 text-text-muted">
          You can dismiss this message and continue to any area that remains available. Subscription restrictions are still enforced securely by the server.
        </p>
      </div>
    </Modal>
  );
}

export default SubscriptionLifecyclePrompt;
