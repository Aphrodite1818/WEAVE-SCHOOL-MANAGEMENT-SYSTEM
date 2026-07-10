import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  Gauge,
  KeyRound,
  LockKeyhole,
  RefreshCw,
  Shield,
  ShieldAlert,
  UserPlus,
  Users,
} from "lucide-react";

import AnalyticsBarChart from "../../components/charts/AnalyticsBarChart";
import AnalyticsDonutChart from "../../components/charts/AnalyticsDonutChart";
import {
  DashboardFocusCard,
  DashboardListCard,
  DashboardMetricCard,
  DashboardQuickActions,
  DashboardWelcomePanel,
} from "../../components/dashboard/DashboardPrimitives";
import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import { formatPlanName } from "../../features/subscriptions/subscriptionConfig";
import { getErrorMessage, parseApiError } from "../../services/api";
import { superadminService } from "../../services/superadmin.service";

const STATUS_OPTIONS = ["active", "inactive", "suspended", "trial", "expired"];
const PLAN_OPTIONS = ["free_trial", "plus", "professional", "enterprise"];

const INITIAL_TENANT_FORM = {
  school_name: "",
  email: "",
  phone: "",
  school_bot_whatssap_number: "",
  plan: "free_trial",
  max_students: 50,
  max_teachers: 10,
};

const INITIAL_SUPERADMIN_FORM = { email: "" };

const toNullable = (value) => {
  const trimmed = String(value || "").trim();
  return trimmed ? trimmed : null;
};

const metricNumber = (value, fallback = 0) => {
  const nextValue = Number(value);
  return Number.isFinite(nextValue) ? nextValue : fallback;
};

const chartData = (charts, key) => {
  const value = charts?.[key];
  return Array.isArray(value) ? value : [];
};

const formatLabel = (value, fallback = "Unknown") => {
  if (!value) return fallback;
  return String(value).replace(/_/g, " ");
};

const formatDateTime = (value) => {
  if (!value) return "Never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const findingTone = (severity) => {
  if (severity === "danger") return "danger";
  if (severity === "warning") return "warning";
  if (severity === "success") return "success";
  return "neutral";
};

const findingIcon = (severity) => {
  if (severity === "danger") return ShieldAlert;
  if (severity === "warning") return AlertTriangle;
  if (severity === "success") return CheckCircle2;
  return Shield;
};

function SuperadminDashboardPage() {
  const [analytics, setAnalytics] = useState(null);
  const [security, setSecurity] = useState(null);
  const [tenants, setTenants] = useState([]);
  const [superadmins, setSuperadmins] = useState([]);
  const [tenantFormData, setTenantFormData] = useState(INITIAL_TENANT_FORM);
  const [superadminFormData, setSuperadminFormData] = useState(INITIAL_SUPERADMIN_FORM);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreatingTenant, setIsCreatingTenant] = useState(false);
  const [isInvitingSuperadmin, setIsInvitingSuperadmin] = useState(false);
  const [activeTenantAction, setActiveTenantAction] = useState(null);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [superadminFieldErrors, setSuperadminFieldErrors] = useState({});

  const loadDashboardData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const [analyticsResult, securityResult, tenantResult, superadminResult] = await Promise.all([
        superadminService.getAnalyticsOverview(),
        superadminService.getSecurityOverview(),
        superadminService.getTenants(),
        superadminService.getSuperadmins(),
      ]);

      setAnalytics(analyticsResult);
      setSecurity(securityResult);
      setTenants(Array.isArray(tenantResult) ? tenantResult : []);
      setSuperadmins(Array.isArray(superadminResult) ? superadminResult : []);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load superadmin data."));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(loadDashboardData, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadDashboardData]);

  const handleTenantFormChange = (event) => {
    const { name, value } = event.target;
    setTenantFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSuperadminFormChange = (event) => {
    const { name, value } = event.target;
    setSuperadminFormData((prev) => ({ ...prev, [name]: value }));
    setSuperadminFieldErrors((prev) => ({ ...prev, [name]: undefined }));
  };

  const handleCreateTenant = async (event) => {
    event.preventDefault();
    setIsCreatingTenant(true);
    setError(null);
    setSuccessMessage(null);

    try {
      await superadminService.createTenant({
        school_name: tenantFormData.school_name,
        email: tenantFormData.email,
        phone: toNullable(tenantFormData.phone),
        school_bot_whatssap_number: toNullable(tenantFormData.school_bot_whatssap_number),
        plan: tenantFormData.plan,
        max_students: Number(tenantFormData.max_students),
        max_teachers: Number(tenantFormData.max_teachers),
      });

      setTenantFormData(INITIAL_TENANT_FORM);
      setSuccessMessage("Tenant created and activation email queued.");
      await loadDashboardData();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to create tenant."));
    } finally {
      setIsCreatingTenant(false);
    }
  };

  const handleInviteSuperadmin = async (event) => {
    event.preventDefault();
    setIsInvitingSuperadmin(true);
    setError(null);
    setSuccessMessage(null);
    setSuperadminFieldErrors({});

    try {
      const result = await superadminService.inviteSuperadmin(superadminFormData);
      setSuperadminFormData(INITIAL_SUPERADMIN_FORM);
      setSuccessMessage(result?.detail || "Superadmin invite created and emailed successfully.");
      await loadDashboardData();
    } catch (err) {
      const apiError = parseApiError(err, "Failed to invite superadmin.");
      if (Object.keys(apiError.fieldErrors).length > 0) {
        setSuperadminFieldErrors(apiError.fieldErrors);
      }
      setError(apiError.message);
    } finally {
      setIsInvitingSuperadmin(false);
    }
  };

  const handleStatusChange = async (tenantId, status) => {
    setActiveTenantAction(`${tenantId}:status`);
    setError(null);
    setSuccessMessage(null);

    try {
      await superadminService.updateTenantStatus(tenantId, {
        status,
        reason: "Updated from the superadmin dashboard.",
      });
      setSuccessMessage("Tenant status updated.");
      await loadDashboardData();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to update tenant status."));
    } finally {
      setActiveTenantAction(null);
    }
  };

  const stats = analytics?.stats || {};
  const charts = analytics?.charts || {};
  const securityStats = security?.stats || {};
  const securityCharts = security?.charts || {};
  const totalTenants = metricNumber(stats.total_tenants, tenants.length);
  const activeTenants = metricNumber(
    stats.active_tenants,
    tenants.filter((tenant) => tenant.status === "active" && !tenant.is_deleted).length,
  );
  const pendingTenants = metricNumber(
    stats.pending_tenants,
    tenants.filter((tenant) => tenant.verification_status === "pending_verification").length,
  );
  const suspendedTenants = metricNumber(
    stats.suspended_tenants,
    tenants.filter((tenant) => tenant.status === "suspended").length,
  );
  const activeSessions = metricNumber(securityStats.active_sessions);
  const securityEvents = metricNumber(securityStats.security_event_count);
  const unusualSignals = metricNumber(securityStats.unusual_login_signals);
  const tokenReuse = metricNumber(securityStats.refresh_reuse_last_7d);
  const neverLoggedInSuperadmins = metricNumber(securityStats.never_logged_in_superadmins);
  const staleSuperadmins = metricNumber(securityStats.stale_superadmins);

  const securityFindings = useMemo(() => {
    const findings = Array.isArray(security?.findings) ? security.findings : [];
    return findings.map((finding, index) => ({
      key: `${finding.title || "finding"}-${index}`,
      title: finding.title || "Security signal",
      description: finding.description || "Review this signal from the platform security telemetry.",
      icon: findingIcon(finding.severity),
      tone: findingTone(finding.severity),
      value: finding.value,
    }));
  }, [security]);

  if (isLoading && !analytics && !error) {
    return (
      <DashboardLayout role="superadmin" title="Platform Dashboard">
        <LoadingState label="Loading platform dashboard..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="superadmin"
      title="Platform Dashboard"
      actions={
        <Button variant="outline" onClick={loadDashboardData} disabled={isLoading}>
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      }
    >
      {error ? (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {error}
        </div>
      ) : null}
      {successMessage ? (
        <div className="rounded-2xl border border-success/20 bg-success-soft px-4 py-3 text-sm font-medium text-emerald-700">
          {successMessage}
        </div>
      ) : null}

      {!error ? (
        <>
          <DashboardWelcomePanel
            eyebrow="Superadmin command center"
            title="Platform health, security, and tenant control"
            description="A cleaner control room for the full product: watch schools, accounts, sessions, token reuse, unusual IP spread, and superadmin access posture."
            chips={[
              { label: "Security events", value: securityEvents, tone: securityEvents > 0 ? "danger" : "success" },
              { label: "Active sessions", value: activeSessions, tone: "primary" },
              { label: "Schools", value: totalTenants, tone: "neutral" },
            ]}
          />

          <section className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
            <DashboardMetricCard
              label="Total schools"
              value={totalTenants}
              description="Registered tenants"
              icon={Building2}
              tone="primary"
            />
            <DashboardMetricCard
              label="Active schools"
              value={activeTenants}
              description="Currently active tenants"
              icon={CheckCircle2}
              tone="success"
            />
            <DashboardMetricCard
              label="Unusual login signals"
              value={unusualSignals}
              description="Actors using 3+ IPs in 7 days"
              icon={ShieldAlert}
              tone={unusualSignals > 0 ? "danger" : "success"}
            />
            <DashboardMetricCard
              label="Token reuse"
              value={tokenReuse}
              description="Refresh-token reuse in 7 days"
              icon={KeyRound}
              tone={tokenReuse > 0 ? "danger" : "success"}
            />
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.85fr)]">
            <DashboardFocusCard
              title="Security control room"
              description="Session and account signals that deserve platform-owner attention. These come from auth session records, refresh-token reuse markers, and superadmin account state."
              icon={Shield}
              tone={securityEvents > 0 ? "danger" : "success"}
            >
              <div className="grid grid-cols-2 gap-3">
                <InfoTile label="Sessions in 24h" value={metricNumber(securityStats.sessions_last_24h)} />
                <InfoTile label="Superadmin sessions" value={metricNumber(securityStats.superadmin_sessions_last_24h)} />
                <InfoTile label="Compromised sessions" value={metricNumber(securityStats.compromised_sessions)} />
                <InfoTile label="Revoked in 7d" value={metricNumber(securityStats.revoked_sessions_last_7d)} />
              </div>
            </DashboardFocusCard>

            <DashboardListCard
              title="Security findings"
              description="Prioritized superadmin items, with the highest-risk session issues first."
              items={securityFindings}
              emptyTitle="Security posture looks calm"
              emptyDescription="No compromised sessions, token reuse, or unusual IP spread is currently visible."
            />
          </section>

          <section className="grid gap-5 xl:grid-cols-2">
            <AnalyticsBarChart
              title="Sessions by actor type"
              description="Login sessions created over the last seven days."
              data={chartData(securityCharts, "sessions_by_actor_type_7d")}
              emptyMessage="No session activity available yet."
            />
            <AnalyticsDonutChart
              title="Security session mix"
              description="Active sessions versus revoked, compromised, and token-reuse signals."
              data={chartData(securityCharts, "security_session_mix")}
              emptyMessage="No security session data available yet."
            />
            <AnalyticsBarChart
              title="Top login IPs"
              description="Most active source IPs across the last seven days."
              data={chartData(securityCharts, "top_login_ips_7d")}
              emptyMessage="No login IP data available yet."
            />
            <AnalyticsBarChart
              title="Unusual login spread"
              description="Actors using three or more IP addresses in seven days."
              data={chartData(securityCharts, "unusual_login_signals")}
              emptyMessage="No unusual login spread detected."
            />
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.85fr)]">
            <DashboardFocusCard
              title="Platform operations"
              description="Tenant status, verification, and subscription posture."
              icon={Gauge}
              tone="primary"
            >
              <div className="grid grid-cols-2 gap-3">
                <InfoTile label="Pending schools" value={pendingTenants} />
                <InfoTile label="Suspended schools" value={suspendedTenants} />
                <InfoTile label="Unused admins" value={neverLoggedInSuperadmins} />
                <InfoTile label="Stale admins" value={staleSuperadmins} />
              </div>
            </DashboardFocusCard>

            <DashboardQuickActions
              title="Superadmin actions"
              description="Core platform-owner workflows."
              actions={[
                { label: "Create tenant", description: "Provision a school workspace", onClick: () => document.getElementById("create-tenant-card")?.scrollIntoView({ behavior: "smooth", block: "start" }), icon: Building2, tone: "primary" },
                { label: "Invite superadmin", description: "Add a platform operator", onClick: () => document.getElementById("invite-superadmin-card")?.scrollIntoView({ behavior: "smooth", block: "start" }), icon: UserPlus, tone: "success" },
                { label: "Review tenants", description: "Audit school status", onClick: () => document.getElementById("tenant-management-card")?.scrollIntoView({ behavior: "smooth", block: "start" }), icon: Users, tone: "warning" },
                { label: "Security review", description: "Check auth session signals", onClick: () => window.scrollTo({ top: 0, behavior: "smooth" }), icon: LockKeyhole, tone: "danger" },
              ]}
            />
          </section>

          <section className="grid gap-5 xl:grid-cols-2">
            <AnalyticsBarChart
              title="Tenant growth"
              description="Growth over time from tenant creation records."
              data={chartData(charts, "tenant_growth")}
              emptyMessage="No tenant growth data available yet."
            />
            <AnalyticsDonutChart
              title="Tenant status distribution"
              description="Active, pending, and suspended schools on the platform."
              data={chartData(charts, "tenant_status_distribution")}
              emptyMessage="No tenant status analytics available yet."
            />
            <AnalyticsDonutChart
              title="Tenant verification breakdown"
              description="Current verification-state counts across tenants."
              data={chartData(charts, "tenant_verification_breakdown")}
              emptyMessage="No verification analytics available yet."
            />
            <AnalyticsBarChart
              title="Subscription plan distribution"
              description="Which subscription plans schools are currently on."
              data={chartData(charts, "subscription_plan_distribution")}
              emptyMessage="No subscription plan analytics available yet."
            />
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_min(100%,440px)]">
            <Card id="tenant-management-card" className="p-4 sm:p-5 md:p-6">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="section-title">Tenant management</h2>
                  <p className="hidden text-sm text-text-muted sm:block">Status, plan, and verification controls.</p>
                </div>
                <Badge variant="primary">{tenants.length} schools</Badge>
              </div>
              {isLoading ? (
                <div className="mt-4 sm:mt-6"><LoadingState label="Loading tenants..." /></div>
              ) : (
                <div className="mt-4 table-wrap sm:mt-6">
                  <table className="data-table">
                    <thead><tr><th>School</th><th>Status</th><th>Plan</th><th>Verification</th></tr></thead>
                    <tbody>
                      {tenants.length === 0 ? (
                        <tr><td colSpan="4" className="text-text-muted"><span>No tenants found.</span></td></tr>
                      ) : tenants.map((tenant) => (
                        <tr key={tenant.id}>
                          <td data-label="School">
                            <span>
                              <span className="block font-semibold">{tenant.school_name}</span>
                              <span className="block text-xs text-text-muted">{tenant.email}</span>
                            </span>
                          </td>
                          <td data-label="Status">
                            <select
                              value={tenant.status}
                              onChange={(event) => handleStatusChange(tenant.id, event.target.value)}
                              disabled={activeTenantAction === `${tenant.id}:status`}
                              className="input-base w-full max-w-full py-1.5 text-xs capitalize sm:min-w-32"
                            >
                              {STATUS_OPTIONS.map((status) => <option key={status} value={status}>{status}</option>)}
                            </select>
                          </td>
                          <td className="capitalize" data-label="Plan"><span>{formatPlanName(tenant.plan)}</span></td>
                          <td data-label="Verification">
                            <Badge variant={tenant.verification_status === "verified" || tenant.verification_status === "active" ? "success" : "warning"}>
                              {formatLabel(tenant.verification_status, "pending")}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>

            <aside className="section-gap">
              <Card id="create-tenant-card" className="p-4 sm:p-5 md:p-6">
                <h2 className="section-title">Create tenant</h2>
                <form onSubmit={handleCreateTenant} className="mt-5 space-y-4 sm:mt-6">
                  <Input label="School name" name="school_name" value={tenantFormData.school_name} onChange={handleTenantFormChange} required />
                  <Input label="Admin email" type="email" name="email" value={tenantFormData.email} onChange={handleTenantFormChange} required />
                  <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-1">
                    <Input label="Phone" name="phone" value={tenantFormData.phone} onChange={handleTenantFormChange} placeholder="+2348012345678" />
                    <Input label="Bot WhatsApp number" name="school_bot_whatssap_number" value={tenantFormData.school_bot_whatssap_number} onChange={handleTenantFormChange} placeholder="+2348012345678" />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-sm font-medium text-text-soft">Plan</label>
                    <select name="plan" value={tenantFormData.plan} onChange={handleTenantFormChange} className="input-base">
                      {PLAN_OPTIONS.map((plan) => <option key={plan} value={plan}>{formatPlanName(plan)}</option>)}
                    </select>
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Input label="Max students" type="number" min="1" name="max_students" value={tenantFormData.max_students} onChange={handleTenantFormChange} required />
                    <Input label="Max teachers" type="number" min="1" name="max_teachers" value={tenantFormData.max_teachers} onChange={handleTenantFormChange} required />
                  </div>
                  <Button type="submit" className="w-full" disabled={isCreatingTenant}>{isCreatingTenant ? "Creating..." : "Create tenant"}</Button>
                </form>
              </Card>

              <Card id="invite-superadmin-card" className="p-4 sm:p-5 md:p-6">
                <h2 className="section-title">Invite superadmin</h2>
                <form onSubmit={handleInviteSuperadmin} className="mt-4 space-y-4 sm:mt-5">
                  <Input label="Superadmin email" type="email" name="email" value={superadminFormData.email} onChange={handleSuperadminFormChange} error={superadminFieldErrors.email} required />
                  <Button type="submit" className="w-full" disabled={isInvitingSuperadmin}>
                    <UserPlus className="h-4 w-4" />
                    {isInvitingSuperadmin ? "Sending invite..." : "Invite superadmin"}
                  </Button>
                </form>
              </Card>
            </aside>
          </section>

          <Card className="p-4 sm:p-5 md:p-6">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="section-title">Platform administrators</h2>
                <p className="hidden text-sm text-text-muted sm:block">Access status and login activity for platform accounts.</p>
              </div>
              <Badge variant="primary">{superadmins.length} admins</Badge>
            </div>
            {isLoading ? (
              <div className="mt-4 sm:mt-6"><LoadingState label="Loading superadmins..." /></div>
            ) : (
              <div className="mt-4 table-wrap sm:mt-6">
                <table className="data-table">
                  <thead><tr><th>Email</th><th>Status</th><th>Last login</th><th>Created</th></tr></thead>
                  <tbody>
                    {superadmins.length === 0 ? (
                      <tr><td colSpan="4" className="text-text-muted"><span>No superadmin accounts found.</span></td></tr>
                    ) : superadmins.map((superadmin) => (
                      <tr key={superadmin.id}>
                        <td data-label="Email"><span>{superadmin.email}</span></td>
                        <td data-label="Status"><Badge variant={superadmin.is_active ? "success" : "default"}>{superadmin.is_active ? "active" : "inactive"}</Badge></td>
                        <td data-label="Last login"><span>{formatDateTime(superadmin.last_login_at)}</span></td>
                        <td data-label="Created"><span>{formatDateTime(superadmin.created_at)}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      ) : null}
    </DashboardLayout>
  );
}

function InfoTile({ label, value }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-surface-muted/20 px-3 py-3 sm:px-4">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-text-muted sm:text-[11px]">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-text">{value}</p>
    </div>
  );
}

export default SuperadminDashboardPage;
