import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, CreditCard, RefreshCw, ShieldCheck } from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import LoadingState from "../../components/shared/LoadingState";
import { authSession, parseApiError } from "../../services/api";
import {
  getSubscriptionCheckoutErrorMessage,
  subscriptionService,
} from "../../services/subscriptionService";
import {
  BILLING_INTERVAL_OPTIONS,
  LANDING_PRICING_PLANS,
  clearSelectedSubscriptionPlan,
  formatBillingInterval,
  formatDateTime,
  formatLimitValue,
  formatPlanName,
  getSelectedSubscriptionPlan,
  saveSelectedSubscriptionPlan,
} from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";

function getDefaultSelection(currentPlanCode) {
  if (!currentPlanCode || currentPlanCode === "free_trial") return "plus";
  return currentPlanCode;
}

function SubscriptionOptionsPage() {
  const user = authSession.getUser() || {};
  const storedSelection = useMemo(() => getSelectedSubscriptionPlan(), []);
  const {
    currentSubscription,
    entitlements,
    planCode,
    statusCode,
    statusMeta,
    isLoading,
    isRefreshing,
    errors,
    refreshSubscriptionState,
  } = useSubscription();
  const [selectedPlanCode, setSelectedPlanCode] = useState(
    storedSelection?.planCode || getDefaultSelection(planCode)
  );
  const [billingInterval, setBillingInterval] = useState(
    storedSelection?.billingInterval || "monthly"
  );
  const [billingEmail, setBillingEmail] = useState(user?.email || "");
  const [checkoutError, setCheckoutError] = useState(null);
  const [isCheckingOut, setIsCheckingOut] = useState(false);

  const effectiveSelectedPlanCode = selectedPlanCode || getDefaultSelection(planCode);
  const selectedPlan = LANDING_PRICING_PLANS.find(
    (plan) => plan.planCode === effectiveSelectedPlanCode
  );
  const selectedPlanRequiresCheckout = effectiveSelectedPlanCode !== "free_trial";
  const currentPlanIsSelected = effectiveSelectedPlanCode === planCode;
  const canRetryCurrentPlan = ["past_due", "grace_period", "expired"].includes(
    String(statusCode || "").toLowerCase()
  );
  const checkoutDisabledReason = !selectedPlanRequiresCheckout
    ? "Free Trial is assigned during signup and does not require checkout."
    : currentPlanIsSelected && !canRetryCurrentPlan
      ? "This is your current plan."
      : null;

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
        title="Upgrade Plan"
        description="Compare subscription options and continue to secure checkout."
        actions={refreshAction}
      >
        <LoadingState label="Loading plans..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="admin"
      title="Upgrade Plan"
      description="Compare subscription options and continue to secure checkout."
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

        <section className="dashboard-grid xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-4">
            {LANDING_PRICING_PLANS.map((plan) => {
              const isCurrentPlan = plan.planCode === planCode;
              const isSelectedPlan = plan.planCode === effectiveSelectedPlanCode;

              return (
                <button
                  key={plan.planCode}
                  type="button"
                  onClick={() => setSelectedPlanCode(plan.planCode)}
                  className={`flex min-h-[430px] flex-col rounded-[1.5rem] border bg-surface p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-premium-hover ${
                    isSelectedPlan
                      ? "border-primary ring-4 ring-primary/10"
                      : "border-border/70"
                  }`}
                >
                  <div className="flex min-h-8 flex-wrap items-center gap-2">
                    {plan.highlighted ? <Badge variant="primary">Recommended</Badge> : null}
                    {isCurrentPlan ? <Badge variant="success">Current plan</Badge> : null}
                  </div>

                  <h2 className="mt-4 text-2xl font-semibold text-text">
                    {plan.name}
                  </h2>
                  <p className="mt-2 text-sm font-semibold text-primary">
                    {plan.bestFor}
                  </p>
                  <p className="mt-3 text-sm leading-6 text-text-muted">
                    {plan.description}
                  </p>

                  <div className="mt-5">
                    <p className="text-2xl font-bold text-text">
                      {plan.priceLabel}
                    </p>
                    <p className="mt-1 text-xs font-medium text-text-muted">
                      {formatBillingInterval(billingInterval)} billing
                    </p>
                  </div>

                  <ul className="mt-5 space-y-3 text-sm text-text-soft">
                    {plan.features.map((feature) => (
                      <li key={feature} className="flex gap-3">
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                        <span>{feature}</span>
                      </li>
                    ))}
                  </ul>

                  <div className="mt-5 grid gap-2 rounded-2xl border border-border/70 bg-surface-muted/30 px-4 py-3 text-sm">
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
                    <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${
                      isSelectedPlan
                        ? "bg-primary-soft text-primary"
                        : "bg-surface-muted text-text-muted"
                    }`}>
                      {isSelectedPlan ? "Selected" : plan.ctaLabel}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>

          <Card className="h-fit p-5 sm:p-6">
            <div className="flex items-start gap-3">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                <CreditCard className="h-5 w-5" />
              </span>
              <div>
                <h2 className="text-lg font-semibold text-text">Checkout</h2>
                <p className="mt-1 text-sm leading-6 text-text-muted">
                  Confirm the selected plan and continue to Paystack.
                </p>
              </div>
            </div>

            <div className="mt-5 space-y-4">
              <div className="rounded-2xl border border-border/70 bg-surface-muted/30 px-4 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                  Current plan
                </p>
                <div className="mt-2 flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-text">
                    {formatPlanName(planCode)}
                  </p>
                  <Badge variant={statusMeta.badgeVariant}>{statusMeta.label}</Badge>
                </div>
                <p className="mt-2 text-xs text-text-muted">
                  Renews or expires: {formatDateTime(currentSubscription?.current_period_end || entitlements?.current_period_end)}
                </p>
              </div>

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

              <div className="rounded-2xl border border-border/70 bg-surface-muted/30 px-4 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                  Selected plan
                </p>
                <p className="mt-2 text-base font-semibold text-text">
                  {selectedPlan?.name || formatPlanName(effectiveSelectedPlanCode)}
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
                {isCheckingOut ? "Redirecting to Paystack..." : "Upgrade Plan"}
              </Button>

              <div className="flex items-start gap-2 rounded-2xl border border-border/70 bg-surface-muted/25 px-4 py-3 text-xs leading-5 text-text-muted">
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                <span>
                  Checkout is initialized by the backend subscription endpoint, then verified after Paystack redirects back to the app.
                </span>
              </div>
            </div>
          </Card>
        </section>
      </div>
    </DashboardLayout>
  );
}

export default SubscriptionOptionsPage;
