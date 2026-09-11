import { termEntitlementLabel } from "../../features/subscriptions/termEntitlementPresentation";
import {
  CalendarClock,
  CreditCard,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import DashboardLayout from "../../components/layout/DashboardLayout";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import {
  formatDateTime,
  formatPlanName,
} from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";
import { subscriptionService } from "../../services/subscriptionService";

const PAYMENT_LIMIT = 50;
const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

const money = (amount, currency = "NGN") => {
  const numericAmount = Number(amount);
  if (!Number.isFinite(numericAmount)) return "--";
  return new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(numericAmount);
};

const statusVariant = (value) => {
  const status = String(value || "").toLowerCase();
  if (["active", "success"].includes(status)) return "success";
  if (["failed", "expired"].includes(status)) return "error";
  if (status === "pending") return "warning";
  return "default";
};

const paymentNeedsReconciliation = (payment) =>
  payment?.status === "success" && payment?.reconciliation_required === true;

const termDisplayName = (term) =>
  String(term?.display_name || term?.name || "Academic term")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

function BillingPage() {
  const {
    entitlements,
    planCode,
    statusMeta,
    errors: subscriptionErrors,
    refreshSubscriptionState,
  } = useSubscription();
  const [history, setHistory] = useState([]);
  const [payments, setPayments] = useState([]);
  const [terms, setTerms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const loadBilling = useCallback(async ({ silent = false } = {}) => {
    if (silent) setRefreshing(true);
    else setLoading(true);
    setError("");
    try {
      const [termRows, paymentRows, termResponse] = await Promise.all([
        subscriptionService.getTermPlanHistory(),
        subscriptionService.getPaymentHistory({ limit: PAYMENT_LIMIT }),
        academicService.listTerms({ limit: 100 }),
      ]);
      setHistory(termRows || []);
      setPayments(paymentRows?.items || []);
      setTerms(asItems(termResponse));
    } catch (loadError) {
      setError(getErrorMessage(loadError, "Could not load billing history."));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadBilling();
  }, [loadBilling]);

  const termById = useMemo(
    () => new Map(terms.map((term) => [term.id, term])),
    [terms],
  );
  const currentTerm =
    terms.find(
      (term) =>
        term.is_current &&
        String(term.status || "").toLowerCase() === "open",
    ) || null;
  const currentEntitlement = currentTerm
    ? history.find(
        (item) =>
          item.status === "active" &&
          String(item.academic_term_id) === String(currentTerm.id),
      ) || null
    : null;
  const effectivePlan = entitlements?.plan || planCode || "free";
  const paidThisTerm = currentTerm
    ? payments
        .filter(
          (payment) =>
            payment.status === "success" &&
            !paymentNeedsReconciliation(payment) &&
            String(payment.academic_term_id) === String(currentTerm.id),
        )
        .reduce((sum, payment) => sum + Number(payment.amount || 0), 0)
    : 0;
  const currentTermLabel = currentTerm
    ? termDisplayName(currentTerm)
    : "No operational term";

  const refresh = async () => {
    await Promise.all([
      loadBilling({ silent: true }),
      refreshSubscriptionState({ silent: true }),
    ]);
  };

  return (
    <DashboardLayout
      role="admin"
      title="Billing"
      description="Current-term plan management and payment history."
    >
      <div className="space-y-5">
        {subscriptionErrors.currentSubscription ? (
          <Notice>{subscriptionErrors.currentSubscription}</Notice>
        ) : null}
        {subscriptionErrors.entitlements ? (
          <Notice>{subscriptionErrors.entitlements}</Notice>
        ) : null}
        {error ? <Notice tone="error">{error}</Notice> : null}

        {loading ? <LoadingState label="Loading billing..." /> : null}

        {!loading ? (
          <>
            <section className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
              <Card className="brand-strip-card dashboard-welcome-blue border-0 p-5 shadow-premium sm:p-7">
                <div className="flex h-full flex-col justify-between gap-7">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-primary">
                        {statusMeta.label}
                      </span>
                      <span className="rounded-full border border-white/30 bg-white/15 px-3 py-1 text-xs font-bold text-white">
                        {currentTerm ? "Current academic term" : "Permanent baseline"}
                      </span>
                    </div>
                    <p className="mt-6 text-[11px] font-bold uppercase tracking-[0.16em] text-white/75">
                      Effective plan
                    </p>
                    <h2 className="mt-2 text-3xl font-semibold text-white sm:text-4xl">
                      {formatPlanName(effectivePlan)}
                    </h2>
                    <p className="mt-3 max-w-2xl text-sm leading-6 text-white/85">
                      Free is always available as Weave&apos;s permanent baseline.
                      Purchased plans belong to their selected academic term and
                      close with that term.
                    </p>
                  </div>
                  <div className="grid gap-3 md:grid-cols-3">
                    <Signal
                      icon={CalendarClock}
                      label="Academic term"
                      value={currentTermLabel}
                    />
                    <Signal
                      icon={CreditCard}
                      label="Paid this term"
                      value={money(paidThisTerm)}
                    />
                    <Signal
                      icon={ShieldCheck}
                      label="Term plan"
                      value={formatPlanName(effectivePlan)}
                    />
                  </div>
                </div>
              </Card>

              <Card className="p-5 sm:p-6">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-faint">
                  Plan management
                </p>
                <h2 className="mt-2 text-xl font-semibold text-text">
                  {currentTerm ? "Manage the current term" : "No term to manage"}
                </h2>
                <p className="mt-2 text-sm leading-6 text-text-muted">
                  {currentTerm
                    ? "Upgrade by paying only the remaining difference, or move to a lower plan when current operational usage fits it."
                    : "Choose Free or a paid plan when you open the next academic term from Academic Terms."}
                </p>
                <div className="mt-6 grid gap-3">
                  {currentTerm ? (
                    <Link
                      to={`/admin/billing/plans?term=${encodeURIComponent(
                        currentTerm.id,
                      )}&origin=billing&return=${encodeURIComponent(
                        "/admin/billing",
                      )}`}
                    >
                      <Button className="w-full">Manage current term plan</Button>
                    </Link>
                  ) : (
                    <Link to="/admin/academic/terms">
                      <Button className="w-full">Open Academic Terms</Button>
                    </Link>
                  )}
                  <Link to="/admin/usage">
                    <Button variant="outline" className="w-full">
                      View usage
                    </Button>
                  </Link>
                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={refresh}
                    disabled={refreshing}
                  >
                    <RefreshCw
                      className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
                    />
                    Refresh billing
                  </Button>
                </div>
              </Card>
            </section>

            <section className="grid gap-5 xl:grid-cols-2">
              <Card className="p-5 sm:p-6">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-faint">
                  Current term
                </p>
                <h2 className="mt-2 text-lg font-semibold text-text">
                  Plan record
                </h2>
                {currentTerm ? (
                  <div className="mt-5 divide-y divide-border overflow-hidden rounded-xl border border-border">
                    <Detail label="Term" value={currentTermLabel} />
                    <Detail
                      label="Plan"
                      value={formatPlanName(effectivePlan)}
                    />
                    <Detail
                      label="Paid this term"
                      value={money(paidThisTerm)}
                    />
                    <Detail
                      label="Activated"
                      value={
                        currentEntitlement
                          ? formatDateTime(currentEntitlement.activated_at)
                          : "Free baseline"
                      }
                    />
                  </div>
                ) : (
                  <div className="mt-5">
                    <EmptyState
                      title="No operational term"
                      description="A plan purchased for a draft term is scheduled. Feature access follows the current open term; review Academic Terms for readiness blockers."
                    />
                  </div>
                )}
              </Card>

              <Card className="p-5 sm:p-6">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-faint">
                  Term history
                </p>
                <h2 className="mt-2 text-lg font-semibold text-text">
                  Plan transitions
                </h2>
                <p className="mt-1 text-sm text-text-muted">
                  Historical Free and paid entitlements remain available for
                  audit without affecting the current term.
                </p>
                {history.length ? (
                  <div className="mt-5 divide-y divide-border overflow-hidden rounded-xl border border-border">
                    {history.map((item) => {
                      const term = termById.get(item.academic_term_id);
                      return (
                        <div
                          key={item.id}
                          className="flex items-center justify-between gap-4 px-4 py-3"
                        >
                          <div>
                            <p className="text-sm font-semibold text-text">
                              {formatPlanName(item.plan_code)}
                            </p>
                            <p className="mt-1 text-xs text-text-muted">
                              {term ? termDisplayName(term) : "Academic term"} ·{" "}
                              {formatDateTime(item.activated_at)}
                            </p>
                          </div>
                          <Badge variant={statusVariant(item.status)}>
                            {termEntitlementLabel(item, term)}
                          </Badge>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="mt-5">
                    <EmptyState
                      title="No term plan history"
                      description="Plan selections appear here after an academic term is opened."
                    />
                  </div>
                )}
              </Card>
            </section>

            <Card className="p-5 sm:p-6">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-faint">
                Transactions
              </p>
              <h2 className="mt-2 text-lg font-semibold text-text">
                Payment history
              </h2>
              <p className="mt-1 text-sm text-text-muted">
                Initial paid activations and upgrade differences processed by
                Paystack. A late payment that needs reconciliation is recorded
                here but does not count toward the term plan automatically.
              </p>

              {payments.length ? (
                <div className="mt-5 overflow-x-auto rounded-xl border border-border">
                  <table className="min-w-full text-left text-sm">
                    <thead className="bg-surface-muted/40 text-xs uppercase tracking-wide text-text-muted">
                      <tr>
                        <th className="px-4 py-3">Term</th>
                        <th className="px-4 py-3">Plan</th>
                        <th className="px-4 py-3">Amount</th>
                        <th className="px-4 py-3">Status</th>
                        <th className="px-4 py-3">Date</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {payments.map((payment) => {
                        const term = termById.get(payment.academic_term_id);
                        const needsReconciliation =
                          paymentNeedsReconciliation(payment);
                        return (
                          <tr key={payment.id}>
                            <td className="px-4 py-3 font-medium text-text">
                              {term ? termDisplayName(term) : "Academic term"}
                            </td>
                            <td className="px-4 py-3">
                              {formatPlanName(payment.plan_code)}
                            </td>
                            <td className="px-4 py-3 font-semibold">
                              {money(payment.amount, payment.currency)}
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex flex-col items-start gap-1">
                                <Badge
                                  variant={
                                    needsReconciliation
                                      ? "warning"
                                      : statusVariant(payment.status)
                                  }
                                >
                                  {needsReconciliation
                                    ? "Needs review"
                                    : payment.status}
                                </Badge>
                                {needsReconciliation ? (
                                  <span className="max-w-xs text-xs leading-4 text-text-muted">
                                    Paid after checkout expiry. Do not retry this
                                    payment; contact support for reconciliation.
                                  </span>
                                ) : null}
                              </div>
                            </td>
                            <td className="px-4 py-3 text-text-muted">
                              {formatDateTime(
                                payment.paid_at || payment.created_at,
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="mt-5">
                  <EmptyState
                    title="No paid transactions"
                    description="Free usage never creates a payment transaction."
                  />
                </div>
              )}
            </Card>
          </>
        ) : null}
      </div>
    </DashboardLayout>
  );
}

function Signal({ icon: Icon, label, value }) {
  return (
    <div className="flex min-h-16 min-w-0 items-center gap-3 rounded-xl border border-white/20 bg-white/[0.12] px-3 py-3 text-white">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/15">
        <Icon className="h-4 w-4" />
      </span>
      <div className="min-w-0">
        <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-white/75">
          {label}
        </p>
        <p className="mt-1 truncate text-sm font-semibold leading-5 text-white">
          {value || "--"}
        </p>
      </div>
    </div>
  );
}

function Detail({ label, value }) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 px-4 py-3">
      <span className="text-sm text-text-muted">{label}</span>
      <strong className="text-right text-sm text-text">{value || "--"}</strong>
    </div>
  );
}

function Notice({ children, tone = "warning" }) {
  const classes =
    tone === "error"
      ? "border-error/30 bg-error-soft text-error"
      : "border-warning/30 bg-warning-soft text-amber-800";
  return (
    <div className={`rounded-2xl border px-4 py-3 text-sm font-medium ${classes}`}>
      {children}
    </div>
  );
}

export default BillingPage;
