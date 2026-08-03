import {
  CheckCircle2,
  ChevronLeft,
  CreditCard,
  Loader2,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import WeaveIcon from "../../components/brand/WeaveIcon";
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
import SubscriptionOptionsPage from "./SubscriptionOptionsPage";

const PLAN_RANK = {
  free_trial: 0,
  plus: 1,
  professional: 2,
  enterprise: 3,
};

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const isMobileViewport = () =>
  typeof window !== "undefined"
  && window.matchMedia("(max-width: 767px)").matches;

function ResponsiveSubscriptionOptionsPage() {
  const [mobile, setMobile] = useState(isMobileViewport);

  useEffect(() => {
    const query = window.matchMedia("(max-width: 767px)");
    const syncViewport = () => setMobile(query.matches);

    syncViewport();
    query.addEventListener?.("change", syncViewport);
    query.addListener?.(syncViewport);

    return () => {
      query.removeEventListener?.("change", syncViewport);
      query.removeListener?.(syncViewport);
    };
  }, []);

  return mobile ? <MobileSubscriptionOptionsPage /> : <SubscriptionOptionsPage />;
}

function MobileSubscriptionOptionsPage() {
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
  const [activePricingPlan, setActivePricingPlan] = useState("professional");
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

  useEffect(() => {
    if (paidPlans.some((plan) => plan.planCode === planCode)) {
      setActivePricingPlan(planCode);
    }
  }, [paidPlans, planCode]);

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

  const selectedPlan = paidPlans.find(
    (plan) => plan.planCode === activePricingPlan,
  ) || paidPlans[0];
  const targetPlan = paidPlans.find(
    (plan) => plan.planCode === targetPlanCode,
  ) || null;
  const selectedPlanContext = getPlanContext(selectedPlan?.planCode);
  const targetContext = targetPlanCode ? getPlanContext(targetPlanCode) : null;
  const requiresCheckout = Boolean(
    targetContext
      && (!targetContext.isDowngrade || targetContext.downgradeReadyForPayment),
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
      setErrorMessage(
        getSubscriptionCheckoutErrorMessage(parsed.message) || parsed.message,
      );
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
    if (!targetContext) return;
    if (targetContext.isDowngrade && !targetContext.downgradeReadyForPayment) {
      scheduleDowngrade();
      return;
    }
    startCheckout();
  };

  const selectedActionLabel = (() => {
    if (selectedPlanContext.samePlan && !selectedPlanContext.retryCurrentPlan) {
      return "Current plan";
    }
    if (selectedPlanContext.retryCurrentPlan) return "Retry payment";
    if (selectedPlanContext.downgradeReadyForPayment) {
      return `Checkout for ${selectedPlan.name}`;
    }
    if (selectedPlanContext.isDowngrade) {
      return `Schedule ${selectedPlan.name}`;
    }
    return `Upgrade to ${selectedPlan.name}`;
  })();

  const modalActionLabel = (() => {
    if (busy) return "Working...";
    if (!targetPlanCode || !targetContext) return "Continue";
    if (targetContext.downgradeReadyForPayment) {
      return `Checkout for ${formatPlanName(targetPlanCode)}`;
    }
    if (targetContext.isDowngrade) {
      return `Schedule ${formatPlanName(targetPlanCode)}`;
    }
    if (targetContext.retryCurrentPlan) return "Retry payment";
    return "Continue to Paystack";
  })();

  const modalActionDisabled =
    busy
    || !targetContext
    || (requiresCheckout && !validBillingEmail)
    || (targetContext?.isDowngrade
      && !targetContext.downgradeReadyForPayment
      && (previewLoading || !preview?.eligible));

  if (isLoading && !currentSubscription && !entitlements) {
    return (
      <PublicLayout>
        <div className="mx-auto min-h-screen max-w-lg px-4 py-8">
          <LoadingState label="Loading subscription plans..." />
        </div>
      </PublicLayout>
    );
  }

  return (
    <PublicLayout>
      <main
        data-mobile-billing-page="true"
        className="mx-auto flex min-h-full w-full max-w-lg flex-col px-5 pb-6 pt-4"
      >
        <header className="flex items-center justify-between">
          <Link
            to="/admin/billing"
            className="grid h-11 w-11 place-items-center rounded-full border border-border/70 bg-surface text-text shadow-sm"
            aria-label="Back to billing"
          >
            <ChevronLeft className="h-5 w-5" />
          </Link>
          <Badge variant={statusMeta.badgeVariant}>{statusMeta.label}</Badge>
        </header>

        <section className="pt-7 text-center">
          <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-primary/10 text-primary">
            <WeaveIcon className="h-11 w-11" decorative />
          </div>
          <h1 className="mt-5 text-3xl font-semibold tracking-tight text-text">
            Choose your Weave plan
          </h1>
          <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-text-muted">
            Select the school capacity and features that fit your current workflow.
          </p>
        </section>

        {errors.currentSubscription ? (
          <Notice tone="warning">{errors.currentSubscription}</Notice>
        ) : null}
        {errors.entitlements ? <Notice tone="warning">{errors.entitlements}</Notice> : null}
        {errorMessage && !modalOpen ? <Notice tone="error">{errorMessage}</Notice> : null}
        {successMessage ? <Notice tone="success">{successMessage}</Notice> : null}

        {planChange ? (
          <Notice tone={planChange.status === "blocked" ? "warning" : "info"}>
            {formatPlanName(planChange.target_plan_code)} plan change: {String(
              planChange.status,
            ).replaceAll("_", " ")}.
          </Notice>
        ) : null}

        <section className="mt-7 grid grid-cols-2 gap-3" aria-label="Available plans">
          {paidPlans.map((plan, index) => {
            const selected = plan.planCode === selectedPlan.planCode;
            return (
              <button
                key={plan.planCode}
                type="button"
                aria-pressed={selected}
                onClick={() => setActivePricingPlan(plan.planCode)}
                className={`rounded-2xl border px-4 py-4 text-left transition ${
                  index === paidPlans.length - 1 ? "col-span-2" : ""
                } ${
                  selected
                    ? "border-primary bg-primary-subtle/70 ring-1 ring-primary/20"
                    : "border-border/70 bg-surface"
                }`}
              >
                <span className="block text-sm font-semibold text-text">{plan.name}</span>
                <span className="mt-1 block text-base font-bold text-text">
                  {plan.priceLabel}
                </span>
                <span className="mt-1 block text-xs leading-5 text-text-muted">
                  {plan.bestFor}
                </span>
              </button>
            );
          })}
        </section>

        <section className="mt-8">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-text">Everything included</p>
              <p className="mt-1 text-sm leading-6 text-text-muted">
                {selectedPlan.description}
              </p>
            </div>
            {selectedPlan.highlighted ? <Badge variant="primary">Recommended</Badge> : null}
          </div>

          <ul className="mt-5 space-y-4">
            {(selectedPlan.features || []).map((feature) => (
              <li key={feature} className="flex items-start gap-3 text-sm text-text">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                <span>{feature}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="mt-8 rounded-2xl border border-border/70 bg-surface p-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-primary" />
            <h2 className="text-sm font-semibold text-text">Plan capacity</h2>
          </div>
          <div className="mt-4 divide-y divide-border/70">
            <PlanLimit label="Students" value={formatLimitValue(selectedPlan.limits?.students)} />
            <PlanLimit label="Teachers" value={formatLimitValue(selectedPlan.limits?.teachers)} />
            <PlanLimit label="Classes" value={formatLimitValue(selectedPlan.limits?.classes)} />
          </div>
        </section>

        <div
          data-mobile-billing-action="true"
          className="mt-auto bg-background/95 pt-6 backdrop-blur-xl"
        >
          <Button
            className="min-h-14 w-full rounded-full text-base"
            disabled={
              selectedPlanContext.samePlan && !selectedPlanContext.retryCurrentPlan
            }
            onClick={() => openPlanModal(selectedPlan.planCode)}
          >
            <CreditCard className="h-5 w-5" />
            {selectedActionLabel}
          </Button>
          <p className="mt-3 text-center text-xs leading-5 text-text-muted">
            Monthly billing through Paystack. Plan changes follow your current billing-period rules.
          </p>
        </div>

        <Modal
          open={modalOpen}
          title={
            targetContext?.isDowngrade && !targetContext?.downgradeReadyForPayment
              ? `Schedule ${targetPlan?.name || "plan"}`
              : `Checkout for ${targetPlan?.name || "plan"}`
          }
          description={
            requiresCheckout
              ? "Confirm the billing details Paystack should use for this payment."
              : "Confirm the plan change before it is scheduled."
          }
          onClose={closeModal}
          closeOnOverlay={!busy}
          footer={(
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button variant="outline" disabled={busy} onClick={closeModal}>
                Cancel
              </Button>
              <Button disabled={modalActionDisabled} onClick={performPlanAction}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                {modalActionLabel}
              </Button>
            </div>
          )}
        >
          <div className="space-y-5">
            <div className="rounded-2xl border border-border bg-surface-muted/30 p-4">
              <p className="text-sm font-semibold text-text">
                {targetPlan?.name || formatPlanName(targetPlanCode)}
              </p>
              <p className="mt-1 text-sm text-text-muted">{targetPlan?.priceLabel}</p>
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

            {targetContext?.isDowngrade
            && !targetContext.downgradeReadyForPayment
            && preview ? (
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
    <div className="flex items-center justify-between gap-3 py-3 text-sm">
      <span className="text-text-muted">{label}</span>
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

export default ResponsiveSubscriptionOptionsPage;
