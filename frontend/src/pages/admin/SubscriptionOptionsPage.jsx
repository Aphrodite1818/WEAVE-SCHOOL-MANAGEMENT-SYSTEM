import { CheckCircle2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import PublicLayout from "../../components/layout/PublicLayout";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import { LANDING_PRICING_PLANS, formatPlanName } from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { parseApiError } from "../../services/api";
import { subscriptionService } from "../../services/subscriptionService";

function SubscriptionOptionsPage() {
  const { planCode } = useSubscription();
  const [busyPlan, setBusyPlan] = useState("");
  const [error, setError] = useState("");
  const paidPlans = useMemo(
    () => LANDING_PRICING_PLANS.filter((plan) => ["plus", "professional", "enterprise"].includes(plan.planCode)),
    [],
  );

  const upgrade = async (targetPlan) => {
    setBusyPlan(targetPlan);
    setError("");
    try {
      const checkout = await subscriptionService.initializePaidCurrentTermCheckout({ plan_code: targetPlan });
      window.location.assign(checkout.authorization_url);
    } catch (checkoutError) {
      setError(parseApiError(checkoutError, "Could not start term-plan checkout.").message);
      setBusyPlan("");
    }
  };

  return (
    <PublicLayout>
      <main className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-primary">Term plans</p>
            <h1 className="mt-1 text-3xl font-semibold text-text">Upgrade the current academic term</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-text-muted">The backend prices and activates the selected plan for the current term. Free remains available when activating a new term.</p>
          </div>
          <Link to="/admin/billing" className="btn-base min-h-10 border border-border/80 bg-surface px-4 py-2 text-sm text-text-soft">Back to billing</Link>
        </div>

        {error ? <div className="mt-5 rounded-2xl border border-error/30 bg-error-soft p-4 text-sm text-error">{error}</div> : null}

        <section className="mt-7 grid gap-5 lg:grid-cols-3">
          {paidPlans.map((plan) => {
            const current = plan.planCode === planCode;
            return (
              <Card key={plan.planCode} className="flex min-h-[28rem] flex-col p-5 sm:p-6">
                <div className="flex items-start justify-between gap-3">
                  <div><p className="text-xl font-semibold text-text">{plan.name}</p><p className="mt-1 text-sm text-text-muted">{plan.bestFor}</p></div>
                  {current ? <Badge variant="success">Current</Badge> : null}
                </div>
                <p className="mt-5 text-2xl font-semibold text-text">{plan.priceLabel}</p>
                <p className="mt-3 text-sm leading-6 text-text-muted">{plan.description}</p>
                <div className="mt-5 space-y-3">
                  {(plan.features || []).slice(0, 8).map((feature) => <div key={feature} className="flex gap-2 text-sm text-text-soft"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />{feature}</div>)}
                </div>
                <Button className="mt-auto" onClick={() => upgrade(plan.planCode)} disabled={current || busyPlan === plan.planCode}>
                  {busyPlan === plan.planCode ? "Starting checkout..." : current ? "Current term plan" : `Upgrade to ${formatPlanName(plan.planCode)}`}
                </Button>
              </Card>
            );
          })}
        </section>
      </main>
    </PublicLayout>
  );
}

export default SubscriptionOptionsPage;
