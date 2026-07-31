import { CheckCircle2, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import PublicLayout from "../../components/layout/PublicLayout";
import LoadingState from "../../components/shared/LoadingState";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import Modal from "../../components/ui/Modal";
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

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

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
  const [targetPlanCode, setTargetPlanCode] = useState(null);
  const [billingInterval, setBillingInterval] = useState("monthly");
  const [billingEmail, setBillingEmail] = useState(user.email || "");
  const [preview, setPreview] = useState(null);
  const [planChange, setPlanChange] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => {
    let active = true;
    subscriptionService
      .getCurrentPlanChange()
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

  const getPlanContext = (candidatePlanCode) => {
    const currentRank = PLAN_RANK[planCode] ?? 0;
    const candidateRank = PLAN_RANK[candidatePlanCode] ?? 0;
    const samePlan = candidatePlanCode === planCode;
    const retryCurrentPlan =
      samePlan
      && ["past_due", "grace_period", "expired"].includes(
        String(statusCode || "").toLowerCase(),
      );
    const matchingPlanChange =
      planChange?.target_plan_code === candidatePlanCode ? planChange : null;

    return {
      samePlan,
      retryCurrentPlan,
      isDowngrade: candidateRank < currentRank,
      isUpgrade: candidateRank > currentRank,
      downgradeReadyForPayment: matchingPlanChange?.status === "awaiting_payment",
    };
  };

  const selectedPlan = paidPlans.find((plan) => plan.planCode === targetPlanCode) || null;
  const selectedContext = targetPlanCode ? getPlanContext(targetPlanCode) : null;
  const requiresCheckout = Boolean(
    selectedContext
      && (!selectedContext.isDowngrade || selectedContext.downgradeReadyForPayment),
  );
  const validBillingEmail = EMAIL_PATTERN.test(billingEmail.trim());

  const closeModal = () => {
    if (busy) return;
    setModalOpen(false);
    setTargetPlanCode(null);
    setPreview(null);
    setPreviewLoading(false);
  };

  const openPlanModal = async (candidatePlanCode) => {
    const context = getPlanContext(candidatePlanCode);
    if (context.samePlan && !context.retryCurrentPlan) return;

    setTargetPlanCode(candidatePlanCode);
    setErrorMessage("");
    setSuccessMessage("");
    setPreview(null);
    setModalOpen(true);

    if (!context.isDowngrade || context.downgradeReadyForPayment) return;

    setPreviewLoading(true);
    try {
      const response = await subscriptionService.previewPlanChange(candidatePlanCode);
      setPreview(response);
    } catch (error) {
      const parsed = parseApiError(error, "Could not review this plan change.");
      setErrorMessage(parsed.message);
    } finally {
      setPreviewLoading(false);
    }
  };

  const startCheckout = async () => {
    if (!targetPlanCode || !validBillingEmail) return;

    setBusy(true);
    setErrorMessage("");
    setSuccessMessage("");
    try {
      const response = await subscriptionService.initializeSubscriptionCheckout({
        plan_code: targetPlanCode,
        billing_interval: billingInterval,
        billing_email: billingEmail.trim(),
      });
      window.location.assign(response.authorization_url);
    } catch (error) {
      const parsed = parseApiError(error, "We could not initialize billing right now.");
      setErrorMessage(getSubscriptionCheckoutErrorMessage(parsed.message) || parsed.message);
      setBusy(false);
    }
  };

  const scheduleDowngrade = async () => {
    if (!targetPlanCode) return;

    setBusy(true);
    setErrorMessage("");
    setSuccessMessage("");
    try {
      const response = await subscriptionService.schedulePlanChange(targetPlanCode);
      setPlanChange(response);
      setSuccessMessage(
        `${formatPlanName(targetPlanCode)} is scheduled for the end of the current billing period.`,
      );
      setModalOpen(false);
      setTargetPlanCode(null);
      setPreview(null);
    } catch (error) {
      const parsed = parseApiError(error, "Could not schedule this downgrade.");
      setErrorMessage(parsed.message);
    } finally {
      setBusy(false);
    }
  };

  const performPlanAction = () => {
    if (!selectedContext) return;
    if (selectedContext.isDowngrade && !selectedContext.downgradeReadyForPayment) {
      scheduleDowngrade();
      return;
    }
    startCheckout();
  };

  const modalActionLabel = (() => {
    if (busy) return "Working...";
    if (!targetPlanCode || !selectedContext) return "Continue";
    if (selectedContext.downgradeReadyForPayment) {
      return `Checkout for ${formatPlanName(targetPlanCode)}`;
    }
    if (selectedContext.isDowngrade) {
      return `Schedule ${formatPlanName(targetPlanCode)}`;
    }
    if (selectedContext.retryCurrentPlan) return "Retry payment";
    return "Continue to Paystack";
  })();

  const modalActionDisabled =
    busy
    || !selectedContext
    || (requiresCheckout && !validBillingEmail)
    || (selectedContext?.isDowngrade
      && !selectedContext.downgradeReadyForPayment
      && (previewLoading || !preview?.eligible));

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
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-primary">
                Subscription plans
              </p>
              <h1 className="mt-2 text-3xl font-semibold text-text">
                Choose the plan that fits your school
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-text-muted">
                Compare plan features and continue securely through Paystack when you are ready.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={statusMeta.badgeVariant}>{statusMeta.label}</Badge>
              <Link to="/admin/billing">
                <Button variant="outline">Back to billing</Button>
              </Link>
            </div>
          </div>
        </section>

        {errors.currentSubscription ? (
          <Notice tone="warning">{errors.currentSubscription}</Notice>
        ) : null}
        {errors.entitlements ? <Notice tone="warning">{errors.entitlements}</Notice> : null}
        {errorMessage ? <Notice tone="error">{errorMessage}</Notice> : null}
        {successMessage ? <Notice tone="success">{successMessage}</Notice> : null}

        {planChange ? (
          <Notice tone={planChange.status === "blocked" ? "warning" : "info"}>
            {formatPlanName(planChange.target_plan_code)} plan change: {String(
              planChange.status,
            ).replaceAll("_", " ")}.
          </Notice>
        ) : null}

        <section className="mt-5 grid gap-4 lg:grid-cols-3">
          {paidPlans.map((plan) => {
            const context = getPlanContext(plan.planCode);
            const current = context.samePlan && !context.retryCurrentPlan;
            const buttonLabel = (() => {
              if (current) return "Current plan";
              if (context.retryCurrentPlan) return "Retry payment";
              if (context.downgradeReadyForPayment) return "Checkout";
              if (context.isDowngrade) return "Schedule downgrade";
              return "Checkout";
            })();

            return (
              <article
                key={plan.planCode}
                className={`flex min-h-[410px] flex-col rounded-[1.6rem] border bg-surface p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-premium-hover ${
                  plan.highlighted ? "border-primary ring-4 ring-primary/10" : "border-border/70"
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
                  <Button
                    className="mt-3 w-full"
                    variant={current ? "outline" : "primary"}
                    disabled={current}
                    onClick={() => openPlanModal(plan.planCode)}
                  >
                    {buttonLabel}
                  </Button>
                </div>
              </article>
            );
          })}
        </section>

        <Modal
          open={modalOpen}
          title={
            selectedContext?.isDowngrade && !selectedContext?.downgradeReadyForPayment
              ? `Schedule ${selectedPlan?.name || "plan"}`
              : `Checkout for ${selectedPlan?.name || "plan"}`
          }
          description={
            requiresCheckout
              ? "Confirm the billing details Paystack should use for this payment."
              : "Confirm the plan change before it is scheduled."
          }
          onClose={closeModal}
          closeOnOverlay={!busy}
          footer={(
            <div className="flex justify-end gap-2">
              <Button variant="outline" disabled={busy} onClick={closeModal}>
                Cancel
              </Button>
              <Button disabled={modalActionDisabled} onClick={performPlanAction}>
                {modalActionLabel}
              </Button>
            </div>
          )}
        >
          <div className="space-y-5">
            <div className="rounded-2xl border border-border bg-surface-muted/30 p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-text">
                    {selectedPlan?.name || formatPlanName(targetPlanCode)}
                  </p>
                  <p className="mt-1 text-sm text-text-muted">{selectedPlan?.priceLabel}</p>
                </div>
                {selectedPlan?.highlighted ? <Badge variant="primary">Recommended</Badge> : null}
              </div>
            </div>

            {requiresCheckout ? (
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-1.5 block text-sm font-medium text-text-soft">
                    Billing interval
                  </span>
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
                </label>
                <Input
                  label="Billing email"
                  type="email"
                  value={billingEmail}
                  onChange={(event) => setBillingEmail(event.target.value)}
                  placeholder="admin@school.example"
                  error={
                    billingEmail && !validBillingEmail
                      ? "Enter a valid billing email address."
                      : undefined
                  }
                />
              </div>
            ) : null}

            {previewLoading ? <LoadingState label="Checking current usage..." /> : null}

            {selectedContext?.isDowngrade && !selectedContext.downgradeReadyForPayment && preview ? (
              preview.eligible ? (
                <Notice tone="info">
                  This plan can be scheduled for the end of the current billing period.
                </Notice>
              ) : (
                <div className="rounded-2xl border border-warning/30 bg-warning-soft p-4">
                  <p className="font-semibold text-amber-700">
                    Current usage exceeds this plan.
                  </p>
                  <div className="mt-3 grid gap-2">
                    {(preview.blockers || []).map((blocker) => (
                      <div
                        key={blocker.resource}
                        className="rounded-xl border border-warning/25 bg-surface px-3 py-2 text-sm text-text"
                      >
                        <strong className="capitalize">
                          {String(blocker.resource).replaceAll("_", " ")}
                        </strong>
                        : {blocker.used} active, limit {blocker.limit}, excess {blocker.excess}
                      </div>
                    ))}
                  </div>
                </div>
              )
            ) : null}

            {errorMessage ? <Notice tone="error">{errorMessage}</Notice> : null}
          </div>
        </Modal>
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
  return (
    <div className={`mt-5 rounded-2xl border px-4 py-3 text-sm font-medium ${classes}`}>
      {children}
    </div>
  );
}

export default SubscriptionOptionsPage;
