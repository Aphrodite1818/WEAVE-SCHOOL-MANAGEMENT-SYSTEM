import {
  CalendarClock,
  CreditCard,
  FileText,
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

const termDisplayName = (term) =>
  String(term?.display_name || term?.name || "Academic term")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

function BillingSignal({ icon: Icon, label, value }) {
  return (
    <div className="flex min-h-16 min-w-0 items-center gap-3 rounded-xl border border-white/20 bg-white/[0.12] px-3 py-3 text-white">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/15">
        <Icon className="h-4 w-4" />
      </span>
      <div className="min-w-0">
        <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-white/75">{label}</p>
        <p className="mt-1 truncate text-sm font-semibold leading-5 text-white">{value || "--"}</p>
      </div>
    </div>
  );
}

function BillingPage() {
  const {
    planCode,
    statusCode,
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
  const activeEntitlement = history.find((item) => item.status === "active") || null;
  const activeTerm = activeEntitlement
    ? termById.get(activeEntitlement.academic_term_id)
    : null;
  const activePlan = activeEntitlement?.plan_code || planCode || "free";
  const effectiveStatus = activeEntitlement?.status || statusCode || "active";
  const activeTermLabel = activeTerm
    ? termDisplayName(activeTerm)
    : activeEntitlement
      ? "Current academic term"
      : "No term activated";
  const provider = activeEntitlement?.provider || "Manual";

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
      description="Academic-term plan activation, capacity and one-time payment records."
    >
      <div className="space-y-5">
        {subscriptionErrors.currentSubscription ? (
          <Notice tone="warning">{subscriptionErrors.currentSubscription}</Notice>
        ) : null}
        {subscriptionErrors.entitlements ? (
          <Notice tone="warning">{subscriptionErrors.entitlements}</Notice>
        ) : null}
        {error ? <Notice tone="error">{error}</Notice> : null}

        {loading ? <LoadingState label="Loading billing history..." /> : null}

        {!loading ? (
          <>
            <section className="dashboard-grid xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
              <Card className="dashboard-welcome-blue border-0 p-5 shadow-premium sm:p-7">
                <div className="flex h-full flex-col justify-between gap-7">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-primary">
                        {String(effectiveStatus).replaceAll("_", " ")}
                      </span>
                      <span className="rounded-full border border-white/30 bg-white/15 px-3 py-1 text-xs font-bold text-white">
                        Per academic term
                      </span>
                    </div>
                    <p className="mt-6 text-[11px] font-bold uppercase tracking-[0.16em] text-white/75">Effective plan</p>
                    <h2 className="mt-2 text-3xl font-semibold text-white sm:text-4xl">{formatPlanName(activePlan)}</h2>
                    <p className="mt-3 max-w-2xl text-sm leading-6 text-white/85">
                      Each entitlement belongs to one academic term. Closing that term closes its plan entitlement; the next term is activated separately.
                    </p>
                  </div>
                  <div className="grid gap-3 md:grid-cols-3">
                    <BillingSignal icon={CalendarClock} label="Academic term" value={activeTermLabel} />
                    <BillingSignal icon={CreditCard} label="Provider" value={provider} />
                    <BillingSignal icon={ShieldCheck} label="Status" value={statusMeta.label} />
                  </div>
                </div>
              </Card>

              <Card className="p-5 sm:p-6">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-faint">Quick actions</p>
                <h2 className="mt-2 text-xl font-semibold text-text">Manage term billing</h2>
                <p className="mt-2 text-sm leading-6 text-text-muted">
                  Choose a plan for a draft or current term, review capacity, or refresh payment state after checkout.
                </p>
                <div className="mt-6 grid gap-3">
                  <Link to="/admin/billing/plans"><Button className="w-full">View term plans</Button></Link>
                  <Link to="/admin/usage"><Button variant="outline" className="w-full">View usage</Button></Link>
                  <Button variant="outline" className="w-full" onClick={refresh} disabled={refreshing}>
                    <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
                    Refresh billing
                  </Button>
                </div>
              </Card>
            </section>

            <section className="dashboard-grid xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
              <Card className="p-5 sm:p-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-faint">Current term record</p>
                    <h2 className="mt-2 text-lg font-semibold text-text">Entitlement details</h2>
                  </div>
                  <ShieldCheck className="h-5 w-5 text-text-muted" />
                </div>
                {activeEntitlement ? (
                  <div className="mt-5 grid gap-3 sm:grid-cols-2">
                    <Detail label="Plan" value={formatPlanName(activeEntitlement.plan_code)} />
                    <Detail label="Academic term" value={activeTermLabel} />
                    <Detail label="Activated" value={formatDateTime(activeEntitlement.activated_at)} />
                    <Detail label="Safety expiry" value={formatDateTime(activeEntitlement.safety_expires_at)} />
                    <Detail label="Provider" value={activeEntitlement.provider || "--"} />
                    <Detail label="Amount" value={money(activeEntitlement.amount, activeEntitlement.currency)} />
                  </div>
                ) : (
                  <div className="mt-5">
                    <EmptyState title="No active term entitlement" description="Open Academic Setup and activate a plan when the term is ready to open." />
                  </div>
                )}
              </Card>

              <Card className="p-5 sm:p-6">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-faint">Term lifecycle</p>
                    <h2 className="mt-2 text-lg font-semibold text-text">Plan history</h2>
                    <p className="mt-1 text-sm text-text-muted">Every Free or paid plan activation recorded for an academic term.</p>
                  </div>
                </div>
                {history.length ? (
                  <div className="mt-5 space-y-3">
                    {history.map((item) => {
                      const term = termById.get(item.academic_term_id);
                      return (
                        <div key={item.id} className="flex flex-col gap-3 rounded-2xl border border-border/70 bg-surface-muted/20 p-4 sm:flex-row sm:items-center sm:justify-between">
                          <div>
                            <p className="font-semibold text-text">{formatPlanName(item.plan_code)}</p>
                            <p className="mt-1 text-sm text-text-muted">{term ? termDisplayName(term) : "Academic term"} · {formatDateTime(item.activated_at)}</p>
                          </div>
                          <div className="text-left sm:text-right">
                            <Badge variant={statusVariant(item.status)}>{item.status}</Badge>
                            <p className="mt-1 text-sm font-semibold text-text">{money(item.amount, item.currency)}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="mt-5"><EmptyState title="No plan history yet" description="The first term activation will appear here." /></div>
                )}
              </Card>
            </section>

            <Card className="p-5 sm:p-6">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-faint">Transactions</p>
                  <h2 className="mt-2 text-lg font-semibold text-text">Payment history</h2>
                  <p className="mt-1 text-sm text-text-muted">Paystack checkout attempts for term-bound paid plans.</p>
                </div>
                <Button variant="outline" size="small" onClick={refresh} disabled={refreshing}>
                  <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} /> Refresh
                </Button>
              </div>
              {payments.length ? (
                <div className="mt-5 overflow-x-auto rounded-2xl border border-border">
                  <table className="w-full min-w-[720px] text-left text-sm">
                    <thead className="border-b border-border bg-surface-muted/40 text-xs uppercase tracking-wide text-text-muted">
                      <tr>
                        <th className="px-4 py-3">Date</th>
                        <th className="px-4 py-3">Reference</th>
                        <th className="px-4 py-3">Term</th>
                        <th className="px-4 py-3">Plan</th>
                        <th className="px-4 py-3">Status</th>
                        <th className="px-4 py-3 text-right">Amount</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {payments.map((record) => {
                        const term = termById.get(record.academic_term_id);
                        return (
                          <tr key={record.id}>
                            <td className="px-4 py-3 text-text">{formatDateTime(record.paid_at || record.created_at)}</td>
                            <td className="px-4 py-3 font-mono text-xs text-text-muted">{record.reference}</td>
                            <td className="px-4 py-3 text-text">{term ? termDisplayName(term) : "Academic term"}</td>
                            <td className="px-4 py-3 text-text">{formatPlanName(record.plan_code)}</td>
                            <td className="px-4 py-3"><Badge variant={statusVariant(record.status)}>{record.status}</Badge></td>
                            <td className="px-4 py-3 text-right font-semibold text-text">{money(record.amount, record.currency)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="mt-5"><EmptyState icon={FileText} title="No payment records yet" description="Paid term checkout attempts will appear here. Free activations remain in plan history." /></div>
              )}
            </Card>
          </>
        ) : null}
      </div>
    </DashboardLayout>
  );
}

function Detail({ label, value }) {
  return (
    <div className="rounded-[1.1rem] border border-border/70 bg-surface-muted/25 px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">{label}</p>
      <p className="mt-2 text-sm font-semibold leading-6 text-text">{value || "--"}</p>
    </div>
  );
}

function Notice({ children, tone = "info" }) {
  const toneClass = {
    info: "border-info/30 bg-info-soft text-info",
    warning: "border-warning/30 bg-warning-soft text-amber-700",
    error: "border-error/30 bg-error-soft text-error",
  }[tone];
  return (
    <div className={`rounded-2xl border px-4 py-3 text-sm font-medium ${toneClass}`}>
      {children}
    </div>
  );
}

export default BillingPage;
