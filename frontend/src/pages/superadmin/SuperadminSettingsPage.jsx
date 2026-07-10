import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, LockKeyhole, RefreshCw, ShieldAlert, Unlock } from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import { getErrorMessage } from "../../services/api";
import { superadminService } from "../../services/superadmin.service";
import { cn } from "../../utils/cn";

const DEFAULT_MESSAGE = "LearnlyAI is temporarily in maintenance mode. Please try again later.";

function SuperadminSettingsPage() {
  const [platformControl, setPlatformControl] = useState(null);
  const [reason, setReason] = useState("Suspicious activity or emergency maintenance.");
  const [message, setMessage] = useState(DEFAULT_MESSAGE);
  const [lockConfirm, setLockConfirm] = useState("");
  const [unlockConfirm, setUnlockConfirm] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const loadPlatformControl = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await superadminService.getPlatformControl();
      setPlatformControl(result);
      if (result?.lockdown_reason) setReason(result.lockdown_reason);
      if (result?.lockdown_message) setMessage(result.lockdown_message);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load platform control state."));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(loadPlatformControl, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadPlatformControl]);

  const lockdownEnabled = Boolean(platformControl?.lockdown_enabled);

  const handleEnableLockdown = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    setSuccess(null);

    try {
      const result = await superadminService.enablePlatformLockdown({
        reason,
        message,
        confirmation: lockConfirm,
      });
      setPlatformControl(result);
      setSuccess("Platform lockdown is active. Non-superadmin traffic is now blocked.");
      setLockConfirm("");
    } catch (err) {
      setError(getErrorMessage(err, "Could not enable platform lockdown."));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDisableLockdown = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    setSuccess(null);

    try {
      const result = await superadminService.disablePlatformLockdown({
        confirmation: unlockConfirm,
      });
      setPlatformControl(result);
      setSuccess("Platform lockdown has been disabled. Normal traffic is allowed again.");
      setUnlockConfirm("");
    } catch (err) {
      setError(getErrorMessage(err, "Could not disable platform lockdown."));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading && !platformControl && !error) {
    return (
      <DashboardLayout role="superadmin" title="Platform Settings">
        <LoadingState label="Loading platform controls..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="superadmin"
      title="Platform Settings"
      actions={
        <Button variant="outline" onClick={loadPlatformControl} disabled={isLoading || isSubmitting}>
          <RefreshCw className="h-4 w-4" />
          Refresh state
        </Button>
      }
    >
      {error ? (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {error}
        </div>
      ) : null}

      {success ? (
        <div className="rounded-2xl border border-success/30 bg-success-soft px-4 py-3 text-sm font-medium text-success">
          {success}
        </div>
      ) : null}

      <section className="relative overflow-hidden rounded-[2rem] border border-slate-800 bg-slate-950 px-4 py-5 text-white shadow-premium sm:px-6 sm:py-7">
        <div className="pointer-events-none absolute inset-0 opacity-70" aria-hidden="true">
          <div className="absolute -right-20 -top-24 h-72 w-72 rounded-full bg-red-500/20 blur-3xl" />
          <div className="absolute -bottom-32 left-8 h-80 w-80 rounded-full bg-cyan-400/15 blur-3xl" />
        </div>

        <div className="relative grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px] xl:items-center">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-red-300/30 bg-red-300/10 px-3 py-1 text-xs font-bold uppercase tracking-[0.2em] text-red-100">
              <ShieldAlert className="h-3.5 w-3.5" />
              Emergency platform control
            </div>
            <h2 className="mt-4 max-w-4xl text-3xl font-semibold leading-tight sm:text-5xl">
              Lock down tenant traffic without shutting the backend down.
            </h2>
            <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-300 sm:text-base">
              Use this only for damage control: suspected compromise, database inconsistency, abuse traffic, or emergency maintenance. Superadmin routes stay available so you can investigate and unlock.
            </p>
          </div>

          <div className="rounded-[1.75rem] border border-white/10 bg-white/10 p-4 backdrop-blur">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-300">Current state</p>
            <div className="mt-4 flex items-center gap-3">
              <div className={cn("flex h-12 w-12 items-center justify-center rounded-2xl", lockdownEnabled ? "bg-red-400/15 text-red-200" : "bg-emerald-400/15 text-emerald-200")}>
                {lockdownEnabled ? <LockKeyhole className="h-6 w-6" /> : <CheckCircle2 className="h-6 w-6" />}
              </div>
              <div>
                <p className="text-2xl font-semibold">{lockdownEnabled ? "Locked down" : "Normal"}</p>
                <p className="text-sm text-slate-300">{lockdownEnabled ? "Only superadmin traffic is allowed." : "All authorized traffic is allowed."}</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)]">
        <Card className="p-4 sm:p-6">
          <div className="flex items-start gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-error-soft text-error">
              <LockKeyhole className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-text">Enable lockdown</h2>
              <p className="mt-1 text-sm leading-6 text-text-muted">
                Blocks normal user operations and shows the maintenance prompt on the frontend.
              </p>
            </div>
          </div>

          <form className="mt-5 grid gap-4" onSubmit={handleEnableLockdown}>
            <Input
              label="Lockdown reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="Suspicious activity detected"
              disabled={isSubmitting || lockdownEnabled}
            />
            <label className="block text-sm font-medium text-text-soft">
              Maintenance message
              <textarea
                className="input-base mt-1.5 min-h-28 resize-y"
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                disabled={isSubmitting || lockdownEnabled}
              />
            </label>
            <Input
              label="Type LOCKDOWN to confirm"
              value={lockConfirm}
              onChange={(event) => setLockConfirm(event.target.value)}
              placeholder="LOCKDOWN"
              disabled={isSubmitting || lockdownEnabled}
            />
            <Button
              type="submit"
              variant="danger"
              disabled={isSubmitting || lockdownEnabled || lockConfirm !== "LOCKDOWN"}
            >
              <LockKeyhole className="h-4 w-4" />
              Activate lockdown
            </Button>
          </form>
        </Card>

        <Card className="p-4 sm:p-6">
          <div className="flex items-start gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-success-soft text-success">
              <Unlock className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-text">Disable lockdown</h2>
              <p className="mt-1 text-sm leading-6 text-text-muted">
                Reopens the platform for tenant admins, teachers, parents, and students.
              </p>
            </div>
          </div>

          <div className="mt-5 rounded-2xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm leading-6 text-warning">
            <div className="flex gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              Unlock only after the incident or maintenance task is complete.
            </div>
          </div>

          <form className="mt-5 grid gap-4" onSubmit={handleDisableLockdown}>
            <Input
              label="Type UNLOCK to confirm"
              value={unlockConfirm}
              onChange={(event) => setUnlockConfirm(event.target.value)}
              placeholder="UNLOCK"
              disabled={isSubmitting || !lockdownEnabled}
            />
            <Button
              type="submit"
              variant="success"
              disabled={isSubmitting || !lockdownEnabled || unlockConfirm !== "UNLOCK"}
            >
              <Unlock className="h-4 w-4" />
              Disable lockdown
            </Button>
          </form>
        </Card>
      </section>
    </DashboardLayout>
  );
}

export default SuperadminSettingsPage;
