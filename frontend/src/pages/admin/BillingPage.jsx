import { useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  Ban,
  CalendarClock,
  CreditCard,
  FileText,
  ShieldCheck,
} from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import {
  formatBillingInterval,
  formatDateTime,
  formatPlanName,
} from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { subscriptionService } from "../../services/subscriptionService";
import { getErrorMessage } from "../../services/api";

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
  const amount = record?.amount ?? record?.amount_paid ?? record?.total;
  const amountKobo = record?.amount_kobo;
  const currency = record?.currency || "NGN";
  const numericAmount = amount !== undefined && amount !== null
    ? Number(amount)
    : amountKobo !== undefined && amountKobo !== null
      ? Number(amountKobo) / 100
      : null;
  if (!Number.isFinite(numericAmount)) return "--";
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(numericAmount);
  } catch {
    return `${currency} ${numericAmount.toLocaleString()}`;
  }
}

function getPaymentDate(record) {
  return record?.paid_at || record?.created_at || record?.updated_at || record?.date;
}

function getPaymentRows(subscription) {
  const candidates = [
    subscription?.payment_history,
    subscription?.billing_history,
    subscription?.payments,
    subscription?.transactions,
    subscription?.invoices,
  ];
  return candidates.find(Array.isArray) || [];
}

function getDaysUntil(dateValue) {
  if (!dateValue) return null;
  const timestamp = new Date(dateValue).getTime();
  if (!Number.isFinite(timestamp)) return null;
  return Math.ceil((timestamp - Date.now()) / 86400000);
}

function getRenewalLabel(daysUntilRenewal, status) {
  if (daysUntilRenewal === null) return "Renewal date pending";
  const normalizedStatus = String(status || "").toLowerCase();
  if (daysUntilRenewal < 0) {
    const elapsed = Math.abs(daysUntilRenewal);
    if (["grace", "past_due", "overdue"].includes(normalizedStatus)) {
      return `${elapsed} day${elapsed === 1 ? "" : "s"} overdue`;
    }
    return `Ended ${elapsed} day${elapsed === 1 ? "" : "s"} ago`;
  }
  if (daysUntilRenewal === 0) {
    return normalizedStatus === "cancelled" || normalizedStatus === "canceled"
      ? "Ends today"
      : "Renews today";
  }
  if (["cancelled", "canceled", "non_renewing"].includes(normalizedStatus)) {
    return `Ends in ${daysUntilRenewal} day${daysUntilRenewal === 1 ? "" : "s"}`;
  }
  return `${daysUntilRenewal} day${daysUntilRenewal === 1 ? "" : "s"} left`;
}

function DetailValue({ fieldKey, subscription, statusMeta }) {
  if (fieldKey === "status") return statusMeta.label;
  if (fieldKey === "plan_code") return formatPlanName(subscription?.plan_code);
  if (fieldKey === "billing_interval") return formatBillingInterval(subscription?.billing_interval);
  if (fieldKey === "cancel_at_period_end") return subscription?.cancel_at_period_end ? "Yes" : "No";
  if (["current_period_start", "current_period_end", "trial_ends_at", "grace_ends_at", "next_payment_at"].includes(fieldKey)) {
    return formatDateTime(subscription?.[fieldKey]);
  }
  return subscription?.[fieldKey] || "--";
}

function BillingSignal({ icon: Icon, label, value }) {
  return (
    <div className="flex min-h-16 min-w-0 items-center gap-3 rounded-xl border border-white/20 bg-white/[0.12] px-3 py-3 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.14)] sm:px-4">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/15 text-white"><Icon className="h-4 w-4" /></span>
      <div className="min-w-0"><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-white/65">{label}</p><p className="mt-1 text-sm font-semibold leading-5 text-white">{value || "--"}</p></div>
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
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelError, setCancelError] = useState("");
  const [isCancelling, setIsCancelling] = useState(false);

  const paymentRows = getPaymentRows(currentSubscription);
  const renewalDate = currentSubscription?.current_period_end || entitlements?.current_period_end;
  const provider = currentSubscription?.provider || entitlements?.provider || "Paystack";
  const rawStatus = currentSubscription?.status || entitlements?.status || statusMeta?.value || statusMeta?.label;
  const daysUntilRenewal = getDaysUntil(renewalDate);
  const renewalLabel = getRenewalLabel(daysUntilRenewal, rawStatus);
  const normalizedStatus = String(rawStatus || "").toLowerCase();
  const isNonRenewing = normalizedStatus === "non_renewing" || Boolean(currentSubscription?.cancel_at_period_end);
  const canCancel = normalizedStatus === "active" && !isNonRenewing;

  const cancelSubscription = async () => {
    setCancelError("");
    setIsCancelling(true);
    try {
      await subscriptionService.cancelCurrentSubscription({
        confirmation: "CANCEL_SUBSCRIPTION",
        reason: cancelReason.trim() || undefined,
      });
      await refreshSubscriptionState({ silent: true });
      setCancelOpen(false);
      setCancelReason("");
    } catch (error) {
      setCancelError(getErrorMessage(error, "Could not cancel automatic renewal."));
    } finally {
      setIsCancelling(false);
    }
  };

  if (isLoading && !currentSubscription && !entitlements) {
    return <DashboardLayout role="admin" title="Billing" description="Payment records, subscription status, and billing details."><LoadingState label="Loading billing..." /></DashboardLayout>;
  }

  return (
    <DashboardLayout role="admin" title="Billing" description="Payment records, subscription status, and billing details.">
      <div className="space-y-5">
        {errors.currentSubscription ? <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-medium text-amber-700">{errors.currentSubscription}</div> : null}
        {errors.entitlements ? <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-medium text-amber-700">{errors.entitlements}</div> : null}
        {isAttentionRequired ? <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-medium text-amber-700"><span className="flex items-start gap-2"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><span>Your subscription needs attention. Review your billing status or continue to plan upgrade.</span></span></div> : null}
        {isNonRenewing ? <div className="rounded-2xl border border-info/30 bg-info-soft px-4 py-3 text-sm font-medium text-info"><span className="flex items-start gap-2"><Ban className="mt-0.5 h-4 w-4 shrink-0" /><span>Automatic renewal is cancelled. Your paid access remains active until {formatDateTime(renewalDate)}.</span></span></div> : null}
        {cancelError ? <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">{cancelError}</div> : null}

        <section className="dashboard-grid xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
          <Card className="dashboard-welcome-blue relative overflow-hidden border-0 p-5 shadow-premium sm:p-7 lg:p-8">
            <div className="relative grid gap-6 2xl:grid-cols-[minmax(0,1fr)_20rem] 2xl:items-stretch">
              <div className="flex min-w-0 flex-col justify-between gap-6">
                <div>
                  <div className="flex flex-wrap items-center gap-2"><span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-primary shadow-sm">{statusMeta.label}</span><span className="rounded-full border border-white/30 bg-white/15 px-3 py-1 text-xs font-bold text-white">{formatBillingInterval(currentSubscription?.billing_interval)}</span></div>
                  <p className="mt-6 text-[11px] font-bold uppercase tracking-[0.16em] text-white/70">Subscription</p>
                  <h2 className="mt-2 max-w-3xl text-3xl font-semibold leading-tight text-white sm:text-4xl">{formatPlanName(planCode)}</h2>
                  <p className="mt-3 max-w-2xl text-sm leading-6 text-white/80">Review lifecycle timing, provider status, and recorded payments before the next billing event.</p>
                </div>
                <div className="grid gap-3 md:grid-cols-3"><BillingSignal icon={CalendarClock} label="Lifecycle" value={renewalLabel} /><BillingSignal icon={CreditCard} label="Provider" value={provider || "--"} /><BillingSignal icon={ShieldCheck} label="Status" value={statusMeta.label} /></div>
              </div>

              <div className="rounded-2xl border border-white/25 bg-white px-5 py-5 text-primary shadow-[0_22px_55px_rgba(15,23,42,0.18)]">
                <div className="flex items-start justify-between gap-3"><div><p className="text-[10px] font-bold uppercase tracking-[0.16em] text-primary/60">Plan card</p><p className="mt-2 text-2xl font-semibold text-primary">{formatPlanName(planCode)}</p></div><span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary text-white"><CreditCard className="h-5 w-5" /></span></div>
                <div className="mt-8 grid gap-3">
                  <div className="grid gap-1 border-b border-primary/10 pb-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"><span className="text-xs font-semibold uppercase tracking-wide text-primary/60">Period end</span><span className="text-sm font-semibold text-primary sm:text-right">{formatDateTime(renewalDate)}</span></div>
                  <div className="grid gap-1 border-b border-primary/10 pb-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"><span className="text-xs font-semibold uppercase tracking-wide text-primary/60">Processor</span><span className="text-sm font-semibold capitalize text-primary sm:text-right">{provider || "--"}</span></div>
                  <div className="grid gap-1 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"><span className="text-xs font-semibold uppercase tracking-wide text-primary/60">Workspace</span><span className="text-sm font-semibold text-primary sm:text-right">Admin billing</span></div>
                </div>
                <div className="mt-7 rounded-2xl bg-primary-subtle px-4 py-3"><p className="text-xs font-semibold text-primary/70">Lifecycle window</p><p className="mt-1 text-lg font-semibold text-primary">{renewalLabel}</p></div>
              </div>
            </div>
          </Card>

          <Card className="p-5 sm:p-6">
            <div className="flex items-start justify-between gap-4"><div><p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-faint">Quick actions</p><h2 className="mt-2 text-xl font-semibold text-text">Manage plan and usage</h2><p className="mt-2 text-sm leading-6 text-text-muted">Jump into plan changes or review resource usage before the next billing event.</p></div><span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary"><CreditCard className="h-5 w-5" /></span></div>
            <div className="mt-6 grid gap-3">
              <Link to="/admin/billing/plans" className="block"><Button className="w-full">Upgrade Plan</Button></Link>
              <Link to="/admin/usage" className="block"><Button variant="outline" className="w-full">View Usage</Button></Link>
              {canCancel ? (
                <Button type="button" variant="outline" className="w-full" onClick={() => setCancelOpen(true)}>
                  <Ban className="h-4 w-4" /> Cancel automatic renewal
                </Button>
              ) : null}
            </div>
            <div className="mt-6 rounded-[1.2rem] border border-border/70 bg-surface-muted/30 px-4 py-4"><p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-text-faint">Admin note</p><p className="mt-2 text-sm leading-6 text-text-muted">Billing stays separate from day-to-day analytics so finance, lifecycle state, and payment history remain clear.</p></div>
          </Card>
        </section>

        <section className="dashboard-grid xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <Card className="p-5 sm:p-6">
            <div className="flex items-start justify-between gap-4"><div><p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-faint">Subscription record</p><h2 className="mt-2 text-lg font-semibold text-text">Billing details</h2><p className="mt-1 text-sm text-text-muted">Live subscription fields from the backend subscription record.</p></div><span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-surface-muted/60 text-text-muted"><ShieldCheck className="h-5 w-5" /></span></div>
            {currentSubscription ? <div className="mt-5 grid gap-3 sm:grid-cols-2">{DETAIL_FIELDS.map((field) => <div key={field.key} className="rounded-[1.1rem] border border-border/70 bg-surface-muted/25 px-4 py-3"><p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">{field.label}</p><p className="mt-2 text-sm font-semibold leading-6 text-text"><DetailValue fieldKey={field.key} subscription={currentSubscription} statusMeta={statusMeta} /></p></div>)}</div> : <div className="mt-5"><EmptyState title="No current subscription found" description="We could not find a current subscription record yet. Billing details will appear here when the backend returns them." /></div>}
          </Card>

          <Card className="p-5 sm:p-6">
            <div className="flex items-start justify-between gap-3"><div><p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-faint">Transactions</p><h2 className="mt-2 text-lg font-semibold text-text">Payment history</h2><p className="mt-1 text-sm text-text-muted">Payment rows appear here when the backend returns transactions, invoices, or payment history.</p></div><span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary"><FileText className="h-5 w-5" /></span></div>
            {paymentRows.length > 0 ? <div className="mt-5 overflow-hidden rounded-2xl border border-border"><div className="grid grid-cols-[1fr_auto_auto] gap-3 border-b border-border bg-surface-muted/40 px-4 py-3 text-xs font-bold uppercase tracking-wide text-text-muted"><span>Date</span><span>Status</span><span className="text-right">Amount</span></div>{paymentRows.map((record, index) => <div key={record?.id || record?.reference || index} className="grid grid-cols-[1fr_auto_auto] gap-3 border-b border-border/70 px-4 py-3 text-sm last:border-b-0"><div><p className="font-semibold text-text">{formatDateTime(getPaymentDate(record))}</p><p className="mt-0.5 text-xs text-text-muted">{record?.reference || record?.invoice_number || "--"}</p></div><Badge variant={["paid", "success"].includes(String(record?.status || "").toLowerCase()) ? "success" : "default"}>{record?.status || "Recorded"}</Badge><p className="text-right font-semibold text-text">{formatPaymentAmount(record)}</p></div>)}</div> : <div className="mt-5"><EmptyState title="No payment history yet" description="No payment-history endpoint data is currently available for this tenant. Completed payments will appear here once the backend exposes them." /></div>}
          </Card>
        </section>
        <Modal
          open={cancelOpen}
          title="Cancel automatic renewal?"
          description="You will keep your current paid features until the end of the billing period. Paystack will not charge the next renewal."
          onClose={() => {
            if (!isCancelling) {
              setCancelOpen(false);
              setCancelError("");
            }
          }}
          closeOnOverlay={!isCancelling}
          footer={(
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" disabled={isCancelling} onClick={() => setCancelOpen(false)}>Keep subscription</Button>
              <Button type="button" variant="danger" disabled={isCancelling} onClick={cancelSubscription}>
                {isCancelling ? "Cancelling..." : "Cancel renewal"}
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
              placeholder="Tell us why you are cancelling"
              maxLength={500}
            />
          </label>
        </Modal>
      </div>
    </DashboardLayout>
  );
}

export default BillingPage;
