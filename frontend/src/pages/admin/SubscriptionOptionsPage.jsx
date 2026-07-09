import { CheckCircle2, Sparkles } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import PublicLayout from "../../components/layout/PublicLayout";
import LoadingState from "../../components/shared/LoadingState";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import {
  BILLING_INTERVAL_OPTIONS,
  LANDING_PRICING_PLANS,
  clearSelectedSubscriptionPlan,
  formatBillingInterval,
  formatLimitValue,
  formatPlanName,
  getSelectedSubscriptionPlan,
  saveSelectedSubscriptionPlan,
} from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { authSession, parseApiError } from "../../services/api";
import {
  getSubscriptionCheckoutErrorMessage,
  subscriptionService,
} from "../../services/subscriptionService";

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
    errors,
  } = useSubscription();
  const [selectedPlanCode, setSelectedPlanCode] = useState(
    storedSelection?.planCode || getDefaultSelection(planCode),
  );
  const [billingInterval, setBillingInterval] = useState(
    storedSelection?.billingInterval || "monthly",
  );
  const [billingEmail, setBillingEmail] = useState(user?.email || "");
  const [checkoutError, setCheckoutError] = useState(null);
  const [isCheckingOut, setIsCheckingOut] = useState(false);
  const checkoutRef = useRef(null);

  const paidPlans = LANDING_PRICING_PLANS.filter((plan) => plan.planCode !== "free_trial");
  const effectiveSelectedPlanCode = selectedPlanCode || getDefaultSelection(planCode);
  const selectedPlan = LANDING_PRICING_PLANS.find((plan) => plan.planCode === effectiveSelectedPlanCode);
  const selectedPaidPlanIndex = Math.max(
    paidPlans.findIndex((plan) => plan.planCode === effectiveSelectedPlanCode),
    0,
  );

  const selectedPlanRequiresCheckout = effectiveSelectedPlanCode !== "free_trial";
  const currentPlanIsSelected = effectiveSelectedPlanCode === planCode;
  const canRetryCurrentPlan = ["past_due", "grace_period", "expired"].includes(
    String(statusCode || "").toLowerCase(),
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
    if (planCode && statusCode === "active" && storedSelection?.planCode === planCode) {
      clearSelectedSubscriptionPlan();
    }
  }, [planCode, statusCode, storedSelection?.planCode]);

  const scrollToBillingDetails = () => {
    checkoutRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const handlePlanAction = (planCodeToSelect, isSelectedPlan, planIsLocked) => {
    if (planIsLocked) return;
    setSelectedPlanCode(planCodeToSelect);

    if (isSelectedPlan && !checkoutDisabledReason && billingEmail) {
      handleCheckout();
    } else {
      scrollToBillingDetails();
    }
  };

  const handleCheckout = async () => {
    if (isCheckingOut || !selectedPlanRequiresCheckout || checkoutDisabledReason) return;

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
      const apiError = parseApiError(error, "We could not initialize billing right now.");
      setCheckoutError(getSubscriptionCheckoutErrorMessage(apiError.message) || apiError.message);
      setIsCheckingOut(false);
    }
  };

  if (isLoading && !currentSubscription && !entitlements) {
    return (
      <PublicLayout>
        <div className="mx-auto min-h-screen max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
          <LoadingState label="Loading plans..." />
        </div>
      </PublicLayout>
    );
  }

  return (
    <PublicLayout>
      <div className="relative mx-auto min-h-screen max-w-7xl overflow-hidden px-4 py-6 sm:px-6 lg:px-8">
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
          <div className="absolute inset-x-0 top-4 h-[20rem] rounded-[2.5rem] bg-[radial-gradient(circle_at_top_left,rgba(37,99,235,0.18),transparent_42%),radial-gradient(circle_at_top_right,rgba(59,130,246,0.12),transparent_36%),linear-gradient(180deg,rgba(15,23,42,0.78),rgba(15,23,42,0))]" />
          <div className="absolute -left-12 top-28 h-56 w-56 rounded-full bg-primary/10 blur-3xl" />
          <div className="absolute right-0 top-24 h-48 w-48 rounded-full bg-slate-300/10 blur-3xl" />
        </div>

        <section className="relative z-10 rounded-[1.75rem] border border-border/70 bg-surface p-5 shadow-sm sm:p-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                  <Sparkles className="h-5 w-5" />
                </span>
                <Badge variant={statusMeta.badgeVariant}>{statusMeta.label}</Badge>
              </div>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-text sm:text-4xl">Upgrade Plan</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-text-muted">
                Compare paid plans in one compact row, choose a billing interval, and continue to secure checkout.
              </p>
            </div>

            <div className="grid gap-3 sm:min-w-[24rem]">
              <div className="relative grid grid-cols-3 items-center rounded-full border border-border/70 bg-surface-muted/65 p-1 shadow-soft-card">
                <span
                  aria-hidden="true"
                  className="pointer-events-none absolute inset-y-1 left-1 rounded-full bg-surface shadow-[0_10px_30px_rgba(15,23,42,0.12)] transition-transform duration-300"
                  style={{
                    width: `calc((100% - 0.5rem) / ${paidPlans.length || 1})`,
                    transform: `translateX(calc(${selectedPaidPlanIndex * 100}% + ${selectedPaidPlanIndex * 0.125}rem))`,
                  }}
                />
                {paidPlans.map((plan) => {
                  const isSelectedPlan = plan.planCode === effectiveSelectedPlanCode;
                  return (
                    <button
                      key={`switch-${plan.planCode}`}
                      type="button"
                      onClick={() => setSelectedPlanCode(plan.planCode)}
                      className={`relative z-10 rounded-full px-3 py-2 text-center text-xs font-semibold transition sm:text-sm ${
                        isSelectedPlan ? "text-text" : "text-text-muted hover:text-text"
                      }`}
                    >
                      {plan.name}
                    </button>
                  );
                })}
              </div>

              <div className="grid grid-cols-2 gap-2 rounded-2xl border border-border/70 bg-surface-muted/30 p-1">
                {BILLING_INTERVAL_OPTIONS.map((option) => {
                  const active = option.value === billingInterval;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setBillingInterval(option.value)}
                      className={`rounded-xl px-3 py-2 text-xs font-semibold transition sm:text-sm ${active ? "bg-surface text-primary shadow-sm" : "text-text-muted hover:text-text"}`}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </section>

        <div className="relative z-10 mt-5 space-y-5 pb-16">
          {errors.currentSubscription ? (
            <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-medium text-text">
              {errors.currentSubscription}
            </div>
          ) : null}
          {errors.entitlements ? (
            <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-medium text-text">
              {errors.entitlements}
            </div>
          ) : null}
          {checkoutError ? (
            <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
              {checkoutError}
            </div>
          ) : null}

          <section className="grid gap-4 lg:grid-cols-3">
            {paidPlans.map((plan) => {
              const isCurrentPlan = plan.planCode === planCode;
              const isSelectedPlan = plan.planCode === effectiveSelectedPlanCode;
              const planIsLocked = isCurrentPlan && !canRetryCurrentPlan;

              return (
                <button
                  key={plan.planCode}
                  type="button"
                  onClick={() => setSelectedPlanCode(plan.planCode)}
                  className={`flex min-h-[24rem] flex-col rounded-[1.5rem] border bg-surface p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-premium-hover ${
                    isSelectedPlan ? "border-primary ring-4 ring-primary/10" : "border-border/70"
                  }`}
                >
                  <div className="flex min-h-8 flex-wrap items-center gap-2">
                    {plan.highlighted ? <Badge variant="primary">Recommended</Badge> : null}
                    {isCurrentPlan ? <Badge variant="success">Current plan</Badge> : null}
                    {isSelectedPlan ? <Badge variant="accent">Selected</Badge> : null}
                  </div>

                  <h2 className="mt-4 text-xl font-semibold text-text">{plan.name}</h2>
                  <p className="mt-1 text-sm font-semibold text-primary">{plan.bestFor}</p>
                  <p className="mt-3 text-sm leading-6 text-text-muted">{plan.description}</p>

                  <div className="mt-4">
                    <p className="text-2xl font-bold text-text">{plan.priceLabel}</p>
                    <p className="mt-1 text-xs font-medium text-text-muted">{formatBillingInterval(billingInterval)} billing</p>
                  </div>

                  <div className="mt-4 grid grid-cols-3 gap-2 rounded-2xl border border-border/70 bg-surface-muted/25 p-3 text-center text-xs">
                    <Limit label="Students" value={formatLimitValue(plan.limits.students)} />
                    <Limit label="Teachers" value={formatLimitValue(plan.limits.teachers)} />
                    <Limit label="Classes" value={formatLimitValue(plan.limits.classes)} />
                  </div>

                  <ul className="mt-4 grid gap-2 text-sm text-text-soft">
                    {plan.features.slice(0, 4).map((feature) => (
                      <li key={feature} className="flex gap-2">
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                        <span>{feature}</span>
                      </li>
                    ))}
                  </ul>

                  <div className="mt-auto pt-5">
                    <Button
                      type="button"
                      className="w-full"
                      onClick={(event) => {
                        event.stopPropagation();
                        handlePlanAction(plan.planCode, isSelectedPlan, planIsLocked);
                      }}
                      disabled={planIsLocked || isCheckingOut}
                    >
                      {isCheckingOut
                        ? "Redirecting..."
                        : planIsLocked
                          ? "Current plan"
                          : isSelectedPlan && billingEmail && !checkoutDisabledReason
                            ? "Checkout"
                            : isSelectedPlan
                              ? "Continue"
                              : "Select plan"}
                    </Button>
                  </div>
                </button>
              );
            })}
          </section>

          <section ref={checkoutRef} className="grid gap-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <Card className="p-5 sm:p-6">
              <h2 className="section-title">Selected plan</h2>
              <p className="mt-1 text-sm text-text-muted">Confirm billing details before checkout.</p>
              <div className="mt-5 rounded-2xl border border-border/70 bg-surface-muted/25 px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Plan</p>
                    <p className="mt-1 text-lg font-semibold text-text">{selectedPlan?.name || formatPlanName(effectiveSelectedPlanCode)}</p>
                  </div>
                  <Badge variant={statusMeta.badgeVariant}>{statusMeta.label}</Badge>
                </div>
              </div>
              <ul className="mt-5 grid gap-3 text-sm text-text-soft sm:grid-cols-2">
                {(selectedPlan?.features || []).slice(0, 6).map((feature) => (
                  <li key={feature} className="flex items-start gap-2">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>
            </Card>

            <Card className="p-5 sm:p-6">
              <h2 className="section-title">Checkout details</h2>
              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-text-soft">Billing interval</label>
                  <select className="input-base" value={billingInterval} onChange={(event) => setBillingInterval(event.target.value)}>
                    {BILLING_INTERVAL_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
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
              {checkoutDisabledReason ? (
                <div className="mt-4 rounded-2xl border border-border bg-surface-muted/35 px-4 py-3 text-sm text-text-muted">
                  {checkoutDisabledReason}
                </div>
              ) : null}
              <Button className="mt-5 w-full" disabled={Boolean(checkoutDisabledReason) || isCheckingOut || !billingEmail} onClick={handleCheckout}>
                {isCheckingOut ? "Redirecting..." : "Continue to checkout"}
              </Button>
            </Card>
          </section>
        </div>
      </div>
    </PublicLayout>
  );
}

function Limit({ label, value }) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">{label}</p>
      <p className="mt-1 font-semibold text-text">{value}</p>
    </div>
  );
}

export default SubscriptionOptionsPage;
