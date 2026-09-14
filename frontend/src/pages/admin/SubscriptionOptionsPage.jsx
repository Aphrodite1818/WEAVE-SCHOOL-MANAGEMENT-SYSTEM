import { CheckCircle2, CreditCard } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Modal from "../../components/ui/Modal";
import { savePendingUpgradeTour } from "../../features/guides/workspaceTourState";
import {
  LANDING_PRICING_PLANS,
  formatPlanName,
} from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { academicService } from "../../services/academicService";
import { parseApiError } from "../../services/api";
import { subscriptionService } from "../../services/subscriptionService";

const asItems = (value) => (Array.isArray(value) ? value : value?.items || []);

const moneyFromKobo = (value) =>
  new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency: "NGN",
    maximumFractionDigits: 0,
  }).format(Number(value || 0) / 100);

const termLabel = (term) =>
  String(term?.display_name || term?.name || "Academic term")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

const resourceLabel = (value) =>
  String(value || "resource")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

function SubscriptionOptionsPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { refreshSubscriptionState } = useSubscription();
  const requestedTermId = searchParams.get("term");
  const requestedPlanCode = searchParams.get("plan");
  const intent = searchParams.get("intent");
  const origin =
    searchParams.get("origin") ||
    (intent === "open-term" ? "academic-terms" : "billing");
  const defaultReturn =
    origin === "guided-onboarding"
      ? "/admin/getting-started"
      : origin === "academic-terms"
        ? "/admin/academic/terms"
        : "/admin/billing";
  const returnPath = subscriptionService.safeReturnPath(
    searchParams.get("return"),
    defaultReturn,
  );
  const postPaymentAction = intent === "open-term" ? "open_term" : "none";

  const [term, setTerm] = useState(null);
  const [planOptions, setPlanOptions] = useState(null);
  const [planHistory, setPlanHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const checkoutLock = useRef(false);
  const [busyPlan, setBusyPlan] = useState("");
  const [error, setError] = useState("");
  const [eligibilityWarning, setEligibilityWarning] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const termsResponse = await academicService.listTerms({ limit: 100 });
      const terms = asItems(termsResponse);
      const selectedTerm = requestedTermId
        ? terms.find((item) => String(item.id) === String(requestedTermId))
        : terms.find(
            (item) =>
              item.is_current &&
              String(item.status || "").toLowerCase() === "open",
          );

      if (!selectedTerm) {
        throw new Error(
          requestedTermId
            ? "The selected academic term could not be found."
            : "There is no open academic term to manage. Choose a plan when opening the next term.",
        );
      }

      const [options, history] = await Promise.all([
        subscriptionService.getTermPlanOptions(selectedTerm.id),
        subscriptionService.getTermPlanHistory(),
      ]);
      setTerm(selectedTerm);
      setPlanOptions(options);
      setPlanHistory(Array.isArray(history) ? history : []);
    } catch (loadError) {
      setError(
        parseApiError(
          loadError,
          "Could not load plan options for this academic term.",
        ).message,
      );
    } finally {
      setLoading(false);
    }
  }, [requestedTermId]);

  useEffect(() => {
    load();
  }, [load]);

  const catalogueByCode = useMemo(
    () => new Map(LANDING_PRICING_PLANS.map((plan) => [plan.planCode, plan])),
    [],
  );
  const paidOptions = (planOptions?.options || []).filter(
    (option) => option.plan_code !== "free",
  );
  const freeOption = (planOptions?.options || []).find(
    (option) => option.plan_code === "free",
  );

  const handlePlan = async (option) => {
    if (
      checkoutLock.current ||
      busyPlan ||
      !term ||
      !option ||
      option.transition === "current"
    )
      return;
    if (!option.eligible) {
      setEligibilityWarning({
        planName: formatPlanName(option.plan_code),
        blockers: option.blockers || [],
      });
      return;
    }
    checkoutLock.current = true;
    setBusyPlan(option.plan_code);
    setError("");

    try {
      const upgradeTour = subscriptionService.upgradeTourForPlan({
        targetPlan: option.plan_code,
        fromPlan: planOptions?.current_plan || "free",
        history: planHistory,
      });
      if (option.requires_payment || Number(option.amount_due_kobo || 0) > 0) {
        const checkout = await subscriptionService.initializeTermCheckout({
          academic_term_id: term.id,
          plan_code: option.plan_code,
        });
        subscriptionService.saveTermPaymentIntent({
          academicTermId: term.id,
          reference: checkout.reference,
          origin,
          returnPath,
          postPaymentAction,
          upgradeTour,
        });
        window.location.assign(
          subscriptionService.checkoutRedirectUrl(checkout),
        );
        return;
      }

      if (
        String(planOptions?.term_status || "").toLowerCase() === "draft" &&
        option.plan_code === "free"
      ) {
        await subscriptionService.activateFreeTerm(term.id);
        if (postPaymentAction === "open_term") {
          await academicService.openTerm(term.id);
        }
      } else {
        await subscriptionService.changeTermPlan({
          academicTermId: term.id,
          targetPlan: option.plan_code,
        });
      }

      await refreshSubscriptionState({ silent: true });
      if (upgradeTour) {
        savePendingUpgradeTour({ ...upgradeTour, dedicated: true });
      }
      navigate(returnPath, { replace: true });
    } catch (actionError) {
      checkoutLock.current = false;
      setError(
        parseApiError(actionError, "Could not change the term plan.").message,
      );
      setBusyPlan("");
    }
  };

  return (
    <DashboardLayout
      role="admin"
      title="Term Plan"
      description="Choose or change the plan for one operational academic term."
    >
      <div className="mx-auto w-full max-w-6xl space-y-4">
        <div className="flex flex-col gap-3 border-b border-border/70 pb-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-semibold text-text">
                {term ? termLabel(term) : "Term plan"}
              </h2>
              {planOptions?.current_plan ? (
                <Badge variant="success">
                  {formatPlanName(planOptions.current_plan)} ?{" "}
                  {String(planOptions.term_status).toLowerCase() === "draft"
                    ? "Purchased for this term"
                    : "Plan for this term"}
                </Badge>
              ) : null}
            </div>
            <p className="mt-1 text-sm capitalize text-text-muted">
              {String(planOptions?.term_status || "").replaceAll("_", " ")}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {freeOption?.eligible && freeOption.transition !== "current" ? (
              <Button
                size="small"
                variant="ghost"
                disabled={busyPlan === "free"}
                onClick={() => handlePlan(freeOption)}
              >
                {busyPlan === "free" ? "Working..." : "Continue with Free"}
              </Button>
            ) : null}
            <Link to={returnPath}>
              <Button size="small" variant="outline">
                Back
              </Button>
            </Link>
          </div>
        </div>

        {error ? (
          <div
            role="alert"
            className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error"
          >
            {error}
          </div>
        ) : null}

        {loading ? <LoadingState label="Loading term plan options..." /> : null}

        {!loading && planOptions ? (
          <>
            <section className="grid items-stretch gap-6 xl:grid-cols-3">
              {paidOptions.map((option) => {
                const plan = catalogueByCode.get(option.plan_code) || {
                  planCode: option.plan_code,
                  name: formatPlanName(option.plan_code),
                  bestFor: "",
                  description: "",
                  features: [],
                };
                const isCurrent = option.transition === "current";
                const isBusy = busyPlan === option.plan_code;
                const selectedAtRegistration =
                  requestedPlanCode === option.plan_code;
                const actionLabel = getActionLabel(
                  option,
                  planOptions.term_status,
                );
                const displayAmount =
                  option.transition === "select"
                    ? option.list_price_kobo
                    : option.amount_due_kobo;

                return (
                  <Card
                    key={option.plan_code}
                    className={`payment-plan-card flex flex-col border-border/70 p-0 shadow-soft-card ${
                      selectedAtRegistration || isCurrent
                        ? "payment-plan-card-selected brand-strip-card ring-2 ring-primary/15"
                        : ""
                    }`}
                  >
                    <div className="flex flex-1 flex-col p-6">
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <h3 className="text-2xl font-semibold tracking-tight text-text">
                            {plan.name}
                          </h3>
                          <p className="mt-2 text-sm text-text-muted">
                            {plan.bestFor}
                          </p>
                        </div>
                        <div className="flex flex-wrap justify-end gap-2">
                          {isCurrent ? (
                            <Badge variant="success">Current</Badge>
                          ) : null}
                          {selectedAtRegistration ? (
                            <Badge variant="info">Signup preference</Badge>
                          ) : null}
                        </div>
                      </div>

                      <p className="mt-6 min-h-[5.25rem] text-sm leading-7 text-text-muted">
                        {plan.description}
                      </p>

                      <div className="mt-7">
                        <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                          {option.transition === "upgrade"
                            ? "Additional amount due"
                            : option.transition === "downgrade"
                              ? "Additional payment"
                              : "Term price"}
                        </p>
                        <strong className="mt-2 block text-4xl font-semibold tracking-tight text-text">
                          {moneyFromKobo(displayAmount)}
                        </strong>
                        <p className="mt-2 text-xs leading-5 text-text-muted">
                          {option.transition === "upgrade" ? (
                            <>
                              {moneyFromKobo(option.paid_to_date_kobo)} already
                              paid toward this term.
                            </>
                          ) : option.transition === "downgrade" ? (
                            "No automatic refund. Existing payments remain as term credit."
                          ) : (
                            "One activation for the selected academic term."
                          )}
                        </p>
                      </div>

                      <Button
                        className="mt-7 min-h-12 w-full rounded-xl"
                        disabled={isCurrent || isBusy}
                        onClick={() => handlePlan(option)}
                      >
                        {Number(option.amount_due_kobo || 0) > 0 ? (
                          <CreditCard className="h-4 w-4" />
                        ) : null}
                        {isBusy ? "Working..." : actionLabel}
                      </Button>

                      <div className="mt-8 border-t border-border/70 pt-7">
                        <p className="text-sm font-semibold text-text">
                          What's included
                        </p>
                      </div>

                      {(plan.features || []).length ? (
                        <ul className="mt-5 grid gap-y-4 text-sm text-text-soft">
                          {plan.features.slice(0, 6).map((feature) => (
                            <li key={feature} className="flex gap-2">
                              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                              <span className="leading-5">{feature}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="mt-5 text-sm leading-6 text-text-muted">
                          Feature details will appear when the live catalogue is
                          available.
                        </p>
                      )}
                    </div>
                  </Card>
                );
              })}
            </section>
          </>
        ) : null}
      </div>
      <Modal
        open={Boolean(eligibilityWarning)}
        title={`${eligibilityWarning?.planName || "This plan"} is not available yet`}
        description="Current school usage exceeds this plan's capacity."
        onClose={() => setEligibilityWarning(null)}
        footer={
          <Button
            className="w-full sm:w-auto"
            onClick={() => setEligibilityWarning(null)}
          >
            Got it
          </Button>
        }
      >
        <p className="text-sm leading-6 text-text-muted">
          Reduce the following active usage before choosing this plan. Checkout
          has not started.
        </p>
        <dl className="mt-5 divide-y divide-border/70 rounded-xl border border-border/70 px-4">
          {(eligibilityWarning?.blockers || []).map((blocker) => (
            <div
              key={blocker.resource}
              className="flex items-center justify-between gap-4 py-3 text-sm"
            >
              <dt className="text-text-muted">
                {resourceLabel(blocker.resource)}
              </dt>
              <dd className="font-semibold text-text">
                {Number(blocker.used).toLocaleString()} active · limit{" "}
                {Number(blocker.limit).toLocaleString()}
              </dd>
            </div>
          ))}
        </dl>
      </Modal>
    </DashboardLayout>
  );
}

function getActionLabel(option, termStatus) {
  const planName = formatPlanName(option.plan_code);
  if (!option.eligible) return `Choose ${planName}`;
  if (option.transition === "current") return "Current term plan";
  if (termStatus === "draft" && option.plan_code === "free") {
    return "Continue with Free";
  }
  if (option.transition === "select") {
    return `Choose ${planName}`;
  }
  if (option.transition === "upgrade") {
    return Number(option.amount_due_kobo || 0) > 0
      ? `Upgrade for ${moneyFromKobo(option.amount_due_kobo)}`
      : `Switch to ${planName}`;
  }
  return `Downgrade to ${planName}`;
}

export default SubscriptionOptionsPage;
