import { useCallback, useEffect, useState } from "react";
import {
  Ban,
  CheckCircle2,
  LockKeyhole,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import { useToast } from "../../hooks/useToast";
import { getErrorMessage } from "../../services/api";
import { superadminService } from "../../services/superadmin.service";
import { cn } from "../../utils/cn";

const DEFAULT_MESSAGE = "Weave is temporarily in maintenance mode. Please try again later.";

function SuperadminControlCenterPage() {
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
        superadminService.getSecurityOverview(),
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
      showError(getErrorMessage(err, "Failed to load control center data."));
    } finally {
      setIsLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    const timeoutId = window.setTimeout(loadData, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadData]);

  const lockdownEnabled = Boolean(platformControl?.lockdown_enabled);
  const activeBlockCount = ipBlocks.filter((block) => block.is_active).length;

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
      setLockConfirm("");
      showSuccess("Platform lockdown is active. Non-superadmin traffic is blocked.");
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
      setUnlockConfirm("");
      showSuccess("Platform lockdown has been disabled.");
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
      setBlockIpAddress("");
      setBlockIpReason("");
      showSuccess("IP address has been blocked.");
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
      <DashboardLayout role="superadmin" title="Control Center">
        <LoadingState label="Loading control center..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="superadmin"
      title="Control Center"
      actions={
        <Button variant="outline" onClick={loadData} disabled={isLoading || isSubmitting}>
          <RefreshCw className="h-4 w-4" />
          Refresh state
        </Button>
      }
    >
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between mb-8">
        <div>
           <div className="inline-flex items-center gap-2 rounded-full border border-red-300/30 bg-red-300/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-red-700 dark:text-red-400">
             <ShieldAlert className="h-3.5 w-3.5" />
             Emergency Operations
           </div>
           <h2 className="mt-4 text-2xl font-semibold leading-tight text-text sm:text-3xl">
             Platform Command Center
           </h2>
        </div>
        <div className={cn("rounded-2xl border px-4 py-3 shrink-0 mt-4 lg:mt-0 min-w-[200px]", lockdownEnabled ? "border-error/30 bg-error-soft text-error" : "border-success/30 bg-success-soft text-success")}>
           <div className="flex items-center gap-3">
             {lockdownEnabled ? <LockKeyhole className="h-5 w-5" /> : <CheckCircle2 className="h-5 w-5" />}
             <div>
               <p className="font-semibold">{lockdownEnabled ? "Lockdown active" : "Normal operations"}</p>
               <p className="text-xs opacity-80">{activeBlockCount} active IP block{activeBlockCount === 1 ? "" : "s"}</p>
             </div>
           </div>
        </div>
      </div>

      <section className="grid gap-5 xl:grid-cols-[1fr_1fr] mb-5">
         <Card className="p-4 sm:p-6 h-fit">
            <div className="flex items-center justify-between mb-5">
               <div className="flex items-center gap-3">
                  <div className={cn("flex h-11 w-11 items-center justify-center rounded-2xl", lockdownEnabled ? "bg-error-soft text-error" : "bg-surface-muted text-text-soft")}>
                    <LockKeyhole className="h-5 w-5" />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold text-text">Platform Lockdown</h2>
                    <p className="text-sm text-text-muted">Blocks non-superadmin traffic globally.</p>
                  </div>
               </div>
            </div>

            {!lockdownEnabled ? (
              <form className="grid gap-4 mt-2" onSubmit={handleEnableLockdown}>
                <Input label="Internal Reason" value={reason} onChange={(event) => setReason(event.target.value)} disabled={isSubmitting} />
                <label className="block text-sm font-medium text-text-soft">
                  User-facing maintenance message
                  <textarea className="input-base mt-1.5 min-h-[80px] resize-y" value={message} onChange={(event) => setMessage(event.target.value)} disabled={isSubmitting} />
                </label>
                <div className="flex gap-3 items-end">
                   <div className="flex-1">
                      <Input label="Type LOCKDOWN to confirm" value={lockConfirm} onChange={(event) => setLockConfirm(event.target.value)} placeholder="LOCKDOWN" disabled={isSubmitting} />
                   </div>
                   <Button type="submit" variant="danger" className="mb-0.5" disabled={isSubmitting || lockConfirm !== "LOCKDOWN"}>
                     Activate
                   </Button>
                </div>
              </form>
            ) : (
              <form className="grid gap-4 mt-4" onSubmit={handleDisableLockdown}>
                <div className="rounded-2xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm leading-6 text-warning mb-2">
                   Lockdown is currently active. Tenant and standard platform traffic is blocked.
                </div>
                <div className="flex gap-3 items-end">
                   <div className="flex-1">
                      <Input label="Type UNLOCK to confirm" value={unlockConfirm} onChange={(event) => setUnlockConfirm(event.target.value)} placeholder="UNLOCK" disabled={isSubmitting} />
                   </div>
                   <Button type="submit" variant="success" className="mb-0.5" disabled={isSubmitting || unlockConfirm !== "UNLOCK"}>
                     Restore Normal Operations
                   </Button>
                </div>
              </form>
            )}
         </Card>

         <Card className="p-4 sm:p-6 h-fit">
            <div className="flex items-start gap-3 mb-5">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-warning/10 text-warning shrink-0">
                <Ban className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-text">Network Containment</h2>
                <p className="mt-1 text-sm leading-6 text-text-muted">Block specific IP addresses and review active containment rules.</p>
              </div>
            </div>

            <form onSubmit={handleBlockIp} className="grid gap-3 mb-5">
              <div className="grid grid-cols-2 gap-3">
                 <Input label="IP address" value={blockIpAddress} onChange={(event) => setBlockIpAddress(event.target.value)} placeholder="192.168.1.1" required disabled={isSubmitting} list="suspicious-ips" />
                 <datalist id="suspicious-ips">
                   {suspiciousIps.map((ip) => (
                     <option key={ip.label} value={ip.label}>{ip.value} sessions in 7 days</option>
                   ))}
                 </datalist>
                 <Input label="Reason" value={blockIpReason} onChange={(event) => setBlockIpReason(event.target.value)} placeholder="Suspicious behavior" disabled={isSubmitting} />
              </div>
              <Button type="submit" variant="danger" disabled={isSubmitting || !blockIpAddress.trim()}>
                <Ban className="h-4 w-4" /> Block IP
              </Button>
            </form>

            <div className="max-h-[220px] overflow-y-auto rounded-xl border border-border bg-surface custom-scrollbar">
              {ipBlocks.length === 0 ? (
                <div className="p-4 text-center text-sm text-text-muted">No IP blocks yet.</div>
              ) : (
                <ul className="divide-y divide-border">
                  {ipBlocks.map((block) => (
                    <li key={block.id} className="flex flex-col gap-2 p-3 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="font-semibold text-text text-sm">{block.ip_address}</p>
                          <span className={cn("rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider", block.is_active ? "bg-error-soft text-error" : "bg-surface-muted text-text-soft")}>
                            {block.is_active ? "Active" : "Inactive"}
                          </span>
                        </div>
                        <p className="mt-0.5 text-xs text-text-soft truncate max-w-[200px]">{block.reason || "No reason provided"}</p>
                      </div>
                      {block.is_active ? (
                        <Button variant="outline" onClick={() => handleUnblockIp(block.id)} disabled={isSubmitting} className="border-error/30 text-error hover:bg-error-soft text-xs py-1 h-8">
                          Unblock
                        </Button>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </div>
         </Card>
      </section>
    </DashboardLayout>
  );
}

export default SuperadminControlCenterPage;
