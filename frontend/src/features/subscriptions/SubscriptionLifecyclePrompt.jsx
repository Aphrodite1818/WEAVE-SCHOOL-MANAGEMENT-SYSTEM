import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CreditCard, ShieldAlert } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import { formatDateTime, formatPlanName } from "./subscriptionConfig";

const PROMPTABLE_STATUSES = new Set([
  "grace_period",
  "expired",
  "cancelled",
]);

const STATUS_CONTENT = {
  grace_period: {
    title: "Payment needs attention",
    description:
      "We are still trying to renew your subscription. Your school remains available during the grace period.",
    eyebrow: "Grace period",
    message:
      "Update your payment details before the grace period ends to avoid an interruption to school management actions.",
    icon: AlertTriangle,
    deadlineLabel: "Grace period ends",
    primaryLabel: "Update payment",
  },
  expired: {
    title: "Subscription paused",
    description:
      "We could not renew your subscription before the grace period ended.",
    eyebrow: "Action required",
    message:
      "School management actions are temporarily paused. Your existing data remains safe and full access returns after payment is restored.",
    icon: ShieldAlert,
    deadlineLabel: "Access paused",
    primaryLabel: "Update payment",
  },
  cancelled: {
    title: "Subscription inactive",
    description:
      "This subscription is no longer active for your school.",
    eyebrow: "Subscription inactive",
    message:
      "Your school data remains available, but restricted management actions require an active subscription.",
    icon: CreditCard,
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

  return null;
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
      description={content.description}
      onClose={dismiss}
      closeOnOverlay
      showClose
      placement="center"
      className="max-w-[29rem]"
      footer={
        <div className="flex w-full flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-between">
          <Button
            type="button"
            variant="ghost"
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
      <div className="space-y-4">
        <div className="rounded-2xl border border-primary/20 bg-primary-subtle/50 p-4">
          <div className="flex items-start gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
              <Icon className="h-5 w-5" aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-text">{content.eyebrow}</p>
              <p className="mt-1 text-sm leading-6 text-text-muted">{content.message}</p>
            </div>
          </div>

          <div className="mt-4 grid gap-3 border-t border-primary/15 pt-4 sm:grid-cols-2">
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
        </div>
      </div>
    </Modal>
  );
}

export default SubscriptionLifecyclePrompt;
