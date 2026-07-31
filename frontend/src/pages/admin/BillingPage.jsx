import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  Ban,
  CalendarClock,
  CreditCard,
  FileText,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Modal from "../../components/ui/Modal";
import {
  formatBillingInterval,
  formatDateTime,
  formatPlanName,
} from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { getErrorMessage } from "../../services/api";
import { subscriptionService } from "../../services/subscriptionService";

const PAGE_SIZE = 20;

const DETAIL_FIELDS = [
  { key: "plan_code", label: "Plan" },
  { key: "status", label: "Subscription status" },
  { key: "provider", label: "Provider" },
  { key: "billing_interval", label: "Billing interval" },
  { key: "current_period_start", label: "Current period start" },
  { key: "current_period_end", label: "Current period end" },
  { key: "trial_ends_at", label: "Trial ends at" },
  { key: "grace_ends_at", label: "Grace ends at" },
  { key: "next_payment_at", label: "Next payment at" },
  { key: "cancel_at_period_end", label: "Cancel at period end" },
];

function formatPaymentAmount(record) {
  const amount = Number(record?.amount);
  if (!Number.isFinite(amount)) return "--";
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: record?.currency || "NGN",
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${record?.currency || "NGN"} ${amount.toLocaleString()}`;
  }
}

function paymentStatusVariant(value) {
  const status = String(value || "").toLowerCase();
  if (status === "success") return "success";
  if (status === "failed") return "error";
  if (status === "pending") return "warning";
  return "default";
}

function getDaysUntil(value) {
  if (!value) return null;
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return null;
  return Math.ceil((timestamp - Date.now()) / 86400000);
}

function getLifecycleLabel(dateValue, status) {
  const days = getDaysUntil(dateValue);
  if (days === null) return "Date pending";
  const normalized = String(status || "").toLowerCase();
  if (days < 0) return `Ended ${Math.abs(days)} day${Math.abs(days) === 1 ? "" : "s"} ago`;
  if (days === 0) return normalized === "non_renewing" ? "Ends today" : "Renews today";
  return `${normalized === "non_renewing" ? "Ends" : "Renews"} in ${days} day${days === 1 ? "" : "s"}`;
}

function detailValue(fieldKey, subscription, statusMeta) {
  if (fieldKey === "status") return statusMeta.label;
  if (fieldKey === "plan_code") return formatPlanName(subscription?.plan_code);
  if (fieldKey === "billing_interval") return formatBillingInterval(subscription?.billing_interval);
  if (fieldKey === "cancel_at_period_end") return subscription?.cancel_at_period_end ? "Yes" : "No";
  if ([
    "current_period_start",
    "current_period_end",
    "trial_ends_at",
    "grace_ends_at",
    "next_payment_at",
  ].includes(fieldKey)) {
    return formatDateTime(subscription?.[fieldKey]);
  }
  return subscription?.[fieldKey] || "--";
}

function BillingSignal({ icon: Icon, label, value }) {
  return (
    <div className="flex min-h-16 min-w-0 items-center gap-3 rounded-xl border border-white/20 bg-white/[0.12] px-3 py-3 text-white">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/15">
        <Icon className="h-4 w-4" />
      </span>
      <div className="min-w-0">
        <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-white/65">{label}</p>
        <p className="mt-1 text-sm font-semibold leading-5 text-white">{value || "--"}</p>
      </div>
    </div>
  );
}

function BillingPage() {
  const {
    currentSubscription,
    entitlements,
    planCode,
    statusMeta,
    isAttentionRequired,
    isLoading,
    errors,
    refreshSubscriptionState,
  } = useSubscription();

  const [payments, setPayments] = useState({ items: [], total: 0, skip: 0, limit: PAGE_SIZE });
  const [paymentPage, setPaymentPage] = useState(1);
  const [paymentLoading, setPaymentLoading] = useState(true);
  const [paymentError, setPaymentError] = useState("");
  const [planChange, setPlanChange] = useState(null);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelError, setCancelError] = useState("");
  const [isCancelling, setIsCancelling] = useState(false);

  const renewalDate = currentSubscription?.current_period_end || entitlements?.current_period_end;
  const provider = currentSubscription?.provider || entitlements?.provider || "Paystack";
  const rawStatus = currentSubscription?.status || entitlements?.subscription_status || statusMeta?.value;
  const normalizedStatus = String(rawStatus || "").toLowerCase();
  const isNonRenewing = normalizedStatus === "non_renewing" || Boolean(currentSubscription?.cancel_at_period_end);
  const canCancel = normalizedStatus === "active" && !isNonRenewing;
  const lifecycleLabel = getLifecycleLabel(renewalDate, normalizedStatus);
  const totalPages = Math.max(1, Math.ceil((payments.total || 0) / PAGE_SIZE));

  const loadBillingRecords = async ({ silent = false } = {}) => {
    if (!silent) setPaymentLoading(true);
    setPaymentError("");
    try {
      const [history, currentChange] = await Promise.all([
        subscriptionService.getPaymentHistory({
          skip: (paymentPage - 1) * PAGE_SIZE,
          limit: PAGE_SIZE,
        }),
        subscriptionService.getCurrentPlanChange(),
      ]);
      setPayments(history || { items: [], total: 0, skip: 0, limit: PAGE_SIZE });
      setPlanChange(currentChange || null);
    } catch (error) {
      setPaymentError(getErrorMessage(error, "Could not load billing records."));
    } finally {
      setPaymentLoading(false);
    }
  };

  useEffect(() => {
    loadBillingRecords();
  }, [paymentPage]);

  const cancelSubscription = async () => {
    setCancelError("");
    setIsCancelling(true);
    try {
      await subscriptionService.cancelCurrentSubscription({
        confirmation: "CANCEL_SUBSCRIPTION",
        reason: cancelReason.trim() || undefined,
      });
      await Promise.all([
        refreshSubscriptionState({ silent: true }),
        loadBillingRecords({ silent: true }),
      ]);
      setCancelOpen(false);
      setCancelReason("");
    } catch (error) {
      setCancelError(getErrorMessage(error, "Could not cancel automatic renewal."));
    } finally {
      setIsCancelling(false);
    }
  };

  const planChangeMessage = useMemo(() => {
    if (!planChange) return null;
    if (planChange.status === "scheduled") {
      return `${formatPlanName(planChange.target_plan_code)} is scheduled for ${formatDateTime(planChange.effective_at)}. New resource creation already follows the target plan limits.`;
    }
    if (planChange.status === "awaiting_payment") {
      return `${formatPlanName(planChange.target_plan_code)} is ready. Complete checkout to activate the lower plan.`;
    }
    if (planChange.status === "blocked") {
      return `The move to ${formatPlanName(planChange.target_plan_code)} is blocked because current usage exceeds its limits.`;
    }
    return `Plan change to ${formatPlanName(planChange.target_plan_code)} is ${planChange.status}.`;
  }, [planChange]);

  if (isLoading && !currentSubscription && !entitlements) {
    return (
      <DashboardLayout role="admin" title="Billing" description="Subscription status and payment records.">
        <LoadingState label="Loading billing..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout role="admin" title="Billing" description="Subscription lifecycle, payments, limits and plan changes.">
      <div className="space-y-5">
        {errors.currentSubscription ? <Notice tone="warning">{errors.currentSubscription}</Notice> : null}
        {errors.entitlements ? <Notice tone="warning">{errors.entitlements}</Notice> : null}
        {isAttentionRequired ? (
          <Notice tone="warning">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            Your subscription needs attention. Review the lifecycle date and payment history below.
          </Notice>
        ) : null}
        {normalizedStatus === "grace_period" ? (
          <Notice tone="warning">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            A renewal payment failed. Paid features remain available until {formatDateTime(currentSubscription?.grace_ends_at || entitlements?.grace_ends_at)}.
          </Notice>
        ) : null}
        {isNonRenewing ? (
          <Notice tone="info">
            <Ban className="mt-0.5 h-4 w-4 shrink-0" />
            Automatic renewal is disabled. Paid access remains active until {formatDateTime(renewalDate)}.
          </Notice>
        ) : null}
        {planChangeMessage ? <Notice tone={planChange?.status === "blocked" ? "warning" : "info"}>{planChangeMessage}</Notice> : null}
        {cancelError ? <Notice tone="error">{cancelError}</Notice> : null}

        <section className="dashboard-grid xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
          <Card className="dashboard-welcome-blue border-0 p-5 shadow-premium sm:p-7">
            <div className="flex h-full flex-col justify-between gap-7">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-primary">{statusMeta.label}</span>
                  <span className="rounded-full border border-white/30 bg-white/15 px-3 py-1 text-xs font-bold text-white">
                    {formatBillingInterval(currentSubscription?.billing_interval)}
                  </span>
                </div>
                <p className="mt-6 text-[11px] font-bold uppercase tracking-[0.16em] text-white/70">Current subscription</p>
                <h2 className="mt-2 text-3xl font-semibold text-white sm:text-4xl">{formatPlanName(planCode)}</h2>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-white/80">
                  Usage limits and premium features are enforced from the active subscription and any scheduled downgrade.
                </p>
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                <BillingSignal icon={CalendarClock} label="Lifecycle" value={lifecycleLabel} />
                <BillingSignal icon={CreditCard} label="Provider" value={provider} />
                <BillingSignal icon={ShieldCheck} label="Status" value={statusMeta.label} />
              </div>
            </div>
          </Card>

          <Card className="p-5 sm:p-6">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-faint">Quick actions</p>
            <h2 className="mt-2 text-xl font-semibold text-text">Manage billing</h2>
            <p className="mt-2 text-sm leading-6 text-text-muted">
              Upgrade immediately, schedule an eligible downgrade, inspect usage, or disable renewal.
            </p>
            <div className="mt-6 grid gap-3">
              <Link to="/admin/billing/plans"><Button className="w-full">Change plan</Button></Link>
              <Link to="/admin/usage"><Button variant="outline" className="w-full">View usage</Button></Link>
              {canCancel ? (
                <Button variant="outline" className="w-full" onClick={() => setCancelOpen(true)}>
                  <Ban className="h-4 w-4" /> Disable automatic renewal
                </Button>
              ) : null}
            </div>
          </Card>
        </section>

        <section className="dashboard-grid xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <Card className="p-5 sm:p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-faint">Subscription record</p>
                <h2 className="mt-2 text-lg font-semibold text-text">Billing details</h2>
              </div>
              <ShieldCheck className="h-5 w-5 text-text-muted" />
            </div>
            {currentSubscription ? (
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                {DETAIL_FIELDS.map((field) => (
                  <div key={field.key} className="rounded-[1.1rem] border border-border/70 bg-surface-muted/25 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">{field.label}</p>
                    <p className="mt-2 text-sm font-semibold leading-6 text-text">
                      {detailValue(field.key, currentSubscription, statusMeta)}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="mt-5"><EmptyState title="No current subscription" description="A subscription record will appear after onboarding or payment." /></div>
            )}
          </Card>

          <Card className="p-5 sm:p-6">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-faint">Transactions</p>
                <h2 className="mt-2 text-lg font-semibold text-text">Payment history</h2>
                <p className="mt-1 text-sm text-text-muted">Successful, failed, pending and abandoned payment attempts recorded by Weave.</p>
              </div>
              <Button variant="outline" size="sm" onClick={() => loadBillingRecords()} disabled={paymentLoading}>
                <RefreshCw className={`h-4 w-4 ${paymentLoading ? "animate-spin" : ""}`} /> Refresh
              </Button>
            </div>

            {paymentError ? <div className="mt-4"><Notice tone="error">{paymentError}</Notice></div> : null}
            {paymentLoading ? (
              <div className="mt-5"><LoadingState label="Loading payments..." /></div>
            ) : payments.items?.length ? (
              <>
                <div className="mt-5 overflow-x-auto rounded-2xl border border-border">
                  <table className="min-w-[680px] w-full text-left text-sm">
                    <thead className="border-b border-border bg-surface-muted/40 text-xs uppercase tracking-wide text-text-muted">
                      <tr><th className="px-4 py-3">Date</th><th className="px-4 py-3">Reference</th><th className="px-4 py-3">Plan</th><th className="px-4 py-3">Status</th><th className="px-4 py-3 text-right">Amount</th></tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {payments.items.map((record) => (
                        <tr key={record.id}>
                          <td className="px-4 py-3 text-text">{formatDateTime(record.paid_at || record.created_at)}</td>
                          <td className="px-4 py-3 font-mono text-xs text-text-muted">{record.reference}</td>
                          <td className="px-4 py-3 text-text">{formatPlanName(record.plan_code)}</td>
                          <td className="px-4 py-3"><Badge variant={paymentStatusVariant(record.status)}>{record.status}</Badge></td>
                          <td className="px-4 py-3 text-right font-semibold text-text">{formatPaymentAmount(record)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="mt-4 flex items-center justify-between gap-3">
                  <p className="text-sm text-text-muted">Page {paymentPage} of {totalPages} · {payments.total} records</p>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" disabled={paymentPage <= 1} onClick={() => setPaymentPage((page) => page - 1)}>Previous</Button>
                    <Button variant="outline" size="sm" disabled={paymentPage >= totalPages} onClick={() => setPaymentPage((page) => page + 1)}>Next</Button>
                  </div>
                </div>
              </>
            ) : (
              <div className="mt-5">
                <EmptyState icon={FileText} title="No payment records yet" description="Checkout attempts and recurring payment events will appear here." />
              </div>
            )}
          </Card>
        </section>

        <Modal
          open={cancelOpen}
          title="Disable automatic renewal?"
          description="Your current paid features remain available until the billing period ends."
          onClose={() => {
            if (!isCancelling) {
              setCancelOpen(false);
              setCancelError("");
            }
          }}
          closeOnOverlay={!isCancelling}
          footer={(
            <div className="flex justify-end gap-2">
              <Button variant="outline" disabled={isCancelling} onClick={() => setCancelOpen(false)}>Keep renewal</Button>
              <Button variant="danger" disabled={isCancelling} onClick={cancelSubscription}>
                {isCancelling ? "Disabling..." : "Disable renewal"}
              </Button>
            </div>
          )}
        >
          <label className="block text-sm font-semibold text-text-soft">
            <span className="mb-1.5 block">Reason (optional)</span>
            <textarea
              className="input-base min-h-24 resize-y"
              value={cancelReason}
              onChange={(event) => setCancelReason(event.target.value)}
              placeholder="Tell us why you are disabling renewal"
              maxLength={500}
            />
          </label>
        </Modal>
      </div>
    </DashboardLayout>
  );
}

function Notice({ children, tone = "info" }) {
  const toneClass = {
    info: "border-info/30 bg-info-soft text-info",
    warning: "border-warning/30 bg-warning-soft text-amber-700",
    error: "border-error/30 bg-error-soft text-error",
  }[tone];
  return (
    <div className={`flex items-start gap-2 rounded-2xl border px-4 py-3 text-sm font-medium ${toneClass}`}>
      {children}
    </div>
  );
}

export default BillingPage;
