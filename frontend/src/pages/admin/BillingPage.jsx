import { CreditCard } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
import Badge from "../../components/ui/Badge";
import Card from "../../components/ui/Card";
import { formatPlanName } from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { getErrorMessage } from "../../services/api";
import { subscriptionService } from "../../services/subscriptionService";

const money = (amount, currency = "NGN") => new Intl.NumberFormat("en-NG", { style: "currency", currency, maximumFractionDigits: 0 }).format(Number(amount || 0));

function BillingPage() {
  const { planCode, statusCode } = useSubscription();
  const [history, setHistory] = useState([]);
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([subscriptionService.getTermPlanHistory(), subscriptionService.getPaymentHistory({ limit: 50 })])
      .then(([termRows, paymentRows]) => {
        setHistory(termRows || []);
        setPayments(paymentRows?.items || []);
      })
      .catch((loadError) => setError(getErrorMessage(loadError, "Could not load billing history.")))
      .finally(() => setLoading(false));
  }, []);

  return (
    <DashboardLayout role="admin" title="Billing" description="Academic-term plan activation and one-time payment history.">
      {loading ? <LoadingState label="Loading billing history..." /> : null}
      {error ? <div className="rounded-2xl border border-error/30 bg-error-soft p-4 text-sm text-error">{error}</div> : null}
      {!loading ? <>
        <section className="grid gap-4 sm:grid-cols-2">
          <Card className="p-5"><p className="text-sm text-text-muted">Effective plan</p><p className="mt-2 text-2xl font-semibold text-text">{formatPlanName(planCode || "free")}</p><Badge className="mt-3" variant="success">{String(statusCode || "active").replaceAll("_", " ")}</Badge></Card>
          <Card className="p-5"><CreditCard className="h-6 w-6 text-primary" /><p className="mt-3 text-sm text-text-muted">Plans are purchased once for a specific term. Closing that term closes its entitlement.</p><Link to="/admin/billing/plans" className="btn-base mt-4 inline-flex min-h-10 bg-primary px-4 py-2 text-sm text-primary-foreground">View paid plans</Link></Card>
        </section>
        <Card className="mt-5 p-5"><h2 className="section-title">Term plan history</h2><div className="mt-4 space-y-3">{history.length ? history.map((item) => <div key={item.id} className="flex flex-col gap-2 rounded-2xl border border-border/70 p-4 sm:flex-row sm:items-center sm:justify-between"><div><p className="font-semibold text-text">{formatPlanName(item.plan_code)}</p><p className="text-sm text-text-muted">Term {item.academic_term_id}</p></div><div className="text-left sm:text-right"><Badge variant={item.status === "active" ? "success" : "default"}>{item.status}</Badge><p className="mt-1 text-sm text-text-muted">{money(item.amount, item.currency)}</p></div></div>) : <p className="text-sm text-text-muted">No term plan has been activated yet.</p>}</div></Card>
        <Card className="mt-5 p-5"><h2 className="section-title">Payments</h2><div className="mt-4 space-y-3">{payments.length ? payments.map((item) => <div key={item.id} className="flex items-center justify-between rounded-xl border border-border/70 p-3"><div><p className="font-semibold text-text">{formatPlanName(item.plan_code)}</p><p className="text-xs text-text-muted">{item.reference}</p></div><div className="text-right"><Badge variant={item.status === "success" ? "success" : "default"}>{item.status}</Badge><p className="mt-1 text-sm text-text-muted">{money(item.amount, item.currency)}</p></div></div>) : <p className="text-sm text-text-muted">No payments recorded.</p>}</div></Card>
      </> : null}
    </DashboardLayout>
  );
}

export default BillingPage;
