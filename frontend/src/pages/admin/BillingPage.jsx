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

function BillingSnapshotCard({ icon: Icon, label, value, hint }) {
  return (
    <div className="rounded-[1.2rem] border border-white/10 bg-white/5 px-4 py-4 backdrop-blur-sm">
      <div className="flex items-center gap-2 text-white/70">
        <Icon className="h-4 w-4" />
        <p className="text-[11px] font-semibold uppercase tracking-[0.12em]">
          {label}
        </p>
      </div>
      <p className="mt-3 text-base font-semibold text-white">
        {value || "--"}
      </p>
      {hint ? (
        <p className="mt-1 text-xs text-white/60">
          {hint}
        </p>
      ) : null}
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
          <Card className="relative overflow-hidden border-border/70 bg-[radial-gradient(circle_at_top_left,rgba(37,99,235,0.2),transparent_45%),linear-gradient(180deg,rgba(15,23,42,0.98),rgba(15,23,42,0.92))] p-5 sm:p-6">
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-y-0 right-0 w-40 bg-[radial-gradient(circle_at_center,rgba(148,163,184,0.14),transparent_70%)]"
            />
            <div className="relative flex flex-col gap-5">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={statusMeta.badgeVariant}>{statusMeta.label}</Badge>
                  <Badge variant="default">{formatPlanName(planCode)}</Badge>
                </div>
                <p className="mt-5 text-[11px] font-semibold uppercase tracking-[0.16em] text-primary/80">
                  Billing overview
                </p>
                <h2 className="mt-2 text-2xl font-semibold text-white sm:text-[2rem]">
                  Subscription command center
                </h2>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
                  Track plan status, renewal timing, payment provider activity,
                  and transaction history from one place without leaving the
                  admin workspace.
                </p>
              </div>

              <div className="dashboard-kpi-grid mt-1 lg:grid-cols-3">
                <BillingSnapshotCard
                  icon={ShieldCheck}
                  label="Current plan"
                  value={formatPlanName(planCode)}
                  hint="Active workspace tier"
                />
                <BillingSnapshotCard
                  icon={CalendarClock}
                  label="Renews or expires"
                  value={formatDateTime(renewalDate)}
                  hint="Next lifecycle date"
                />
                <BillingSnapshotCard
                  icon={CreditCard}
                  label="Payment provider"
                  value={provider || "--"}
                  hint="Billing infrastructure"
                />
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
