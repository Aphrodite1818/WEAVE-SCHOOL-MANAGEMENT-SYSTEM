import { CheckCircle2, ShieldAlert, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import PublicLayout from "../../components/layout/PublicLayout";
import LoadingState from "../../components/shared/LoadingState";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import {
  BILLING_INTERVAL_OPTIONS,
  LANDING_PRICING_PLANS,
  formatLimitValue,
  formatPlanName,
} from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { authSession, parseApiError } from "../../services/api";
import {
  getSubscriptionCheckoutErrorMessage,
  subscriptionService,
} from "../../services/subscriptionService";

const PLAN_RANK = {
  free_trial: 0,
  plus: 1,
  professional: 2,
  enterprise: 3,
};

function defaultSelection(currentPlan) {
  if (!currentPlan || currentPlan === "free_trial") return "plus";
  return currentPlan;
}

function SubscriptionOptionsPage() {
  const user = authSession.getUser() || {};
  const {
    currentSubscription,
    entitlements,
    planCode,
    statusCode,
    statusMeta,
    isLoading,
    errors,
  } = useSubscription();

  const paidPlans = useMemo(
    () => LANDING_PRICING_PLANS.filter((plan) => plan.planCode !== "free_trial"),
    [],
  );
  const [selectedPlanCode, setSelectedPlanCode] = useState(defaultSelection(planCode));
  const [billingInterval, setBillingInterval] = useState("monthly");
  const [billingEmail, setBillingEmail] = useState(user.email || "");
  const [preview, setPreview] = useState(null);
  const [planChange, setPlanChange] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);

  const selectedPlan = paidPlans.find((plan) => plan.planCode === selectedPlanCode);
  const currentRank = PLAN_RANK[planCode] ?? 0;
  const selectedRank = PLAN_RANK[selectedPlanCode] ?? 0;
  const isDowngrade = selectedRank < currentRank;
  const isUpgrade = selectedRank > currentRank;
  const samePlan = selectedPlanCode === planCode;
  const retryCurrentPlan = samePlan && ["past_due", "grace_period", "expired"].includes(
    String(statusCode || "").toLowerCase(),
  );
  const matchingPlanChange = planChange?.target_plan_code === selectedPlanCode
    ? planChange
    : null;
  const downgradeReadyForPayment = matchingPlanChange?.status === "awaiting_payment";

  useEffect(() => {
    if (!planCode) return;
    setSelectedPlanCode((current) => current || defaultSelection(planCode));
  }, [planCode]);

  useEffect(() => {
    let active = true;
    subscriptionService.getCurrentPlanChange()
      .then((response) => {
        if (active) setPlanChange(response || null);
      })
      .catch(() => {
        if (active) setPlanChange(null);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    setPreview(null);
    if (!isDowngrade || downgradeReadyForPayment) return () => {};

    setPreviewLoading(true);
    subscriptionService.previewPlanChange(selectedPlanCode)
      .then((response) => {
        if (active) setPreview(response);
      })
      .catch((error) => {
        if (active) {
          const parsed = parseApiError(error, "Could not review this plan change.");
          setErrorMessage(parsed.message);
        }
      })
      .finally(() => {
        if (active) setPreviewLoading(false);
      });

    return () => {
      active = false;
    };
  }, [downgradeReadyForPayment, isDowngrade, selectedPlanCode]);

  const startCheckout = async () => {
    setBusy(true);
    setErrorMessage("");
    setSuccessMessage("");
    try {
      const response = await subscriptionService.initializeSubscriptionCheckout({
        plan_code: selectedPlanCode,
        billing_interval: billingInterval,
        billing_email: billingEmail,
      });
      window.location.assign(response.authorization_url);
    } catch (error) {
      const parsed = parseApiError(error, "We could not initialize billing right now.");
      setErrorMessage(getSubscriptionCheckoutErrorMessage(parsed.message) || parsed.message);
      setBusy(false);
    }
  };

  const scheduleDowngrade = async () => {
    setBusy(true);
    setErrorMessage("");
    setSuccessMessage("");
    try {
      const response = await subscriptionService.schedulePlanChange(selectedPlanCode);
      setPlanChange(response);
      setSuccessMessage(
        `${formatPlanName(selectedPlanCode)} is scheduled for the end of the current billing period. New resource creation now follows its limits.`,
      );
    } catch (error) {
      const parsed = parseApiError(error, "Could not schedule this downgrade.");
      setErrorMessage(parsed.message);
    } finally {
      setBusy(false);
    }
  };

  const performPlanAction = () => {
    if (isDowngrade && !downgradeReadyForPayment) {
      scheduleDowngrade();
      return;
    }
    startCheckout();
  };

  const actionLabel = (() => {
    if (busy) return "Working...";
    if (samePlan && !retryCurrentPlan) return "Current plan";
    if (downgradeReadyForPayment) return `Pay for ${formatPlanName(selectedPlanCode)}`;
    if (isDowngrade) return `Schedule ${formatPlanName(selectedPlanCode)}`;
    if (isUpgrade) return `Upgrade to ${formatPlanName(selectedPlanCode)}`;
    return `Retry ${formatPlanName(selectedPlanCode)}`;
  })();

  const actionDisabled = busy
    || !billingEmail
    || (samePlan && !retryCurrentPlan)
    || (isDowngrade && !downgradeReadyForPayment && (!preview || !preview.eligible));

  if (isLoading && !currentSubscription && !entitlements) {
    return (
      <PublicLayout>
        <div className="mx-auto min-h-screen max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          <LoadingState label="Loading subscription plans..." />
        </div>
      </PublicLayout>
    );
  }

  return (
    <PublicLayout>
      <main className="mx-auto min-h-screen max-w-7xl px-4 py-7 sm:px-6 lg:px-8">
        <section className="rounded-[1.75rem] border border-border/70 bg-surface p-5 shadow-sm sm:p-7">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-primary">Subscription plans</p>
              <h1 className="mt-2 text-3xl font-semibold text-text">Choose the capacity your school needs</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-text-muted">
                Upgrades activate after payment. Downgrades are scheduled for the current period end and require your active records to fit the target limits.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={statusMeta.badgeVariant}>{statusMeta.label}</Badge>
              <Link to="/admin/billing"><Button variant="outline">Back to billing</Button></Link>
            </div>
          </div>
        </section>

        {errors.currentSubscription ? <Notice tone="warning">{errors.currentSubscription}</Notice> : null}
        {errors.entitlements ? <Notice tone="warning">{errors.entitlements}</Notice> : null}
        {errorMessage ? <Notice tone="error">{errorMessage}</Notice> : null}
        {successMessage ? <Notice tone="success">{successMessage}</Notice> : null}

        {planChange ? (
          <Notice tone={planChange.status === "blocked" ? "warning" : "info"}>
            Existing plan change: {formatPlanName(planChange.current_plan_code)} → {formatPlanName(planChange.target_plan_code)} ({String(planChange.status).replaceAll("_", " ")}).
          </Notice>
        ) : null}

        <section className="mt-5 grid gap-4 lg:grid-cols-3">
          {paidPlans.map((plan) => {
            const selected = plan.planCode === selectedPlanCode;
            const current = plan.planCode === planCode;
            return (
              <button
                key={plan.planCode}
                type="button"
                onClick={() => {
                  setSelectedPlanCode(plan.planCode);
                  setErrorMessage("");
                  setSuccessMessage("");
                }}
                className={`flex min-h-[390px] flex-col rounded-[1.6rem] border bg-surface p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-premium-hover ${
                  selected ? "border-primary ring-4 ring-primary/10" : "border-border/70"
                }`}
              >
                <div className="flex min-h-8 flex-wrap items-center gap-2">
                  {plan.highlighted ? <Badge variant="primary">Recommended</Badge> : null}
                  {current ? <Badge variant="success">Current plan</Badge> : null}
                </div>
                <div className="mt-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                  <Sparkles className="h-6 w-6" />
                </div>
                <h2 className="mt-5 text-2xl font-semibold text-text">{plan.name}</h2>
                <p className="mt-2 text-xl font-bold text-text">{plan.priceLabel}</p>
                <ul className="mt-5 space-y-3 text-sm text-text-soft">
                  {(plan.features || []).slice(0, 6).map((feature) => (
                    <li key={feature} className="flex items-start gap-2">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
                <div className="mt-auto grid gap-2 border-t border-border/70 pt-5 text-sm text-text-muted">
                  <PlanLimit label="Students" value={formatLimitValue(plan.limits?.students)} />
                  <PlanLimit label="Teachers" value={formatLimitValue(plan.limits?.teachers)} />
                  <PlanLimit label="Classes" value={formatLimitValue(plan.limits?.classes)} />
                </div>
              </button>
            );
          })}
        </section>

        <section className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.75fr)]">
          <Card className="p-5 sm:p-6">
            <h2 className="text-xl font-semibold text-text">Plan change details</h2>
            <p className="mt-2 text-sm leading-6 text-text-muted">
              Selected: <strong>{selectedPlan?.name || formatPlanName(selectedPlanCode)}</strong>
            </p>

            {previewLoading ? <div className="mt-5"><LoadingState label="Checking current usage..." /></div> : null}
            {isDowngrade && preview ? (
              <div className="mt-5">
                {preview.eligible ? (
                  <Notice tone="info">
                    Your school fits this plan. It can be scheduled for {preview.effective_at ? new Date(preview.effective_at).toLocaleDateString() : "the current period end"}.
                  </Notice>
                ) : (
                  <div className="rounded-2xl border border-warning/30 bg-warning-soft p-4">
                    <div className="flex items-start gap-2 text-amber-700">
                      <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
                      <div>
                        <p className="font-semibold">Reduce active usage before downgrading</p>
                        <p className="mt-1 text-sm">Weave will not delete school records automatically.</p>
                      </div>
                    </div>
                    <div className="mt-4 grid gap-2">
                      {(preview.blockers || []).map((blocker) => (
                        <div key={blocker.resource} className="rounded-xl border border-warning/25 bg-surface px-3 py-2 text-sm text-text">
                          <strong className="capitalize">{String(blocker.resource).replaceAll("_", " ")}</strong>: {blocker.used} active, limit {blocker.limit}, excess {blocker.excess}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : null}

            {downgradeReadyForPayment ? (
              <Notice tone="info">
                The previous paid period has ended and the scheduled downgrade is ready for payment.
              </Notice>
            ) : null}

            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-text-soft">Billing interval</span>
                <select className="input-base" value={billingInterval} onChange={(event) => setBillingInterval(event.target.value)}>
                  {BILLING_INTERVAL_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </label>
              <Input
                label="Billing email"
                type="email"
                value={billingEmail}
                onChange={(event) => setBillingEmail(event.target.value)}
                placeholder="admin@school.example"
              />
            </div>

            <Button className="mt-6 w-full sm:w-auto" disabled={actionDisabled} onClick={performPlanAction}>
              {actionLabel}
            </Button>
          </Card>

          <Card className="p-5 sm:p-6">
            <h2 className="text-lg font-semibold text-text">Downgrade guardrails</h2>
            <ul className="mt-4 space-y-3 text-sm leading-6 text-text-muted">
              <li>Existing data is never deleted automatically.</li>
              <li>The target plan must fit all active resource counts.</li>
              <li>Target limits apply to new writes immediately after scheduling.</li>
              <li>Usage is checked again when the current paid period ends.</li>
              <li>Payment for the lower plan is accepted only after it becomes due.</li>
            </ul>
          </Card>
        </section>
      </main>
    </PublicLayout>
  );
}

function PlanLimit({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span>{label}</span>
      <strong className="text-text">{value}</strong>
    </div>
  );
}

function Notice({ children, tone = "info" }) {
  const classes = {
    info: "border-info/30 bg-info-soft text-info",
    warning: "border-warning/30 bg-warning-soft text-amber-700",
    error: "border-error/30 bg-error-soft text-error",
    success: "border-success/30 bg-success-soft text-success",
  }[tone];
  return <div className={`mt-5 rounded-2xl border px-4 py-3 text-sm font-medium ${classes}`}>{children}</div>;
}

export default SubscriptionOptionsPage;
