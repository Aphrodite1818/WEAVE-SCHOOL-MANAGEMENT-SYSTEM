import { useState } from "react";
import { FlaskConical, RefreshCw } from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import { simulationService } from "../../features/simulation/simulationService";
import { useToast } from "../../hooks/useToast";
import { getErrorMessage } from "../../services/api";

const SCENARIOS = [
  ["activate_free", "Activate Free term"],
  ["initialize_paid", "Initialize paid term"],
  ["payment_success", "Simulate successful payment"],
  ["payment_failure", "Simulate payment failure"],
  ["duplicate_webhook", "Replay successful payment"],
  ["wrong_amount", "Reject wrong amount"],
  ["wrong_term", "Reject wrong term"],
  ["upgrade_to_professional", "Upgrade Free to Professional"],
  ["close_term", "Close term entitlement"],
  ["trial_expired", "Expire trial to Free fallback"],
  ["closed_active_reconciliation", "Repair closed term with active entitlement"],
  ["safety_cap_expired", "Expire entitlement at safety cap"],
];

const StateRow = ({ label, value }) => (
  <div className="flex items-start justify-between gap-4 border-b border-border/60 py-3 last:border-b-0">
    <span className="text-sm text-text-muted">{label}</span>
    <span className="max-w-[65%] break-words text-right text-sm font-semibold text-text">
      {value || "—"}
    </span>
  </div>
);

function SuperadminSimulationPage() {
  const { showError, showSuccess } = useToast();
  const [tenantId, setTenantId] = useState("");
  const [termId, setTermId] = useState("");
  const [scenario, setScenario] = useState("activate_free");
  const [planCode, setPlanCode] = useState("plus");
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);

  const requireTenant = () => {
    if (tenantId.trim()) return tenantId.trim();
    showError("Enter a tenant ID first.");
    return null;
  };

  const loadState = async () => {
    const tenant = requireTenant();
    if (!tenant) return;
    setBusy(true);
    try {
      const result = await simulationService.getSubscriptionState(tenant);
      setState(result);
      showSuccess("Term entitlement state loaded.");
    } catch (error) {
      showError(getErrorMessage(error, "Unable to load term entitlement state."));
    } finally {
      setBusy(false);
    }
  };

  const runSimulation = async () => {
    const tenant = requireTenant();
    if (!tenant) return;
    setBusy(true);
    try {
      const result = await simulationService.runSubscriptionSimulation(tenant, {
        scenario,
        academic_term_id: termId.trim() || null,
        plan_code: planCode,
      });
      setState(result.state);
      showSuccess(result.detail || "Term simulation applied.");
    } catch (error) {
      showError(getErrorMessage(error, "Unable to apply the term simulation."));
    } finally {
      setBusy(false);
    }
  };

  const reconcile = async () => {
    const tenant = requireTenant();
    if (!tenant) return;
    setBusy(true);
    try {
      const result = await simulationService.reconcileSubscription(tenant);
      setState(result.state);
      showSuccess(result.detail || "Term entitlement reconciled.");
    } catch (error) {
      showError(getErrorMessage(error, "Unable to reconcile term entitlements."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <DashboardLayout role="superadmin" title="Simulation Lab">
      <div className="grid gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <Card className="p-5 sm:p-6">
          <div className="flex items-start gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary-soft text-primary">
              <FlaskConical className="h-5 w-5" />
            </div>
            <div>
              <h2 className="section-title">Term entitlement simulation</h2>
              <p className="mt-1 text-sm text-text-muted">
                Staging only. Simulated paid events never contact Paystack and never expose provider credentials.
              </p>
            </div>
          </div>

          <div className="mt-5 space-y-4">
            <Input label="Tenant ID" value={tenantId} onChange={(event) => setTenantId(event.target.value)} placeholder="Tenant UUID" />
            <Input label="Academic term ID" value={termId} onChange={(event) => setTermId(event.target.value)} placeholder="Optional; current or latest term is used" />
            <div>
              <label className="mb-1.5 block text-sm font-semibold text-text-soft" htmlFor="simulation-scenario">Scenario</label>
              <select id="simulation-scenario" className="input-base w-full" value={scenario} onChange={(event) => setScenario(event.target.value)}>
                {SCENARIOS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-semibold text-text-soft" htmlFor="simulation-plan">Paid plan</label>
              <select id="simulation-plan" className="input-base w-full" value={planCode} onChange={(event) => setPlanCode(event.target.value)}>
                <option value="plus">Plus</option>
                <option value="professional">Professional</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="button" onClick={runSimulation} disabled={busy}><FlaskConical className="h-4 w-4" />Apply simulation</Button>
              <Button type="button" variant="outline" onClick={loadState} disabled={busy}>Load state</Button>
              <Button type="button" variant="outline" onClick={reconcile} disabled={busy}><RefreshCw className="h-4 w-4" />Reconcile</Button>
            </div>
          </div>
        </Card>

        <Card className="p-5 sm:p-6">
          <div className="flex items-center justify-between gap-3">
            <div><h2 className="section-title">Current term state</h2><p className="mt-1 text-sm text-text-muted">The latest entitlement and payment attempt for the selected tenant term.</p></div>
            {state ? <Badge variant={state.status === "active" ? "success" : "default"}>{state.status}</Badge> : null}
          </div>
          {state ? (
            <div className="mt-4 rounded-2xl border border-border/70 px-4">
              <StateRow label="Academic term" value={state.academic_term_id} />
              <StateRow label="Term status" value={state.term_status} />
              <StateRow label="Plan" value={state.plan_code} />
              <StateRow label="Entitlement status" value={state.status} />
              <StateRow label="Activated" value={state.activated_at} />
              <StateRow label="Closed" value={state.closed_at} />
              <StateRow label="Safety expiry" value={state.safety_expires_at} />
              <StateRow label="Payment reference" value={state.payment_reference} />
              <StateRow label="Payment status" value={state.payment_status} />
            </div>
          ) : <p className="mt-8 text-center text-sm text-text-muted">Load a tenant or apply a scenario to inspect its term state.</p>}
        </Card>
      </div>
    </DashboardLayout>
  );
}

export default SuperadminSimulationPage;
