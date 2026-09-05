import {
  CheckCircle2,
  ChevronLeft,
  CreditCard,
  ShieldCheck,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import PublicLayout from "../../components/layout/PublicLayout";
import LoadingState from "../../components/shared/LoadingState";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import {
  LANDING_PRICING_PLANS,
  formatLimitValue,
  formatPlanName,
} from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { academicService } from "../../services/academicService";
import { parseApiError } from "../../services/api";
import { subscriptionService } from "../../services/subscriptionService";
import SubscriptionOptionsPage from "./SubscriptionOptionsPage";

const isMobileViewport = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(max-width: 767px)").matches;
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

  return mobile ? (
    <MobileSubscriptionOptionsPage />
  ) : (
    <SubscriptionOptionsPage />
  );
}

function MobileSubscriptionOptionsPage() {
  const { refreshSubscriptionState, statusMeta } = useSubscription();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
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
  const [activePlanCode, setActivePlanCode] = useState(
    requestedPlanCode || "professional",
  );
  const checkoutLock = useRef(false);
  const [busyPlan, setBusyPlan] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [eligibilityWarning, setEligibilityWarning] = useState(null);

  const catalogueByCode = useMemo(
    () => new Map(LANDING_PRICING_PLANS.map((plan) => [plan.planCode, plan])),
    [],
  );
  const availableOptions = planOptions?.options || [];
  const paidOptions = availableOptions.filter(
    (option) => option.plan_code !== "free",
  );
  const freeOption = availableOptions.find(
    (option) => option.plan_code === "free",
  );
  const activeOption =
    paidOptions.find((option) => option.plan_code === activePlanCode) ||
    paidOptions[0];
  const activePlan = activeOption
    ? catalogueByCode.get(activeOption.plan_code) || {
        planCode: activeOption.plan_code,
        name: formatPlanName(activeOption.plan_code),
        description: "",
        features: [],
        limits: {},
      }
    : null;

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
      setActivePlanCode((current) => {
        if (requestedPlanCode) return requestedPlanCode;
        if (options?.current_plan && options.current_plan !== "free") {
          return options.current_plan;
        }
        return current;
      });
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
  }, [requestedTermId, requestedPlanCode]);

  useEffect(() => {
    load();
  }, [load]);

  const handlePlan = async (selectedOption = activeOption) => {
    const option = selectedOption;
    if (checkoutLock.current || busyPlan || !term || !option || option.transition === "current") {
      return;
    }
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
      checkoutLock.current = false;
      setError(
        parseApiError(actionError, "Could not change the term plan.").message,
      );
      setBusyPlan("");
    }
  };

  const actionLabel = activeOption
    ? getActionLabel(activeOption, planOptions?.term_status, busyPlan)
    : "Choose plan";

  return (
    <PublicLayout>
      <main
        data-mobile-billing-page="true"
        className="mx-auto flex min-h-full w-full max-w-lg flex-col px-5 pb-6 pt-4"
      >
        <header className="flex items-center justify-between">
          <Link
            to={returnPath}
            className="grid h-11 w-11 place-items-center rounded-full border border-border/70 bg-surface text-text shadow-sm"
            aria-label="Back to billing"
          >
            <ChevronLeft className="h-5 w-5" />
          </Link>
          <Badge variant={statusMeta.badgeVariant}>{statusMeta.label}</Badge>
        </header>

        <section className="pt-8">
          <h1 className="text-3xl font-semibold tracking-tight text-text">
            Choose this term's plan
          </h1>
          <p className="mt-3 max-w-sm text-sm leading-6 text-text-muted">
            The plan you activate here belongs only to the selected academic
            term.
          </p>
          {term || planOptions ? (
            <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-text-faint">
              {term ? termLabel(term) : "Academic term"} ·{" "}
              {String(planOptions?.term_status || "").replaceAll("_", " ")}
            </p>
          ) : null}
        </section>

        {error ? <Notice tone="error">{error}</Notice> : null}
        {loading ? (
          <div className="mt-8">
            <LoadingState label="Loading term plan options..." />
          </div>
        ) : null}

        {!loading && paidOptions.length ? (
          <>
            {freeOption ? (
              <div className="mt-8 flex items-center justify-between gap-4 rounded-2xl border border-border/70 bg-surface px-5 py-4">
                <div>
                  <p className="text-sm font-semibold text-text">
                    Continue on Free
                  </p>
                  <p className="mt-1 text-xs leading-5 text-text-muted">
                    No payment required.
                  </p>
                </div>
                {freeOption.transition === "current" ? (
                  <Badge variant="success">Current</Badge>
                ) : (
                  <Button
                    size="small"
                    variant="outline"
                    disabled={!freeOption.eligible || busyPlan === "free"}
                    onClick={() => handlePlan(freeOption)}
                  >
                    {busyPlan === "free" ? "Working..." : "Use Free"}
                  </Button>
                )}
              </div>
            ) : null}

            <section
              className="mt-6 grid grid-cols-2 gap-3"
              aria-label="Available plans"
            >
              {paidOptions.map((option) => {
                const plan = catalogueByCode.get(option.plan_code) || {
                  planCode: option.plan_code,
                  name: formatPlanName(option.plan_code),
                  bestFor: "",
                  priceLabel: "",
                };
                const selected = option.plan_code === activeOption?.plan_code;
                return (
                  <button
                    key={option.plan_code}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => setActivePlanCode(option.plan_code)}
                    className={`min-h-36 rounded-2xl border px-4 py-4 text-left transition ${
                      selected
                        ? "border-primary/60 bg-primary-subtle/40 ring-1 ring-primary/10"
                        : "border-border/70 bg-surface"
                    }`}
                  >
                    <span className="flex h-full flex-col">
                      <span className="min-w-0">
                        <span className="block text-base font-semibold text-text">
                          {plan.name}
                        </span>
                        <span className="mt-2 block text-xs leading-5 text-text-muted">
                          {option.transition === "upgrade"
                            ? "Only the remaining difference is due."
                            : option.transition === "downgrade"
                              ? "Existing payments remain as term credit."
                              : plan.bestFor}
                        </span>
                      </span>
                      <span className="mt-auto pt-4">
                        <span className="block text-base font-semibold text-text">
                          {option.transition === "select"
                            ? moneyFromKobo(option.list_price_kobo)
                            : moneyFromKobo(option.amount_due_kobo)}
                        </span>
                        <span className="mt-2 block min-h-5">
                          {option.transition === "current" ? (
                            <Badge variant="success">Current</Badge>
                          ) : requestedPlanCode === option.plan_code ? (
                            <Badge variant="info">Chosen</Badge>
                          ) : null}
                        </span>
                      </span>
                    </span>
                  </button>
                );
              })}
            </section>

            {activePlan && activeOption ? (
              <>
                <section className="mt-10 border-t border-border/70 pt-8">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-sm font-semibold text-text">
                        Everything included
                      </p>
                      <p className="mt-1 text-sm leading-6 text-text-muted">
                        {activePlan.description}
                      </p>
                    </div>
                    {activePlan.highlighted ? (
                      <Badge variant="primary">Recommended</Badge>
                    ) : null}
                  </div>
                  {(activePlan.features || []).length ? (
                    <ul className="mt-5 space-y-4">
                      {activePlan.features.map((feature) => (
                        <li
                          key={feature}
                          className="flex items-start gap-3 text-sm text-text"
                        >
                          <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                          <span>{feature}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-4 text-sm leading-6 text-text-muted">
                      Backend catalogue details are not available yet for this
                      plan, so only the verified term price and eligibility are
                      shown.
                    </p>
                  )}
                </section>

                <section className="mt-8 rounded-2xl border border-border/70 bg-surface p-4">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="h-5 w-5 text-primary" />
                    <h2 className="text-sm font-semibold text-text">
                      Plan capacity
                    </h2>
                  </div>
                  <div className="mt-4 divide-y divide-border/70">
                    {Object.keys(activePlan.limits || {}).length ? (
                      Object.entries(activePlan.limits).map(
                        ([resource, limit]) => (
                          <PlanLimit
                            key={resource}
                            label={resourceLabel(resource)}
                            value={formatLimitValue(limit)}
                          />
                        ),
                      )
                    ) : (
                      <PlanLimit label="Current usage" value="Fits this plan" />
                    )}
                  </div>
                </section>

                <div
                  data-mobile-billing-action="true"
                  className="mt-auto bg-background/95 pt-6"
                >
                  <Button
                    className="min-h-14 w-full rounded-full text-base"
                    disabled={
                      activeOption.transition === "current" ||
                      Boolean(busyPlan)
                    }
                    onClick={() => handlePlan()}
                  >
                    {Number(activeOption.amount_due_kobo || 0) > 0 ? (
                      <CreditCard className="h-5 w-5" />
                    ) : null}
                    {actionLabel}
                  </Button>
                  <p className="mt-3 text-center text-xs leading-5 text-text-muted">
                    One activation per academic term. Paid checkout is handled
                    securely by Paystack.
                  </p>
                </div>
              </>
            ) : null}
          </>
        ) : null}
      </main>
      <Modal
        open={Boolean(eligibilityWarning)}
        title={`${eligibilityWarning?.planName || "This plan"} is not available yet`}
        description="Current school usage exceeds this plan's capacity."
        onClose={() => setEligibilityWarning(null)}
        placement="bottom"
        footer={
          <Button className="w-full" onClick={() => setEligibilityWarning(null)}>
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
    </PublicLayout>
  );
}

function getActionLabel(option, termStatus, busyPlan) {
  const planName = formatPlanName(option.plan_code);
  if (busyPlan === option.plan_code) return "Working...";
  if (!option.eligible) return `Choose ${planName}`;
  if (option.transition === "current") return "Current term plan";
  if (
    String(termStatus || "").toLowerCase() === "draft" &&
    option.plan_code === "free"
  ) {
    return "Continue with Free";
  }
  if (option.transition === "select") return `Choose ${planName}`;
  if (option.transition === "upgrade") {
    return Number(option.amount_due_kobo || 0) > 0
      ? `Upgrade for ${moneyFromKobo(option.amount_due_kobo)}`
      : `Switch to ${planName}`;
  }
  return `Downgrade to ${planName}`;
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
    <div
      className={`mt-5 rounded-2xl border px-4 py-3 text-sm font-medium ${classes}`}
    >
      {children}
    </div>
  );
}

export default ResponsiveSubscriptionOptionsPage;
