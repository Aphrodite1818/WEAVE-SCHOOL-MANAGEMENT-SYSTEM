import { CheckCircle2, ChevronLeft } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import PublicLayout from "../../components/layout/PublicLayout";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
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
  const { planCode } = useSubscription();
  const [searchParams] = useSearchParams();
  const checkoutTermId = searchParams.get("term");
  const paidPlans = useMemo(
    () => LANDING_PRICING_PLANS.filter((plan) => PAID_PLAN_CODES.has(plan.planCode)),
    [],
  );
  const [activePlanCode, setActivePlanCode] = useState(
    PAID_PLAN_CODES.has(planCode) ? planCode : "professional",
  );
  const [busyPlan, setBusyPlan] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (PAID_PLAN_CODES.has(planCode)) setActivePlanCode(planCode);
  }, [planCode]);

  const activePlan =
    paidPlans.find((plan) => plan.planCode === activePlanCode) || paidPlans[0];
  const isCurrent = activePlan?.planCode === planCode;
  const hasCurrentPaidPlan = PAID_PLAN_CODES.has(planCode);
  const lowerOrEqualMidTerm =
    hasCurrentPaidPlan &&
    (PLAN_RANK[activePlan?.planCode] ?? 0) <= (PLAN_RANK[planCode] ?? 0);

  const upgrade = async () => {
    if (!activePlan || isCurrent || lowerOrEqualMidTerm) return;
    setBusyPlan(activePlan.planCode);
    setError("");
    try {
      const checkout = await subscriptionService.initializePaidCurrentTermCheckout({
        plan_code: activePlan.planCode,
        academic_term_id: checkoutTermId || undefined,
      });
      window.location.assign(checkout.authorization_url);
    } catch (checkoutError) {
      setError(
        parseApiError(
          checkoutError,
          "Could not start term-plan checkout.",
        ).message,
      );
      setBusyPlan("");
    }
  };

  return (
    <PublicLayout>
      <main
        data-mobile-billing-page="true"
        className="mx-auto min-h-screen w-full max-w-lg px-4 py-5"
      >
        <Link
          to="/admin/billing"
          className="inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-text-soft"
        >
          <ChevronLeft className="h-4 w-4" />
          Back to billing
        </Link>

        <section className="mt-3 rounded-3xl border border-border/70 bg-surface p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">
            Current term plans
          </p>
          <h1 className="mt-2 text-2xl font-semibold text-text">
            Choose the capacity your school needs
          </h1>
          <p className="mt-2 text-sm leading-6 text-text-muted">
            Paid access applies to one academic term. During an active paid term
            you can only move upward; lower plans become selectable for the next
            term.
          </p>
        </section>

        {error ? (
          <div className="mt-4 rounded-2xl border border-error/30 bg-error-soft p-4 text-sm text-error">
            {error}
          </div>
        ) : null}

        <div className="mt-4 grid grid-cols-3 gap-2">
          {paidPlans.map((plan) => (
            <Button
              key={plan.planCode}
              type="button"
              size="small"
              variant={activePlan?.planCode === plan.planCode ? "primary" : "outline"}
              onClick={() => setActivePlanCode(plan.planCode)}
            >
              {plan.name}
            </Button>
          ))}
        </div>

        {activePlan ? (
          <Card className="mt-4 p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-xl font-semibold text-text">{activePlan.name}</h2>
                <p className="mt-1 text-sm text-text-muted">{activePlan.bestFor}</p>
              </div>
              {isCurrent ? <Badge variant="success">Current</Badge> : null}
            </div>

            <p className="mt-5 text-2xl font-semibold text-text">
              {activePlan.priceLabel}
            </p>
            <p className="mt-2 text-sm leading-6 text-text-muted">
              {activePlan.description}
            </p>

            <section className="mt-6">
              <h3 className="text-sm font-semibold text-text">Everything included</h3>
              <div className="mt-3 space-y-3">
                {(activePlan.features || []).map((feature) => (
                  <div key={feature} className="flex gap-2 text-sm text-text-soft">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                    <span>{feature}</span>
                  </div>
                ))}
              </div>
            </section>

            <section className="mt-6 border-t border-border/70 pt-5">
              <h3 className="text-sm font-semibold text-text">Plan capacity</h3>
              <div className="mt-3 grid gap-2">
                {Object.entries(activePlan.limits || {}).map(([resource, limit]) => (
                  <div
                    key={resource}
                    className="flex items-center justify-between rounded-xl bg-surface-muted px-3 py-2 text-sm"
                  >
                    <span className="capitalize text-text-muted">
                      {resource.replaceAll("_", " ")}
                    </span>
                    <span className="font-semibold text-text">
                      {formatLimitValue(limit)}
                    </span>
                  </div>
                ))}
              </div>
            </section>

            <Button
              data-mobile-billing-action="true"
              className="mt-6 w-full"
              onClick={upgrade}
              disabled={
                isCurrent ||
                lowerOrEqualMidTerm ||
                busyPlan === activePlan.planCode
              }
            >
              {busyPlan === activePlan.planCode
                ? "Starting checkout..."
                : isCurrent
                  ? "Current term plan"
                  : lowerOrEqualMidTerm
                    ? "Available next term"
                    : `Upgrade to ${formatPlanName(activePlan.planCode)}`}
            </Button>
          </Card>
        ) : null}
      </main>
    </PublicLayout>
  );
}

export default ResponsiveSubscriptionOptionsPage;
