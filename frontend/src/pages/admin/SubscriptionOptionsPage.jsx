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
          <div className="rounded-[1.5rem] border border-border/70 bg-surface p-6 shadow-sm">
            <div>
              <h1 className="text-2xl font-semibold text-text">Upgrade Plan</h1>
              <p className="mt-2 text-sm text-text-muted">
                Compare subscription options and continue to secure checkout.
              </p>
            </div>
          </div>
          <div className="mt-6">
            <LoadingState label="Loading plans..." />
          </div>
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
          <div className="absolute bottom-20 left-1/3 h-40 w-40 rounded-full bg-primary/[0.08] blur-3xl" />
        </div>

        <div className="relative z-10 mb-6 rounded-[1.5rem] border border-border/70 bg-surface p-6 shadow-sm md:hidden">
          <div>
            <h1 className="text-2xl font-semibold text-text">Upgrade Plan</h1>
            <p className="mt-2 text-sm text-text-muted">
              Compare subscription options and continue to secure checkout.
            </p>
          </div>
        </div>

        <section className="relative z-10 mb-6 hidden items-center justify-center md:flex">
          <div className="justify-self-center">
            <div className="relative inline-grid grid-cols-3 items-center rounded-full border border-border/70 bg-surface-muted/65 p-1 shadow-soft-card">
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
                    key={`desktop-switch-${plan.planCode}`}
                    type="button"
                    onClick={() => setSelectedPlanCode(plan.planCode)}
                    className={`relative z-10 min-w-[8.5rem] rounded-full px-4 py-2.5 text-center transition ${
                      isSelectedPlan ? "text-text" : "text-text-muted hover:text-text"
                    }`}
                  >
                    <span className="block text-sm font-semibold">{plan.name}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </section>

        <div className="relative z-10 space-y-5 pb-24 md:pb-0">
          {errors.currentSubscription ? (
            <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-medium text-amber-950">
              {errors.currentSubscription}
            </div>
          ) : null}
          {errors.entitlements ? (
            <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-medium text-amber-950">
              {errors.entitlements}
            </div>
          ) : null}
          {checkoutError ? (
            <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
              {checkoutError}
            </div>
          ) : null}

          <section className="md:hidden">
            <Card className="overflow-hidden rounded-[2rem] p-5">
              <div className="flex flex-col items-center text-center">
                <span className="flex h-14 w-14 rotate-45 items-center justify-center rounded-2xl bg-primary text-text-inverse shadow-sm shadow-primary/30">
                  <Sparkles className="h-6 w-6 -rotate-45" />
                </span>
                <h2 className="mt-6 text-3xl font-semibold tracking-tight text-text">Upgrade your plan</h2>
                <p className="mt-2 max-w-sm text-sm leading-6 text-text-muted">
                  Get higher school limits and more workspace capacity for your team.
                </p>
              </div>

              <div className="mt-7 grid grid-cols-1 gap-3">
                {paidPlans.map((plan) => {
                  const isSelectedPlan = plan.planCode === effectiveSelectedPlanCode;
                  const isCurrentPlan = plan.planCode === planCode;
                  const planIsLocked = isCurrentPlan && !canRetryCurrentPlan;

                  return (
                    <div
                      key={plan.planCode}
                      role="button"
                      tabIndex={0}
                      onClick={() => setSelectedPlanCode(plan.planCode)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") setSelectedPlanCode(plan.planCode);
                      }}
                      className={`min-h-[6rem] rounded-2xl border px-4 py-4 text-left transition ${
                        isSelectedPlan
                          ? "border-warning/40 bg-surface-amber/75 shadow-[0_16px_34px_rgba(245,158,11,0.14)] ring-2 ring-warning/10"
                          : "border-border bg-surface-muted/30"
                      } focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-warning/35`}
                    >
                      <p className="text-lg font-bold leading-tight text-text">{plan.priceLabel}</p>
                      <p className="mt-1 text-sm font-semibold text-text-muted">{plan.name}</p>
                      {isCurrentPlan ? <p className="mt-2 text-[11px] font-bold text-success">Current plan</p> : null}
                      <div className="mt-4">
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
                    </div>
                  );
                })}
              </div>

              <div className="mt-7 rounded-2xl border border-border/70 bg-surface-muted/25 px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Selected plan</p>
                    <p className="mt-1 text-base font-semibold text-text">
                      {selectedPlan?.name || formatPlanName(effectiveSelectedPlanCode)}
                    </p>
                  </div>
                  <Badge variant={statusMeta.badgeVariant}>{statusMeta.label}</Badge>
                </div>
              </div>

              <div className="mt-6 text-left">
                <p className="text-sm font-semibold text-text">Everything included:</p>
                <ul className="mt-4 space-y-4 text-base text-text-soft">
                  {(selectedPlan?.features || []).map((feature) => (
                    <li key={feature} className="flex items-start gap-3">
                      <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="mt-6 grid gap-2 rounded-2xl border border-border/70 bg-surface-muted/25 px-4 py-3 text-sm">
                <PlanLimit label="Students" value={formatLimitValue(selectedPlan?.limits?.students)} />
                <PlanLimit label="Teachers" value={formatLimitValue(selectedPlan?.limits?.teachers)} />
                <PlanLimit label="Classes" value={formatLimitValue(selectedPlan?.limits?.classes)} />
              </div>

              <div ref={checkoutRef} className="mt-6 space-y-4">
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

                {checkoutDisabledReason ? (
                  <div className="rounded-2xl border border-border bg-surface-muted/35 px-4 py-3 text-sm text-text-muted">
                    {checkoutDisabledReason}
                  </div>
                ) : null}
              </div>
            </Card>
          </section>

          <section className="hidden md:block">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {paidPlans.map((plan) => {
                const isCurrentPlan = plan.planCode === planCode;
                const isSelectedPlan = plan.planCode === effectiveSelectedPlanCode;
                const planIsLocked = isCurrentPlan && !canRetryCurrentPlan;

                return (
                  <div
                    key={plan.planCode}
                    role="button"
                    tabIndex={0}
                    onClick={() => setSelectedPlanCode(plan.planCode)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") setSelectedPlanCode(plan.planCode);
                    }}
                    className={`flex min-h-[430px] flex-col rounded-[1.5rem] border bg-surface p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-accent/50 hover:shadow-premium-hover ${
                      isSelectedPlan ? "border-accent ring-4 ring-accent/10" : "border-border/70"
                    } focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50`}
                  >
                    <div className="flex min-h-8 flex-wrap items-center gap-2">
                      {plan.highlighted ? <Badge variant="primary">Recommended</Badge> : null}
                      {isCurrentPlan ? <Badge variant="success">Current plan</Badge> : null}
                    </div>

                    <h2 className="mt-4 text-2xl font-semibold text-text">{plan.name}</h2>
                    <p className="mt-2 text-sm font-semibold text-primary">{plan.bestFor}</p>
                    <p className="mt-3 text-sm leading-6 text-text-muted">{plan.description}</p>

                    <div className="mt-5">
                      <p className="text-2xl font-bold text-text">{plan.priceLabel}</p>
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
                      <PlanLimit label="Students" value={formatLimitValue(plan.limits.students)} />
                      <PlanLimit label="Teachers" value={formatLimitValue(plan.limits.teachers)} />
                      <PlanLimit label="Classes" value={formatLimitValue(plan.limits.classes)} />
                    </div>

                    <div className="flex flex-1 items-center justify-center pt-6">
                      <div className="w-full max-w-[19rem] text-center">
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
                        <div className="mt-3 flex justify-center">
                          <span
                            className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${
                              isSelectedPlan ? "bg-accent-soft text-accent" : "bg-surface-muted text-text-muted"
                            }`}
                          >
                            {isSelectedPlan ? "Selected" : plan.ctaLabel}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        </div>
      </div>
    </PublicLayout>
  );
}

function PlanLimit({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-text-muted">{label}</span>
      <span className="font-semibold text-text">{value}</span>
    </div>
  );
}

export default SubscriptionOptionsPage;
