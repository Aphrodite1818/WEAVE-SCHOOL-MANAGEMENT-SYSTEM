import { AlertTriangle, CheckCircle2, CreditCard } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
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
  const [loading, setLoading] = useState(true);
  const [busyPlan, setBusyPlan] = useState("");
  const [error, setError] = useState("");

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

      const options = await subscriptionService.getTermPlanOptions(
        selectedTerm.id,
      );
      setTerm(selectedTerm);
      setPlanOptions(options);
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

  const handlePlan = async (option) => {
    if (!term || !option?.eligible || option.transition === "current") return;
    setBusyPlan(option.plan_code);
    setError("");

    try {
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
      navigate(returnPath, { replace: true });
    } catch (actionError) {
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
      <div className="mx-auto w-full max-w-6xl space-y-5">
        <div className="flex flex-col gap-3 rounded-2xl border border-border/70 bg-surface px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Academic term
            </p>
            <h2 className="mt-1 text-xl font-semibold text-text">
              {term ? termLabel(term) : "Term plan"}
            </h2>
            {planOptions ? (
              <p className="mt-1 text-sm text-text-muted">
                {String(planOptions.term_status || "").replaceAll("_", " ")} ·{" "}
                {planOptions.current_plan
                  ? `${formatPlanName(planOptions.current_plan)} currently active`
                  : "No plan selected yet"}
              </p>
            ) : null}
          </div>
          <Link to={returnPath}>
            <Button variant="outline">Back</Button>
          </Link>
        </div>

        {error ? (
          <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
            {error}
          </div>
        ) : null}

        {loading ? <LoadingState label="Loading term plan options..." /> : null}

        {!loading && planOptions ? (
          <>
            <Card className="p-5 sm:p-6">
              <div className="grid gap-3 sm:grid-cols-3">
                <Summary
                  label="Current plan"
                  value={
                    planOptions.current_plan
                      ? formatPlanName(planOptions.current_plan)
                      : "Not selected"
                  }
                />
                <Summary
                  label="Paid this term"
                  value={moneyFromKobo(planOptions.paid_to_date_kobo)}
                />
                <Summary
                  label="Plan changes"
                  value={
                    planOptions.term_status === "draft"
                      ? "Select for opening"
                      : "Current term only"
                  }
                />
              </div>
            </Card>

            <section className="grid gap-4 lg:grid-cols-2">
              {(planOptions.options || []).map((option) => {
                const plan = catalogueByCode.get(option.plan_code) || {
                  planCode: option.plan_code,
                  name: formatPlanName(option.plan_code),
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

                return (
                  <Card
                    key={option.plan_code}
                    className={`flex min-h-[25rem] flex-col p-5 sm:p-6 ${
                      selectedAtRegistration ? "ring-2 ring-primary/20" : ""
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-xl font-semibold text-text">
                            {plan.name}
                          </h3>
                          {isCurrent ? (
                            <Badge variant="success">Current</Badge>
                          ) : null}
                          {selectedAtRegistration ? (
                            <Badge variant="info">Signup preference</Badge>
                          ) : null}
                        </div>
                        <p className="mt-2 text-sm leading-6 text-text-muted">
                          {plan.description}
                        </p>
                      </div>
                    </div>

                    <div className="mt-5 rounded-xl border border-border/70 bg-surface-muted/25 px-4 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm text-text-muted">
                          {option.transition === "upgrade"
                            ? "Additional amount due"
                            : option.transition === "downgrade"
                              ? "Additional payment"
                              : "Term price"}
                        </span>
                        <strong className="text-lg text-text">
                          {option.transition === "select"
                            ? moneyFromKobo(option.list_price_kobo)
                            : moneyFromKobo(option.amount_due_kobo)}
                        </strong>
                      </div>
                      {option.transition === "upgrade" ? (
                        <p className="mt-1 text-xs text-text-muted">
                          {moneyFromKobo(option.paid_to_date_kobo)} already paid
                          toward this term.
                        </p>
                      ) : option.transition === "downgrade" ? (
                        <p className="mt-1 text-xs text-text-muted">
                          No automatic refund. Existing term payments remain as
                          credit.
                        </p>
                      ) : null}
                    </div>

                    {option.blockers?.length ? (
                      <div className="mt-5 rounded-xl border border-warning/30 bg-warning-soft px-4 py-3">
                        <div className="flex gap-2">
                          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                          <div>
                            <p className="text-sm font-semibold">
                              This school does not currently fit {plan.name}.
                            </p>
                            <ul className="mt-2 space-y-1 text-xs">
                              {option.blockers.map((blocker) => (
                                <li key={blocker.resource}>
                                  {resourceLabel(blocker.resource)}:{" "}
                                  {Number(blocker.used).toLocaleString()} active ·
                                  limit {Number(blocker.limit).toLocaleString()}
                                </li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="mt-5 flex items-start gap-2 text-sm text-text-soft">
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                        Current operational usage fits this plan.
                      </div>
                    )}

                    {(plan.features || []).length ? (
                      <ul className="mt-5 space-y-2 text-sm text-text-soft">
                        {plan.features.slice(0, 5).map((feature) => (
                          <li key={feature} className="flex gap-2">
                            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                            {feature}
                          </li>
                        ))}
                      </ul>
                    ) : null}

                    <Button
                      className="mt-auto"
                      variant={
                        option.plan_code === "free" && !isCurrent
                          ? "outline"
                          : "primary"
                      }
                      disabled={!option.eligible || isCurrent || isBusy}
                      onClick={() => handlePlan(option)}
                    >
                      {Number(option.amount_due_kobo || 0) > 0 ? (
                        <CreditCard className="h-4 w-4" />
                      ) : null}
                      {isBusy ? "Working..." : actionLabel}
                    </Button>
                  </Card>
                );
              })}
            </section>
          </>
        ) : null}
      </div>
    </DashboardLayout>
  );
}

function Summary({ label, value }) {
  return (
    <div className="rounded-xl border border-border/70 bg-surface-muted/20 px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
        {label}
      </p>
      <p className="mt-1 text-sm font-semibold text-text">{value}</p>
    </div>
  );
}

function getActionLabel(option, termStatus) {
  const planName = formatPlanName(option.plan_code);
  if (!option.eligible) return "Unavailable";
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
