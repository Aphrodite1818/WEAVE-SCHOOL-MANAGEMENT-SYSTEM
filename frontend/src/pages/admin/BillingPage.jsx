import { Link } from "react-router-dom";
import {
  AlertTriangle,
  CalendarClock,
  CreditCard,
  FileText,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import {
  formatBillingInterval,
  formatDateTime,
  formatPlanName,
} from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";

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

  const days = Math.ceil((timestamp - Date.now()) / 86400000);
  return Math.max(days, 0);
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
    <div className="flex min-h-16 items-center gap-3 rounded-2xl border border-white/20 bg-white/[0.12] px-4 py-3 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.14)]">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-white/15 text-white">
        <Icon className="h-4 w-4" />
      </span>
      <div className="min-w-0">
        <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-white/65">{label}</p>
        <p className="mt-1 truncate text-sm font-semibold text-white">{value || "--"}</p>
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
    isRefreshing,
    errors,
    refreshSubscriptionState,
  } = useSubscription();

  const paymentRows = getPaymentRows(currentSubscription);
  const renewalDate =
    currentSubscription?.current_period_end || entitlements?.current_period_end;
  const provider = currentSubscription?.provider || entitlements?.provider || "Paystack";
  const daysUntilRenewal = getDaysUntil(renewalDate);
  const renewalLabel = daysUntilRenewal === null
    ? "Renewal date pending"
    : daysUntilRenewal === 0
      ? "Renews today"
      : `${daysUntilRenewal} day${daysUntilRenewal === 1 ? "" : "s"} left`;

  const refreshAction = (
    <Button
      variant="outline"
      onClick={() => refreshSubscriptionState()}
      disabled={isLoading || isRefreshing}
    >
      <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
      {isRefreshing ? "Refreshing..." : "Refresh"}
    </Button>
  );

  if (isLoading && !currentSubscription && !entitlements) {
    return (
      <DashboardLayout
        role="admin"
        title="Billing"
        description="Payment records, subscription status, and billing details."
        actions={refreshAction}
      >
        <LoadingState label="Loading billing..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="admin"
      title="Billing"
      description="Payment records, subscription status, and billing details."
      actions={refreshAction}
    >
      <div className="space-y-5">
        {errors.currentSubscription ? (
          <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-medium text-amber-700">
            {errors.currentSubscription}
          </div>
        ) : null}

        {errors.entitlements ? (
          <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-medium text-amber-700">
            {errors.entitlements}
          </div>
        ) : null}

        {isAttentionRequired ? (
          <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-medium text-amber-700">
            <span className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                Your subscription needs attention. Review your billing status or continue to plan upgrade.
              </span>
            </span>
          </div>
        ) : null}

        <section className="dashboard-grid xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
          <Card className="dashboard-welcome-blue relative overflow-hidden border-0 p-5 shadow-premium sm:p-7 lg:p-8">
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-y-0 right-0 w-1/3 bg-[linear-gradient(135deg,transparent_0%,rgba(255,255,255,0.12)_48%,transparent_49%,transparent_100%)]"
            />
            <div
              aria-hidden="true"
              className="pointer-events-none absolute bottom-0 left-0 right-0 h-px bg-white/25"
            />
            <div className="relative grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-stretch">
              <div className="flex min-w-0 flex-col justify-between gap-6">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-primary shadow-sm">
                      {statusMeta.label}
                    </span>
                    <span className="rounded-full border border-white/30 bg-white/15 px-3 py-1 text-xs font-bold text-white">
                      {formatBillingInterval(currentSubscription?.billing_interval)}
                    </span>
                  </div>
                  <p className="mt-6 text-[11px] font-bold uppercase tracking-[0.16em] text-white/70">
                    Active subscription
                  </p>
                  <h2 className="mt-2 max-w-3xl text-3xl font-semibold leading-tight text-white sm:text-4xl">
                    {formatPlanName(planCode)}
                  </h2>
                  <p className="mt-3 max-w-2xl text-sm leading-6 text-white/80">
                    Billing is active for this workspace. Review renewal timing,
                    provider status, and payments before the next cycle.
                  </p>
                </div>

                <div className="grid gap-3 sm:grid-cols-3">
                  <BillingSignal icon={CalendarClock} label="Lifecycle" value={renewalLabel} />
                  <BillingSignal icon={CreditCard} label="Provider" value={provider || "--"} />
                  <BillingSignal icon={ShieldCheck} label="Status" value={statusMeta.label} />
                </div>
              </div>

              <div className="rounded-[1.5rem] border border-white/25 bg-white px-5 py-5 text-primary shadow-[0_22px_55px_rgba(15,23,42,0.18)]">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-primary/60">Plan card</p>
                    <p className="mt-2 text-2xl font-semibold text-primary">{formatPlanName(planCode)}</p>
                  </div>
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary text-white">
                    <CreditCard className="h-5 w-5" />
                  </span>
                </div>

                <div className="mt-8 grid gap-3">
                  <div className="flex items-center justify-between gap-4 border-b border-primary/10 pb-3">
                    <span className="text-xs font-semibold uppercase tracking-wide text-primary/60">Next billing</span>
                    <span className="text-sm font-semibold text-primary">{formatDateTime(renewalDate)}</span>
                  </div>
                  <div className="flex items-center justify-between gap-4 border-b border-primary/10 pb-3">
                    <span className="text-xs font-semibold uppercase tracking-wide text-primary/60">Processor</span>
                    <span className="text-sm font-semibold capitalize text-primary">{provider || "--"}</span>
                  </div>
                  <div className="flex items-center justify-between gap-4">
                    <span className="text-xs font-semibold uppercase tracking-wide text-primary/60">Workspace</span>
                    <span className="text-sm font-semibold text-primary">Admin billing</span>
                  </div>
                </div>

                <div className="mt-7 rounded-2xl bg-primary-subtle px-4 py-3">
                  <p className="text-xs font-semibold text-primary/70">Renewal window</p>
                  <p className="mt-1 text-lg font-semibold text-primary">{renewalLabel}</p>
                </div>
              </div>
            </div>
          </Card>

          <Card className="p-5 sm:p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-faint">
                  Quick actions
                </p>
                <h2 className="mt-2 text-xl font-semibold text-text">
                  Manage plan and usage
                </h2>
                <p className="mt-2 text-sm leading-6 text-text-muted">
                  Jump straight into plan changes or review resource usage before
                  the next renewal cycle.
                </p>
              </div>
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                <CreditCard className="h-5 w-5" />
              </span>
            </div>

            <div className="mt-6 grid gap-3">
              <Link to="/admin/billing/plans" className="block">
                <Button className="w-full">Upgrade Plan</Button>
              </Link>
              <Link to="/admin/usage" className="block">
                <Button variant="outline" className="w-full">
                  View Usage
                </Button>
              </Link>
            </div>

            <div className="mt-6 rounded-[1.2rem] border border-border/70 bg-surface-muted/30 px-4 py-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-text-faint">
                Admin note
              </p>
              <p className="mt-2 text-sm leading-6 text-text-muted">
                Billing stays separate from day-to-day analytics so finance,
                renewals, and payment history are easier to review without
                mixing them into operational dashboards.
              </p>
            </div>
          </Card>
        </section>

        <section className="dashboard-grid xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <Card className="p-5 sm:p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-faint">
                  Subscription record
                </p>
                <h2 className="mt-2 text-lg font-semibold text-text">
                  Billing details
                </h2>
                <p className="mt-1 text-sm text-text-muted">
                  Live subscription fields from the backend subscription record.
                </p>
              </div>
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-surface-muted/60 text-text-muted">
                <ShieldCheck className="h-5 w-5" />
              </span>
            </div>

            {currentSubscription ? (
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                {DETAIL_FIELDS.map((field) => (
                  <div
                    key={field.key}
                    className="rounded-[1.1rem] border border-border/70 bg-surface-muted/25 px-4 py-3"
                  >
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                      {field.label}
                    </p>
                    <p className="mt-2 text-sm font-semibold leading-6 text-text">
                      <DetailValue
                        fieldKey={field.key}
                        subscription={currentSubscription}
                        statusMeta={statusMeta}
                      />
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="mt-5">
                <EmptyState
                  title="No current subscription found"
                  description="We could not find a current subscription record yet. Billing details will appear here when the backend returns them."
                />
              </div>
            )}
          </Card>

          <Card className="p-5 sm:p-6">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-faint">
                  Transactions
                </p>
                <h2 className="mt-2 text-lg font-semibold text-text">Payment history</h2>
                <p className="mt-1 text-sm text-text-muted">
                  Payment rows appear here when the backend returns transactions, invoices, or payment history.
                </p>
              </div>
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                <FileText className="h-5 w-5" />
              </span>
            </div>

            {paymentRows.length > 0 ? (
              <div className="mt-5 overflow-hidden rounded-2xl border border-border">
                <div className="grid grid-cols-[1fr_auto_auto] gap-3 border-b border-border bg-surface-muted/40 px-4 py-3 text-xs font-bold uppercase tracking-wide text-text-muted">
                  <span>Date</span>
                  <span>Status</span>
                  <span className="text-right">Amount</span>
                </div>
                {paymentRows.map((record, index) => (
                  <div
                    key={record?.id || record?.reference || index}
                    className="grid grid-cols-[1fr_auto_auto] gap-3 border-b border-border/70 px-4 py-3 text-sm last:border-b-0"
                  >
                    <div>
                      <p className="font-semibold text-text">{formatDateTime(getPaymentDate(record))}</p>
                      <p className="mt-0.5 text-xs text-text-muted">{record?.reference || record?.invoice_number || "--"}</p>
                    </div>
                    <Badge variant={String(record?.status || "").toLowerCase() === "paid" || String(record?.status || "").toLowerCase() === "success" ? "success" : "default"}>
                      {record?.status || "Recorded"}
                    </Badge>
                    <p className="text-right font-semibold text-text">{formatPaymentAmount(record)}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="mt-5">
                <EmptyState
                  title="No payment history yet"
                  description="No payment-history endpoint data is currently available for this tenant. Completed payments will appear here once the backend exposes them."
                />
              </div>
            )}
          </Card>
        </section>
      </div>
    </DashboardLayout>
  );
}

export default BillingPage;
