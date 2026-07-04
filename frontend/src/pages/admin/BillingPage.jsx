import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  CreditCard,
  Lock,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import { authSession, parseApiError } from "../../services/api";
import {
  getSubscriptionCheckoutErrorMessage,
  subscriptionService,
} from "../../services/subscriptionService";
import {
  BILLING_INTERVAL_OPTIONS,
  FEATURE_CODES,
  LANDING_PRICING_PLANS,
  clearSelectedSubscriptionPlan,
  formatBillingInterval,
  formatDateTime,
  formatLimitValue,
  formatPlanName,
  formatUsageValue,
  getSelectedSubscriptionPlan,
  saveSelectedSubscriptionPlan,
} from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";

const FEATURE_SUMMARY_ITEMS = [
  {
    key: FEATURE_CODES.REPORT_CARDS,
    title: "Report cards",
    description: "Generate, regenerate, review, and publish report cards.",
  },
  {
    key: FEATURE_CODES.ADVANCED_ANALYTICS,
    title: "Advanced analytics",
    description: "Unlock deeper academic and operational reporting.",
  },
  {
    key: FEATURE_CODES.AI_ASSISTANT,
    title: "AI assistant",
    description: "Enable the in-app AI workflow for faster admin support.",
  },
  {
    key: FEATURE_CODES.BULK_IMPORT,
    title: "Bulk imports",
    description: "Import larger datasets without one-by-one manual entry.",
  },
];

const DETAIL_FIELDS = [
  { key: "status", label: "Subscription status" },
  { key: "billing_interval", label: "Billing interval" },
  { key: "current_period_start", label: "Current period start" },
  { key: "current_period_end", label: "Current period end" },
  { key: "trial_ends_at", label: "Trial ends at" },
  { key: "grace_ends_at", label: "Grace ends at" },
  { key: "next_payment_at", label: "Next payment at" },
  { key: "cancel_at_period_end", label: "Cancel at period end" },
];

const USAGE_FIELDS = [
  { key: "students", label: "Students" },
  { key: "teachers", label: "Teachers" },
  { key: "parents", label: "Parents" },
  { key: "classes", label: "Classes" },
  { key: "subjects", label: "Subjects" },
];

function DetailValue({ fieldKey, subscription, statusMeta }) {
  if (fieldKey === "status") {
    return statusMeta.label;
  }

  if (fieldKey === "billing_interval") {
    return formatBillingInterval(subscription?.billing_interval);
  }

  if (fieldKey === "cancel_at_period_end") {
    return subscription?.cancel_at_period_end ? "Yes" : "No";
  }

  return formatDateTime(subscription?.[fieldKey]);
}

function BillingPage() {
  const user = authSession.getUser() || {};
  const storedSelection = useMemo(() => getSelectedSubscriptionPlan(), []);
  const {
    currentSubscription,
    entitlements,
    planCode,
    statusCode,
    statusMeta,
    isAttentionRequired,
    isLoading,
    isRefreshing,
    errors,
    refreshSubscriptionState,
  } = useSubscription();
  const [selectedPlanCode, setSelectedPlanCode] = useState(
    storedSelection?.planCode || "plus"
  );
  const [billingInterval, setBillingInterval] = useState(
    storedSelection?.billingInterval || "monthly"
  );
  const [billingEmail, setBillingEmail] = useState(user?.email || "");
  const [checkoutError, setCheckoutError] = useState(null);
  const [isCheckingOut, setIsCheckingOut] = useState(false);
  const effectiveSelectedPlanCode =
    planCode &&
    planCode !== "free_trial" &&
    (!storedSelection?.planCode || storedSelection.planCode === "free_trial")
      ? planCode
      : selectedPlanCode;

  useEffect(() => {
    saveSelectedSubscriptionPlan({
      planCode: effectiveSelectedPlanCode,
      billingInterval,
    });
  }, [billingInterval, effectiveSelectedPlanCode]);

  useEffect(() => {
    if (
      planCode &&
      statusCode === "active" &&
      storedSelection?.planCode === planCode
    ) {
      clearSelectedSubscriptionPlan();
    }
  }, [planCode, statusCode, storedSelection?.planCode]);

  const usageSummary = {
    students: entitlements?.usage?.students || null,
    teachers: entitlements?.usage?.teachers || null,
    classes: entitlements?.usage?.classes || null,
  };

  const currentPlanIsSelected = effectiveSelectedPlanCode === planCode;
  const selectedPlan = LANDING_PRICING_PLANS.find(
    (plan) => plan.planCode === effectiveSelectedPlanCode
  );
  const selectedPlanName = formatPlanName(effectiveSelectedPlanCode);
  const selectedPlanRequiresCheckout =
    effectiveSelectedPlanCode !== "free_trial";
  const canRetryCurrentPlan = ["past_due", "grace_period", "expired"].includes(
    String(statusCode || "").toLowerCase()
  );
  const checkoutDisabledReason = !selectedPlanRequiresCheckout
    ? "Free Trial is assigned during signup and does not require checkout."
    : currentPlanIsSelected && !canRetryCurrentPlan
      ? "You are already on this plan."
      : null;

  const handleCheckout = async () => {
    if (!selectedPlanRequiresCheckout || checkoutDisabledReason) return;

    setIsCheckingOut(true);
    setCheckoutError(null);

    try {
      const response = await subscriptionService.initializeSubscriptionCheckout({
        plan_code: effectiveSelectedPlanCode,
        billing_interval: billingInterval,
        billing_email: billingEmail,
      });

      saveSelectedSubscriptionPlan({
        planCode: effectiveSelectedPlanCode,
        billingInterval,
      });
      window.location.assign(response.authorization_url);
    } catch (error) {
      const apiError = parseApiError(
        error,
        "We could not initialize billing right now."
      );
      setCheckoutError(
        getSubscriptionCheckoutErrorMessage(apiError.message) || apiError.message
      );
      setIsCheckingOut(false);
    }
  };

  const refreshAction = (
    <Button
      variant="outline"
      onClick={() => refreshSubscriptionState()}
      disabled={isLoading || isRefreshing}
    >
      <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
      {isRefreshing ? "Refreshing..." : "Refresh"}
    </Button>
  );

  if (isLoading && !currentSubscription && !entitlements) {
    return (
      <DashboardLayout
        role="admin"
        title="Billing"
        description="Manage your current plan, billing state, and subscription usage."
        actions={refreshAction}
      >
        <LoadingState label="Loading subscription..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="admin"
      title="Billing"
      description="Manage your current plan, billing state, and subscription usage."
      actions={refreshAction}
    >
      <div className="space-y-5">
        {errors.currentSubscription ? (
          <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-medium text-amber-700">
            {errors.currentSubscription}
          </div>
        ) : null}

        {errors.entitlements ? (
          <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-medium text-amber-700">
            {errors.entitlements}
          </div>
        ) : null}

        {checkoutError ? (
          <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
            {checkoutError}
          </div>
        ) : null}

        <section className="dashboard-grid xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
          <Card
            className={`p-5 sm:p-6 ${
              isAttentionRequired
                ? "border-warning/40 bg-warning-soft/40"
                : "border-border"
            }`}
          >
            <div className="flex flex-col gap-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={statusMeta.badgeVariant}>
                      {statusMeta.label}
                    </Badge>
                    <Badge variant="default">
                      Current plan: {formatPlanName(planCode)}
                    </Badge>
                  </div>
                  <h2 className="mt-4 text-xl font-semibold text-text">
                    Subscription summary
                  </h2>
                  <p className="mt-1 text-sm leading-6 text-text-muted">
                    {statusMeta.message}
                  </p>
                </div>
                <Button
                  variant="outline"
                  onClick={() => {
                    setSelectedPlanCode(planCode === "free_trial" ? "plus" : planCode || "plus");
                  }}
                >
                  Manage Plan
                </Button>
              </div>

              <div className="dashboard-kpi-grid lg:grid-cols-3">
                <div className="rounded-[1.15rem] border border-border/70 bg-surface px-4 py-3">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                    Renews or expires
                  </p>
                  <p className="mt-2 text-base font-semibold text-text">
                    {formatDateTime(
                      currentSubscription?.current_period_end ||
                        entitlements?.current_period_end
                    )}
                  </p>
                </div>
                <div className="rounded-[1.15rem] border border-border/70 bg-surface px-4 py-3">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                    Students usage
                  </p>
                  <p className="mt-2 text-base font-semibold text-text">
                    {formatUsageValue(usageSummary.students)}
                  </p>
                </div>
                <div className="rounded-[1.15rem] border border-border/70 bg-surface px-4 py-3">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                    Teachers and classes
                  </p>
                  <p className="mt-2 text-base font-semibold text-text">
                    {formatUsageValue(usageSummary.teachers)} / {formatUsageValue(usageSummary.classes)}
                  </p>
                </div>
              </div>
            </div>
          </Card>

          <Card className="p-5 sm:p-6">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                <CreditCard className="h-5 w-5" />
              </span>
              <div>
                <h2 className="text-lg font-semibold text-text">
                  Checkout setup
                </h2>
                <p className="text-sm text-text-muted">
                  Choose a paid plan, confirm the interval, and continue to Paystack.
                </p>
              </div>
            </div>

            <div className="mt-5 space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-text-soft">
                    Billing interval
                  </label>
                  <select
                    className="input-base"
                    value={billingInterval}
                    onChange={(event) => setBillingInterval(event.target.value)}
                  >
                    {BILLING_INTERVAL_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                <Input
                  label="Billing email"
                  type="email"
                  value={billingEmail}
                  onChange={(event) => setBillingEmail(event.target.value)}
                  placeholder="tenant-admin-email@example.com"
                />
              </div>

              <div className="rounded-2xl border border-border/70 bg-surface-muted/35 px-4 py-3">
                <p className="text-sm font-semibold text-text">
                  Selected plan: {selectedPlanName}
                </p>
                <p className="mt-1 text-sm text-text-muted">
                  {selectedPlan?.bestFor || "Choose the plan that matches your school size."}
                </p>
              </div>

              {checkoutDisabledReason ? (
                <div className="rounded-2xl border border-border bg-surface-muted/35 px-4 py-3 text-sm text-text-muted">
                  {checkoutDisabledReason}
                </div>
              ) : null}

              <Button
                className="w-full"
                disabled={
                  isCheckingOut ||
                  !billingEmail ||
                  Boolean(checkoutDisabledReason)
                }
                onClick={handleCheckout}
              >
                {isCheckingOut ? "Redirecting to Paystack..." : "Continue to Paystack"}
              </Button>
            </div>
          </Card>
        </section>

        <section className="dashboard-grid xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <Card className="p-5 sm:p-6">
            <h2 className="text-lg font-semibold text-text">Billing details</h2>
            <p className="mt-1 text-sm text-text-muted">
              Live subscription fields from the backend subscription record.
            </p>

            {currentSubscription ? (
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                {DETAIL_FIELDS.map((field) => (
                  <div
                    key={field.key}
                    className="rounded-[1.1rem] border border-border/70 bg-surface-muted/25 px-4 py-3"
                  >
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                      {field.label}
                    </p>
                    <p className="mt-2 text-sm font-semibold text-text">
                      <DetailValue
                        fieldKey={field.key}
                        subscription={currentSubscription}
                        statusMeta={statusMeta}
                      />
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="mt-5">
                <EmptyState
                  title="No current subscription found"
                  description="We could not find a current subscription record yet. Your current entitlements still appear below when available."
                />
              </div>
            )}
          </Card>

          <Card className="p-5 sm:p-6">
            <h2 className="text-lg font-semibold text-text">Plan usage</h2>
            <p className="mt-1 text-sm text-text-muted">
              Quotas come from the backend entitlement response and remain the source of truth.
            </p>

            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              {USAGE_FIELDS.map((field) => {
                const usage = entitlements?.usage?.[field.key];

                return (
                  <div
                    key={field.key}
                    className="rounded-[1.1rem] border border-border/70 bg-surface-muted/25 px-4 py-3"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-text">
                        {field.label}
                      </p>
                      <Badge
                        variant={usage?.limit_reached ? "warning" : "default"}
                      >
                        {usage?.is_unlimited
                          ? "Unlimited"
                          : formatLimitValue(usage?.limit)}
                      </Badge>
                    </div>
                    <p className="mt-2 text-base font-semibold text-text">
                      {formatUsageValue(usage)}
                    </p>
                    {usage?.limit_reached ? (
                      <p className="mt-1 text-xs font-medium text-amber-700">
                        You have reached the limit for your current plan.
                      </p>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </Card>
        </section>

        <Card className="p-5 sm:p-6">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-text">Available plans</h2>
              <p className="mt-1 text-sm text-text-muted">
                Select a plan to prepare checkout. Paid plans use live checkout and verification.
              </p>
            </div>
            <div className="rounded-full border border-border bg-surface-muted/35 px-3 py-1.5 text-xs font-semibold text-text-muted">
              {formatBillingInterval(billingInterval)} billing selected
            </div>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
            {LANDING_PRICING_PLANS.map((plan) => {
              const isCurrentPlan = plan.planCode === planCode;
              const isSelectedPlan =
                plan.planCode === effectiveSelectedPlanCode;

              return (
                <button
                  key={plan.planCode}
                  type="button"
                  onClick={() => setSelectedPlanCode(plan.planCode)}
                  className={`text-left ${
                    isSelectedPlan
                      ? "rounded-[1.4rem] border-primary ring-4 ring-primary/10"
                      : "rounded-[1.4rem] border-border"
                  } flex min-h-[420px] flex-col border bg-background p-5 shadow-soft-card transition hover:border-primary/40`}
                >
                  <div className="flex min-h-8 items-center gap-2">
                    {plan.highlighted ? (
                      <Badge variant="primary">Most selected</Badge>
                    ) : null}
                    {isCurrentPlan ? (
                      <Badge variant="success">Current plan</Badge>
                    ) : null}
                  </div>

                  <h3 className="mt-4 text-2xl font-semibold text-text">
                    {plan.name}
                  </h3>
                  <p className="mt-2 text-sm font-semibold text-primary">
                    {plan.bestFor}
                  </p>
                  <p className="mt-3 text-sm leading-6 text-text-muted">
                    {plan.description}
                  </p>

                  <ul className="mt-5 space-y-3 text-sm text-text-soft">
                    {plan.features.map((feature) => (
                      <li key={feature} className="flex gap-3">
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                        <span>{feature}</span>
                      </li>
                    ))}
                  </ul>

                  <div className="mt-5 grid gap-2 rounded-2xl border border-border/70 bg-surface-muted/35 px-4 py-3 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-text-muted">Students</span>
                      <span className="font-semibold text-text">
                        {formatLimitValue(plan.limits.students)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-text-muted">Teachers</span>
                      <span className="font-semibold text-text">
                        {formatLimitValue(plan.limits.teachers)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-text-muted">Classes</span>
                      <span className="font-semibold text-text">
                        {formatLimitValue(plan.limits.classes)}
                      </span>
                    </div>
                  </div>

                  <div className="mt-auto pt-6">
                    <div
                      className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${
                        isSelectedPlan
                          ? "bg-primary-soft text-primary"
                          : "bg-surface-muted text-text-muted"
                      }`}
                    >
                      {isSelectedPlan ? "Selected for checkout" : plan.ctaLabel}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </Card>

        <Card className="p-5 sm:p-6">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary-soft text-primary">
              <Sparkles className="h-5 w-5" />
            </span>
            <div>
              <h2 className="text-lg font-semibold text-text">
                Feature access on your current plan
              </h2>
              <p className="text-sm text-text-muted">
                Restricted modules stay visible for context, but remain locked until your plan includes them.
              </p>
            </div>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {FEATURE_SUMMARY_ITEMS.map((feature) => {
              const allowed = entitlements?.features?.[feature.key] === true;

              return (
                <div
                  key={feature.key}
                  className={`rounded-[1.2rem] border px-4 py-4 ${
                    allowed
                      ? "border-success/20 bg-success-soft/40"
                      : "border-border bg-surface-muted/30"
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="text-sm font-semibold text-text">
                      {feature.title}
                    </h3>
                    <Badge variant={allowed ? "success" : "default"}>
                      {allowed ? "Unlocked" : "Locked"}
                    </Badge>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-text-muted">
                    {feature.description}
                  </p>
                  {!allowed ? (
                    <p className="mt-3 flex items-start gap-2 text-sm font-medium text-text-soft">
                      <Lock className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" />
                      <span>
                        This feature is not available on your current plan. Upgrade your plan to unlock it.
                      </span>
                    </p>
                  ) : null}
                </div>
              );
            })}
          </div>
        </Card>

        {storedSelection?.planCode &&
        storedSelection.planCode !== "free_trial" &&
        storedSelection.planCode !== planCode ? (
          <div className="rounded-2xl border border-primary/20 bg-primary-soft/30 px-4 py-3 text-sm text-primary-deep">
            You selected the {formatPlanName(storedSelection.planCode)} plan during signup. It remains preselected here until you complete checkout.
          </div>
        ) : null}

        {isAttentionRequired ? (
          <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-medium text-amber-700">
            <span className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                Your subscription needs attention. Complete billing to restore or protect access to paid features.
              </span>
            </span>
          </div>
        ) : null}
      </div>
    </DashboardLayout>
  );
}

export default BillingPage;
