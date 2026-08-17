import { CheckCircle2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import PublicLayout from "../../components/layout/PublicLayout";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import {
  LANDING_PRICING_PLANS,
  formatPlanName,
} from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { academicService } from "../../services/academicService";
import { parseApiError } from "../../services/api";
import { subscriptionService } from "../../services/subscriptionService";

const PLAN_RANK = {
  free: 0,
  free_trial: 0,
  plus: 1,
  professional: 2,
  enterprise: 3,
};

const isPaidPlan = (planCode) =>
  ["plus", "professional", "enterprise"].includes(planCode);

const asItems = (value) => Array.isArray(value) ? value : value?.items || [];
const termLabel = (term) =>
  String(term?.display_name || term?.name || "Academic term")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
const isCheckoutEligibleTerm = (term) => ["draft", "open"].includes(String(term?.status || "").toLowerCase());

function SubscriptionOptionsPage() {
  const { planCode } = useSubscription();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [busyPlan, setBusyPlan] = useState("");
  const [error, setError] = useState("");
  const [terms, setTerms] = useState([]);
  const [selectedTermId, setSelectedTermId] = useState("");
  const checkoutTermId = searchParams.get("term");
  const shouldOpenTermAfterPayment =
    checkoutTermId && searchParams.get("intent") === "open-term";
  const requestedPlanCode = searchParams.get("plan");
  const availablePlans = useMemo(
    () => LANDING_PRICING_PLANS.filter(
      (plan) => isPaidPlan(plan.planCode) || (checkoutTermId && plan.planCode === "free"),
    ),
    [checkoutTermId],
  );
  const checkoutTerms = useMemo(
    () => terms.filter(isCheckoutEligibleTerm),
    [terms],
  );
  const effectiveCheckoutTermId = checkoutTermId || selectedTermId;

  useEffect(() => {
    if (checkoutTermId) return;
    let active = true;
    academicService
      .listTerms({ limit: 100 })
      .then((response) => {
        if (!active) return;
        const rows = asItems(response).filter(isCheckoutEligibleTerm);
        setTerms(rows);
        setSelectedTermId((current) =>
          current ||
          rows.find((term) => term.is_current && term.status === "open")?.id ||
          rows.find((term) => term.status === "draft")?.id ||
          rows[0]?.id ||
          "",
        );
      })
      .catch((loadError) => {
        if (active) {
          setError(parseApiError(loadError, "Could not load academic terms for checkout.").message);
        }
      });
    return () => {
      active = false;
    };
  }, [checkoutTermId]);

  const upgrade = async (targetPlan) => {
    setBusyPlan(targetPlan);
    setError("");
    try {
      if (!effectiveCheckoutTermId) {
        setError("Select a draft or open academic term before starting checkout.");
        setBusyPlan("");
        return;
      }
      if (targetPlan === "free" && effectiveCheckoutTermId) {
        await subscriptionService.activateFreeTerm(effectiveCheckoutTermId);
        navigate("/admin/getting-started", { replace: true });
        return;
      }
      const checkout = await subscriptionService.initializeTermCheckout({
        plan_code: targetPlan,
        academic_term_id: effectiveCheckoutTermId,
      });
      if (shouldOpenTermAfterPayment) {
        subscriptionService.saveTermPaymentOpenIntent({
          academicTermId: effectiveCheckoutTermId,
          reference: checkout.reference,
        });
      }
      window.location.assign(subscriptionService.checkoutRedirectUrl(checkout));
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

  const currentRank = PLAN_RANK[planCode] ?? 0;
  const hasCurrentPaidPlan = isPaidPlan(planCode);

  return (
    <PublicLayout>
      <main className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-primary">
              Term plans
            </p>
            <h1 className="mt-1 text-3xl font-semibold text-text">
              {checkoutTermId
                ? "Choose a plan for this academic term"
                : "Upgrade the current academic term"}
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-text-muted">
              {checkoutTermId
                ? "This checkout is tied to the exact academic term selected in Academic Setup."
                : "During an active paid term, you can only move to a higher paid plan. Lower plans become available when the next term is activated."}
            </p>
          </div>
          <Link
            to="/admin/billing"
            className="btn-base min-h-10 border border-border/80 bg-surface px-4 py-2 text-sm text-text-soft"
          >
            Back to billing
          </Link>
        </div>

        {error ? (
          <div className="mt-5 rounded-2xl border border-error/30 bg-error-soft p-4 text-sm text-error">
            {error}
          </div>
        ) : null}

        {!checkoutTermId ? (
          <Card className="mt-5 p-4">
            <label className="block text-sm font-semibold text-text">
              Academic term
              <select
                className="input-base mt-2"
                value={selectedTermId}
                onChange={(event) => setSelectedTermId(event.target.value)}
              >
                {checkoutTerms.map((term) => (
                  <option key={term.id} value={term.id}>
                    {termLabel(term)} - {String(term.status || "").replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </label>
            {!checkoutTerms.length ? (
              <p className="mt-2 text-sm text-error">
                Create or open an academic term before starting checkout.
              </p>
            ) : null}
          </Card>
        ) : null}

        <section className="mt-7 grid gap-5 lg:grid-cols-3">
          {availablePlans.map((plan) => {
            const current = !checkoutTermId && plan.planCode === planCode;
            const lowerOrEqualMidTerm =
              !checkoutTermId &&
              hasCurrentPaidPlan &&
              (PLAN_RANK[plan.planCode] ?? 0) <= currentRank;
            const disabled =
              current || lowerOrEqualMidTerm || !effectiveCheckoutTermId || busyPlan === plan.planCode;

            return (
              <Card
                key={plan.planCode}
                className="flex min-h-[28rem] flex-col p-5 sm:p-6"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xl font-semibold text-text">{plan.name}</p>
                    <p className="mt-1 text-sm text-text-muted">{plan.bestFor}</p>
                  </div>
                  {requestedPlanCode === plan.planCode ? (
                    <Badge variant="info">Chosen at registration</Badge>
                  ) : current ? (
                    <Badge variant="success">Current</Badge>
                  ) : null}
                </div>
                <p className="mt-5 text-2xl font-semibold text-text">
                  {plan.priceLabel}
                </p>
                <p className="mt-3 text-sm leading-6 text-text-muted">
                  {plan.description}
                </p>
                <div className="mt-5 space-y-3">
                  {(plan.features || []).slice(0, 8).map((feature) => (
                    <div key={feature} className="flex gap-2 text-sm text-text-soft">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                      {feature}
                    </div>
                  ))}
                </div>
                <Button
                  className="mt-auto"
                  onClick={() => upgrade(plan.planCode)}
                  disabled={disabled}
                >
                  {busyPlan === plan.planCode
                    ? "Starting checkout..."
                    : current
                      ? "Current term plan"
                      : lowerOrEqualMidTerm
                        ? "Available next term"
                    : checkoutTermId && plan.planCode === "free"
                      ? "Activate Free for this term"
                      : checkoutTermId
                      ? `Choose ${formatPlanName(plan.planCode)}`
                          : `Upgrade to ${formatPlanName(plan.planCode)}`}
                </Button>
              </Card>
            );
          })}
        </section>
      </main>
    </PublicLayout>
  );
}

export default SubscriptionOptionsPage;
