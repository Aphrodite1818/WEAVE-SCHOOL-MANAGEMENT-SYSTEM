import {
  CheckCircle2,
  ChevronLeft,
  CreditCard,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import WeaveIcon from "../../components/brand/WeaveIcon";
import PublicLayout from "../../components/layout/PublicLayout";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import {
  LANDING_PRICING_PLANS,
  formatLimitValue,
  formatPlanName,
} from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { parseApiError } from "../../services/api";
import { subscriptionService } from "../../services/subscriptionService";
import SubscriptionOptionsPage from "./SubscriptionOptionsPage";

const PAID_PLAN_CODES = new Set(["plus", "professional", "enterprise"]);
const PLAN_RANK = {
  free: 0,
  free_trial: 0,
  plus: 1,
  professional: 2,
  enterprise: 3,
};

const isMobileViewport = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(max-width: 767px)").matches;

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
  const { planCode, statusMeta } = useSubscription();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const checkoutTermId = searchParams.get("term");
  const shouldOpenTermAfterPayment = checkoutTermId && searchParams.get("intent") === "open-term";
  const requestedPlanCode = searchParams.get("plan");
  const availablePlans = useMemo(
    () => LANDING_PRICING_PLANS.filter(
      (plan) => PAID_PLAN_CODES.has(plan.planCode) || (checkoutTermId && plan.planCode === "free"),
    ),
    [checkoutTermId],
  );
  const [activePlanCode, setActivePlanCode] = useState(
    requestedPlanCode || (PAID_PLAN_CODES.has(planCode) ? planCode : "professional"),
  );
  const [busyPlan, setBusyPlan] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (availablePlans.some((plan) => plan.planCode === requestedPlanCode)) {
      setActivePlanCode(requestedPlanCode);
    } else if (PAID_PLAN_CODES.has(planCode)) {
      setActivePlanCode(planCode);
    }
  }, [availablePlans, planCode, requestedPlanCode]);

  const activePlan =
    availablePlans.find((plan) => plan.planCode === activePlanCode) || availablePlans[0];
  const isCurrent = !checkoutTermId && activePlan?.planCode === planCode;
  const hasCurrentPaidPlan = PAID_PLAN_CODES.has(planCode);
  const lowerOrEqualMidTerm =
    !checkoutTermId &&
    hasCurrentPaidPlan &&
    (PLAN_RANK[activePlan?.planCode] ?? 0) <= (PLAN_RANK[planCode] ?? 0);

  const activatePlan = async () => {
    if (!activePlan || isCurrent || lowerOrEqualMidTerm) return;
    setBusyPlan(activePlan.planCode);
    setError("");
    try {
      if (activePlan.planCode === "free" && checkoutTermId) {
        await subscriptionService.activateFreeTerm(checkoutTermId);
        navigate("/admin/getting-started", { replace: true });
        return;
      }
      const checkout = await subscriptionService.initializePaidCurrentTermCheckout({
        plan_code: activePlan.planCode,
        academic_term_id: checkoutTermId || undefined,
      });
      if (shouldOpenTermAfterPayment) {
        subscriptionService.saveTermPaymentOpenIntent({
          academicTermId: checkoutTermId,
          reference: checkout.reference,
        });
      }
      window.location.assign(checkout.authorization_url);
    } catch (checkoutError) {
      setError(
        parseApiError(checkoutError, "Could not start term-plan checkout.").message,
      );
      setBusyPlan("");
    }
  };

  const actionLabel = (() => {
    if (busyPlan === activePlan?.planCode) return "Starting...";
    if (isCurrent) return "Current term plan";
    if (lowerOrEqualMidTerm) return "Available next term";
    if (checkoutTermId && activePlan?.planCode === "free") return "Activate Free for this term";
    if (checkoutTermId) return `Choose ${formatPlanName(activePlan?.planCode)}`;
    return `Upgrade to ${formatPlanName(activePlan?.planCode)}`;
  })();

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
            {checkoutTermId ? "Choose this term's plan" : "Choose your Weave plan"}
          </h1>
          <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-text-muted">
            {checkoutTermId
              ? "The plan you activate here belongs only to the academic term you selected."
              : "Select the school capacity and features that fit the current academic term."}
          </p>
        </section>

        {error ? <Notice tone="error">{error}</Notice> : null}

        <section className="mt-7 grid grid-cols-2 gap-3" aria-label="Available plans">
          {availablePlans.map((plan, index) => {
            const selected = plan.planCode === activePlan?.planCode;
            const spanLastCard = availablePlans.length % 2 === 1 && index === availablePlans.length - 1;
            return (
              <button
                key={plan.planCode}
                type="button"
                aria-pressed={selected}
                onClick={() => setActivePlanCode(plan.planCode)}
                className={`rounded-2xl border px-4 py-4 text-left transition ${
                  spanLastCard ? "col-span-2" : ""
                } ${
                  selected
                    ? "border-primary bg-primary-subtle/70 ring-1 ring-primary/20"
                    : "border-border/70 bg-surface"
                }`}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-text">{plan.name}</span>
                  {requestedPlanCode === plan.planCode ? (
                    <Badge variant="info">Chosen</Badge>
                  ) : null}
                </span>
                <span className="mt-2 block text-base font-bold text-text">{plan.priceLabel}</span>
                <span className="mt-1 block text-xs leading-5 text-text-muted">{plan.bestFor}</span>
              </button>
            );
          })}
        </section>

        {activePlan ? (
          <>
            <section className="mt-8">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-text">Everything included</p>
                  <p className="mt-1 text-sm leading-6 text-text-muted">{activePlan.description}</p>
                </div>
                {activePlan.highlighted ? <Badge variant="primary">Recommended</Badge> : null}
              </div>
              <ul className="mt-5 space-y-4">
                {(activePlan.features || []).map((feature) => (
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
                {Object.entries(activePlan.limits || {}).map(([resource, limit]) => (
                  <PlanLimit
                    key={resource}
                    label={resource.replaceAll("_", " ")}
                    value={formatLimitValue(limit)}
                  />
                ))}
              </div>
            </section>

            <div data-mobile-billing-action="true" className="mt-auto bg-background/95 pt-6">
              <Button
                className="min-h-14 w-full rounded-full text-base"
                disabled={isCurrent || lowerOrEqualMidTerm || busyPlan === activePlan.planCode}
                onClick={activatePlan}
              >
                <CreditCard className="h-5 w-5" />
                {actionLabel}
              </Button>
              <p className="mt-3 text-center text-xs leading-5 text-text-muted">
                One activation per academic term. Paid checkout is handled securely by Paystack.
              </p>
            </div>
          </>
        ) : null}
      </main>
    </PublicLayout>
  );
}

function PlanLimit({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-3 py-3 text-sm">
      <span className="capitalize text-text-muted">{label}</span>
      <strong className="text-text">{value}</strong>
    </div>
  );
}

function Notice({ children, tone = "info" }) {
  const classes = {
    info: "border-info/30 bg-info-soft text-info",
    error: "border-error/30 bg-error-soft text-error",
  }[tone];
  return (
    <div className={`mt-5 rounded-2xl border px-4 py-3 text-sm font-medium ${classes}`}>
      {children}
    </div>
  );
}

export default ResponsiveSubscriptionOptionsPage;
