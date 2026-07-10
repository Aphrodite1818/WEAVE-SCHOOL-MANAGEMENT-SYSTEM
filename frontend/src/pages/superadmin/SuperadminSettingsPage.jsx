import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Ban, CheckCircle2, LockKeyhole, RefreshCw, ShieldAlert, Trash2, Unlock } from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import { useToast } from "../../hooks/useToast";
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
  const [ipBlocks, setIpBlocks] = useState([]);
  const [suspiciousIps, setSuspiciousIps] = useState([]);
  const [blockIpAddress, setBlockIpAddress] = useState("");
  const [blockIpReason, setBlockIpReason] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { showSuccess, showError } = useToast();

  const loadData = useCallback(async () => {
    setIsLoading(true);

    try {
      const [platformResult, ipBlocksResult, securityResult] = await Promise.allSettled([
        superadminService.getPlatformControl(),
        superadminService.getSecurityIPBlocks(true, 50),
        superadminService.getSecurityOverview()
      ]);
      
      if (platformResult.status === "fulfilled" && platformResult.value) {
        setPlatformControl(platformResult.value);
        if (platformResult.value.lockdown_reason) setReason(platformResult.value.lockdown_reason);
        if (platformResult.value.lockdown_message) setMessage(platformResult.value.lockdown_message);
      }
      
      if (ipBlocksResult.status === "fulfilled" && Array.isArray(ipBlocksResult.value)) {
        setIpBlocks(ipBlocksResult.value);
      }

      if (securityResult.status === "fulfilled" && securityResult.value) {
        setSuspiciousIps(securityResult.value.charts?.top_login_ips_7d || []);
      }
    } catch (err) {
      showError(getErrorMessage(err, "Failed to load settings data."));
    } finally {
      setIsLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    const timeoutId = window.setTimeout(loadData, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadData]);

  const lockdownEnabled = Boolean(platformControl?.lockdown_enabled);

  const handleEnableLockdown = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);

    try {
      const result = await superadminService.enablePlatformLockdown({
        reason,
        message,
        confirmation: lockConfirm,
      });
      setPlatformControl(result);
      showSuccess("Platform lockdown is active. Non-superadmin traffic is now blocked.");
      setLockConfirm("");
    } catch (err) {
      showError(getErrorMessage(err, "Could not enable platform lockdown."));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDisableLockdown = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);

    try {
      const result = await superadminService.disablePlatformLockdown({
        confirmation: unlockConfirm,
      });
      setPlatformControl(result);
      showSuccess("Platform lockdown has been disabled. Normal traffic is allowed again.");
      setUnlockConfirm("");
    } catch (err) {
      showError(getErrorMessage(err, "Could not disable platform lockdown."));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleBlockIp = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);

    try {
      await superadminService.createSecurityIPBlock({
        ip_address: blockIpAddress,
        reason: blockIpReason || "Manual block",
      });
      showSuccess(`IP ${blockIpAddress} has been blocked.`);
      setBlockIpAddress("");
      setBlockIpReason("");
      await loadData();
    } catch (err) {
      showError(getErrorMessage(err, "Could not block IP address."));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUnblockIp = async (blockId) => {
    if (!window.confirm("Are you sure you want to unblock this IP?")) return;
    setIsSubmitting(true);

    try {
      await superadminService.unblockSecurityIP(blockId, { reason: "Manual unblock" });
      showSuccess("IP has been unblocked.");
      await loadData();
    } catch (err) {
      showError(getErrorMessage(err, "Could not unblock IP."));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading && !platformControl) {
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
        <Button variant="outline" onClick={loadData} disabled={isLoading || isSubmitting}>
          <RefreshCw className="h-4 w-4" />
          Refresh state
        </Button>
      }
    >
      <section className="relative overflow-hidden rounded-2xl border border-border bg-surface px-4 py-5 sm:px-6 sm:py-7">
        <div className="relative grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px] xl:items-center">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-red-300/30 bg-red-300/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-red-700 dark:text-red-400">
              <ShieldAlert className="h-3.5 w-3.5" />
              Emergency Platform Control
            </div>
            <h2 className="mt-4 max-w-4xl text-2xl font-semibold leading-tight text-text sm:text-3xl">
              Lock down tenant traffic without shutting down the backend.
            </h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-text-muted sm:text-base">
              Use this only for damage control: suspected compromise, database inconsistency, abuse traffic, or emergency maintenance. Superadmin routes stay available so you can investigate and unlock.
            </p>
          </div>

          <div className="rounded-2xl border border-border bg-surface-muted/30 p-4">
            <p className="text-xs font-bold uppercase tracking-wider text-text-muted">Current state</p>
            <div className="mt-4 flex items-center gap-3">
              <div className={cn("flex h-12 w-12 items-center justify-center rounded-xl", lockdownEnabled ? "bg-red-100 text-red-600 dark:bg-red-400/15 dark:text-red-200" : "bg-emerald-100 text-emerald-600 dark:bg-emerald-400/15 dark:text-emerald-200")}>
                {lockdownEnabled ? <LockKeyhole className="h-6 w-6" /> : <CheckCircle2 className="h-6 w-6" />}
              </div>
              <div>
                <p className="text-lg font-semibold text-text">{lockdownEnabled ? "Locked down" : "Normal"}</p>
                <p className="text-sm text-text-muted">{lockdownEnabled ? "Only superadmin traffic is allowed." : "All authorized traffic is allowed."}</p>
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

      <section className="mt-8">
        <Card className="p-4 sm:p-6">
          <div className="flex items-start justify-between gap-3 mb-5">
            <div className="flex items-start gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-warning/10 text-warning">
                <Ban className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-text">Manual IP Containment</h2>
                <p className="mt-1 text-sm leading-6 text-text-muted">
                  Block specific IP addresses from accessing any platform endpoints.
                </p>
              </div>
            </div>
          </div>
          
          <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
            <form onSubmit={handleBlockIp} className="flex flex-col gap-4 rounded-2xl border border-border bg-surface-muted/30 p-4 h-fit">
              <h3 className="text-sm font-semibold text-text">Block new IP</h3>
              <Input
                label="IP Address"
                value={blockIpAddress}
                onChange={(e) => setBlockIpAddress(e.target.value)}
                placeholder="192.168.1.1"
                required
                disabled={isSubmitting}
                list="suspicious-ips"
              />
              <datalist id="suspicious-ips">
                {suspiciousIps.map((ip) => (
                  <option key={ip.label} value={ip.label}>
                    {ip.value} sessions in last 7 days
                  </option>
                ))}
              </datalist>
              <Input
                label="Reason (Optional)"
                value={blockIpReason}
                onChange={(e) => setBlockIpReason(e.target.value)}
                placeholder="Suspicious login attempts"
                disabled={isSubmitting}
              />
              <Button type="submit" variant="danger" disabled={isSubmitting || !blockIpAddress.trim()}>
                <Ban className="h-4 w-4" />
                Block IP
              </Button>
            </form>

            <div className="rounded-2xl border border-border bg-surface overflow-hidden">
              <div className="px-4 py-3 border-b border-border bg-surface-muted/50">
                <h3 className="text-sm font-semibold text-text">Active Blocks</h3>
              </div>
              {ipBlocks.length === 0 ? (
                <div className="p-8 text-center text-sm text-text-muted">
                  No active IP blocks.
                </div>
              ) : (
                <ul className="divide-y divide-border">
                  {ipBlocks.map((block) => (
                    <li key={block.id} className="flex items-center justify-between p-4 hover:bg-surface-muted/30">
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="font-semibold text-text">{block.ip_address}</p>
                          {!block.is_active && (
                            <span className="rounded bg-surface-muted px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-text-soft">
                              Inactive
                            </span>
                          )}
                        </div>
                        <p className="mt-1 text-sm text-text-soft">{block.reason || "No reason provided"}</p>
                        <p className="mt-1 text-xs text-text-muted">
                          Added {new Date(block.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      {block.is_active && (
                        <Button
                          variant="outline"
                          onClick={() => handleUnblockIp(block.id)}
                          disabled={isSubmitting}
                          className="border-error/30 text-error hover:bg-error-soft"
                        >
                          <Trash2 className="h-4 w-4 mr-2" />
                          Unblock
                        </Button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </Card>
      </section>
    </DashboardLayout>
  );
}

export default SuperadminSettingsPage;
