import { useMemo, useState } from "react";
import { FlaskConical, RotateCcw, RefreshCw } from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import { simulationService } from "../../features/simulation/simulationService";
import { useToast } from "../../hooks/useToast";
import { getErrorMessage } from "../../services/api";

const SCENARIOS = [
  {
    value: "expires_in_days",
    label: "Subscription expires in N days",
    needsDays: true,
  },
  {
    value: "period_ended",
    label: "Subscription period already ended",
    needsDays: false,
  },
  {
    value: "grace_expires_in_days",
    label: "Grace period expires in N days",
    needsDays: true,
  },
  {
    value: "grace_expired",
    label: "Grace period already expired",
    needsDays: false,
  },
];

const formatDate = (value) => {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString();
};

function StateRow({ label, value }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-border/60 py-3 last:border-b-0">
      <span className="text-sm text-text-muted">{label}</span>
      <span className="max-w-[65%] break-words text-right text-sm font-semibold text-text">{value}</span>
    </div>
  );
}

function SuperadminSimulationPage() {
  const { showError, showSuccess } = useToast();
  const [tenantId, setTenantId] = useState("");
  const [scenario, setScenario] = useState("expires_in_days");
  const [days, setDays] = useState("7");
  const [state, setState] = useState(null);
  const [busyAction, setBusyAction] = useState("");
  const [lastResult, setLastResult] = useState(null);

  const selectedScenario = useMemo(
    () => SCENARIOS.find((item) => item.value === scenario) || SCENARIOS[0],
    [scenario],
  );

  const requireTenantId = () => {
    const normalized = tenantId.trim();
    if (!normalized) {
      showError("Enter a tenant ID first.");
      return null;
    }
    return normalized;
  };

  const loadState = async () => {
    const normalizedTenantId = requireTenantId();
    if (!normalizedTenantId) return;
    setBusyAction("load");
    try {
      const result = await simulationService.getSubscriptionState(normalizedTenantId);
      setState(result);
      setLastResult(null);
      showSuccess("Subscription state loaded.");
    } catch (error) {
      showError(getErrorMessage(error, "Unable to load the subscription simulation state."));
    } finally {
      setBusyAction("");
    }
  };

  const runSimulation = async () => {
    const normalizedTenantId = requireTenantId();
    if (!normalizedTenantId) return;

    const payload = { scenario };
    if (selectedScenario.needsDays) {
      const parsedDays = Number(days);
      if (!Number.isInteger(parsedDays) || parsedDays < 1 || parsedDays > 90) {
        showError("Days must be a whole number between 1 and 90.");
        return;
      }
      payload.days = parsedDays;
    }

    setBusyAction("simulate");
    try {
      const result = await simulationService.runSubscriptionSimulation(
        normalizedTenantId,
        payload,
      );
      setState(result.state);
      setLastResult(result);
      showSuccess(result.detail || "Simulation applied.");
    } catch (error) {
      showError(getErrorMessage(error, "Unable to apply the subscription simulation."));
    } finally {
      setBusyAction("");
    }
  };

  const reconcile = async () => {
    const normalizedTenantId = requireTenantId();
    if (!normalizedTenantId) return;
    setBusyAction("reconcile");
    try {
      const result = await simulationService.reconcileSubscription(normalizedTenantId);
      setState(result.state);
      setLastResult(result);
      showSuccess(result.detail || "Subscription reconciled.");
    } catch (error) {
      showError(getErrorMessage(error, "Unable to reconcile the simulated subscription."));
    } finally {
      setBusyAction("");
    }
  };

  const reset = async () => {
    const normalizedTenantId = requireTenantId();
    if (!normalizedTenantId) return;
    setBusyAction("reset");
    try {
      const result = await simulationService.resetSubscription(normalizedTenantId);
      setState(result.state);
      setLastResult(result);
      showSuccess(result.detail || "Original subscription state restored.");
    } catch (error) {
      showError(getErrorMessage(error, "Unable to reset the subscription simulation."));
    } finally {
      setBusyAction("");
    }
  };

  const busy = Boolean(busyAction);

  return (
    <DashboardLayout role="superadmin" title="Simulation Lab">
      <div className="grid gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <Card className="p-5 sm:p-6">
          <div className="flex items-start gap-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary">
              <FlaskConical className="h-5 w-5" />
            </div>
            <div>
              <h2 className="section-title">Subscription simulation</h2>
              <p className="mt-1 text-sm text-text-muted">
                Staging only. This changes Weave's local subscription dates and never calls Paystack.
              </p>
            </div>
          </div>

          <div className="mt-5 space-y-4">
            <Input
              label="Tenant ID"
              value={tenantId}
              onChange={(event) => setTenantId(event.target.value)}
              placeholder="Paste tenant UUID"
              autoComplete="off"
            />

            <div>
              <label className="mb-1.5 block text-sm font-semibold text-text-soft" htmlFor="simulation-scenario">
                Scenario
              </label>
              <select
                id="simulation-scenario"
                className="input-base w-full"
                value={scenario}
                onChange={(event) => setScenario(event.target.value)}
              >
                {SCENARIOS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </div>

            {selectedScenario.needsDays ? (
              <Input
                label="Days"
                type="number"
                min="1"
                max="90"
                value={days}
                onChange={(event) => setDays(event.target.value)}
              />
            ) : null}

            <div className="flex flex-wrap gap-2">
              <Button type="button" onClick={runSimulation} disabled={busy}>
                <FlaskConical className="h-4 w-4" />
                {busyAction === "simulate" ? "Applying..." : "Apply simulation"}
              </Button>
              <Button type="button" variant="outline" onClick={loadState} disabled={busy}>
                {busyAction === "load" ? "Loading..." : "Load current state"}
              </Button>
            </div>
          </div>
        </Card>

        <Card className="p-5 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="section-title">Current simulated state</h2>
              <p className="mt-1 text-sm text-text-muted">
                Only subscription lifecycle fields are shown here. Provider credentials and tenant personal data are never returned.
              </p>
            </div>
            {state ? (
              <Badge variant={state.snapshot_available ? "warning" : "default"}>
                {state.snapshot_available ? "Snapshot saved" : "No active snapshot"}
              </Badge>
            ) : null}
          </div>

          {state ? (
            <div className="mt-4 rounded-2xl border border-border/70 px-4">
              <StateRow label="Plan" value={state.plan_code} />
              <StateRow label="Status" value={state.status} />
              <StateRow label="Period starts" value={formatDate(state.current_period_start)} />
              <StateRow label="Period ends" value={formatDate(state.current_period_end)} />
              <StateRow label="Trial ends" value={formatDate(state.trial_ends_at)} />
              <StateRow label="Grace ends" value={formatDate(state.grace_ends_at)} />
              <StateRow label="Next payment" value={formatDate(state.next_payment_at)} />
              <StateRow label="Cancel at period end" value={state.cancel_at_period_end ? "Yes" : "No"} />
            </div>
          ) : (
            <div className="mt-5 rounded-2xl border border-dashed border-border px-4 py-10 text-center text-sm text-text-muted">
              Enter a tenant ID and load its subscription state.
            </div>
          )}

          <div className="mt-5 flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={reconcile} disabled={busy || !state}>
              <RefreshCw className="h-4 w-4" />
              {busyAction === "reconcile" ? "Reconciling..." : "Run reconciliation"}
            </Button>
            <Button type="button" variant="outline" onClick={reset} disabled={busy || !state?.snapshot_available}>
              <RotateCcw className="h-4 w-4" />
              {busyAction === "reset" ? "Resetting..." : "Reset original state"}
            </Button>
          </div>

          {lastResult?.lifecycle ? (
            <div className="mt-4 rounded-xl border border-border/70 bg-surface-muted/30 px-4 py-3 text-sm text-text-muted">
              Reconciliation: {lastResult.lifecycle.past_due || 0} past due, {lastResult.lifecycle.grace_period || 0} grace, {lastResult.lifecycle.expired || 0} expired.
            </div>
          ) : null}
        </Card>
      </div>
    </DashboardLayout>
  );
}

export default SuperadminSimulationPage;
