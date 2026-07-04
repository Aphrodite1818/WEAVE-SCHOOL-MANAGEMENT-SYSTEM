import { useCallback, useEffect, useState } from "react";
import { Building2, CheckCircle2, Clock3, RefreshCw, Shield, UserPlus } from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import Badge from "../../components/ui/Badge";
import LoadingState from "../../components/shared/LoadingState";
import StatCard from "../../components/shared/StatCard";
import AnalyticsBarChart from "../../components/charts/AnalyticsBarChart";
import AnalyticsDonutChart from "../../components/charts/AnalyticsDonutChart";
import { getErrorMessage, parseApiError } from "../../services/api";
import { superadminService } from "../../services/superadmin.service";
import { formatPlanName } from "../../features/subscriptions/subscriptionConfig";

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

function SuperadminDashboardPage() {
  const [analytics, setAnalytics] = useState(null);
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
      const [analyticsResult, tenantResult, superadminResult] = await Promise.all([
        superadminService.getAnalyticsOverview(),
        superadminService.getTenants(),
        superadminService.getSuperadmins(),
      ]);

      setAnalytics(analyticsResult);
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

  const activeTenants = analytics?.stats?.active_tenants ?? tenants.filter((tenant) => tenant.status === "active" && !tenant.is_deleted).length;
  const pendingTenants = analytics?.stats?.pending_tenants ?? tenants.filter((tenant) => tenant.verification_status === "pending_verification").length;
  const suspendedTenants = analytics?.stats?.suspended_tenants ?? tenants.filter((tenant) => tenant.status === "suspended").length;
  const totalTenants = analytics?.stats?.total_tenants ?? tenants.length;

  return (
    <DashboardLayout
      role="superadmin"
      title="Platform Dashboard"
      actions={<Button variant="outline" onClick={loadDashboardData} disabled={isLoading}><RefreshCw className="h-4 w-4" />Refresh</Button>}
    >
      {error && <div className="rounded-2xl border border-error/20 bg-error-soft px-4 py-3 text-sm font-medium text-error">{error}</div>}
      {successMessage && <div className="rounded-2xl border border-success/20 bg-success-soft px-4 py-3 text-sm font-medium text-emerald-700">{successMessage}</div>}

      <section className="stat-grid stat-grid-four">
        <StatCard label="Total Schools" value={totalTenants} icon={Building2} tone="primary" description="registered tenants" compact />
        <StatCard label="Active Schools" value={activeTenants} icon={CheckCircle2} tone="success" description="currently active" compact />
        <StatCard label="Pending Schools" value={pendingTenants} icon={Clock3} tone="warning" description="awaiting verification" compact />
        <StatCard label="Suspended Schools" value={suspendedTenants} icon={Shield} tone="error" description="restricted tenants" compact />
      </section>

      <section className="dashboard-grid xl:grid-cols-2">
        <AnalyticsBarChart title="Tenant Growth" description="Growth over time from tenant creation records." data={analytics?.charts?.tenant_growth || []} />
        <AnalyticsDonutChart title="Tenant Status Distribution" description="Active, pending, and suspended schools on the platform." data={analytics?.charts?.tenant_status_distribution || []} emptyMessage="No tenant status analytics available yet." />
        <AnalyticsDonutChart title="Tenant Verification Breakdown" description="Current verification-state counts across tenants." data={analytics?.charts?.tenant_verification_breakdown || []} emptyMessage="No verification analytics available yet." />
        <AnalyticsBarChart title="Subscription Plan Distribution" description="Which subscription plans schools are currently on." data={analytics?.charts?.subscription_plan_distribution || []} emptyMessage="No subscription plan analytics available yet." />
      </section>

      <section className="dashboard-grid xl:grid-cols-[minmax(0,1fr)_min(100%,440px)]">
        <Card className="p-4 sm:p-5 md:p-6">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div><h2 className="section-title">Tenant management</h2><p className="hidden text-sm text-text-muted sm:block">Status, plan, and verification controls.</p></div>
            <Badge variant="primary">{tenants.length} schools</Badge>
          </div>
          {isLoading ? <div className="mt-4 sm:mt-6"><LoadingState label="Loading tenants..." /></div> : (
            <div className="mt-4 table-wrap sm:mt-6">
              <table className="data-table">
                <thead><tr><th>School</th><th>Status</th><th>Plan</th><th>Verification</th></tr></thead>
                <tbody>
                  {tenants.length === 0 ? <tr><td colSpan="4" className="text-text-muted"><span>No tenants found.</span></td></tr> : tenants.map((tenant) => (
                    <tr key={tenant.id}>
                      <td data-label="School"><span><span className="block font-semibold">{tenant.school_name}</span><span className="block text-xs text-text-muted">{tenant.email}</span></span></td>
                      <td data-label="Status"><select value={tenant.status} onChange={(event) => handleStatusChange(tenant.id, event.target.value)} disabled={activeTenantAction === `${tenant.id}:status`} className="input-base w-full max-w-full py-1.5 text-xs capitalize sm:min-w-32">{STATUS_OPTIONS.map((status) => <option key={status} value={status}>{status}</option>)}</select></td>
                      <td className="capitalize" data-label="Plan"><span>{formatPlanName(tenant.plan)}</span></td>
                      <td data-label="Verification"><Badge variant={tenant.verification_status === "verified" ? "success" : "warning"}>{tenant.verification_status?.replace(/_/g, " ") || "pending"}</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <aside className="section-gap">
          <Card className="p-4 sm:p-5 md:p-6">
            <h2 className="section-title">Create tenant</h2>
            <form onSubmit={handleCreateTenant} className="mt-5 space-y-4 sm:mt-6">
              <Input label="School name" name="school_name" value={tenantFormData.school_name} onChange={handleTenantFormChange} required />
              <Input label="Admin email" type="email" name="email" value={tenantFormData.email} onChange={handleTenantFormChange} required />
              <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-1">
                <Input label="Phone" name="phone" value={tenantFormData.phone} onChange={handleTenantFormChange} placeholder="+2348012345678" />
                <Input label="Bot WhatsApp number" name="school_bot_whatssap_number" value={tenantFormData.school_bot_whatssap_number} onChange={handleTenantFormChange} placeholder="+2348012345678" />
              </div>
              <div><label className="mb-1.5 block text-sm font-medium text-text-soft">Plan</label><select name="plan" value={tenantFormData.plan} onChange={handleTenantFormChange} className="input-base">{PLAN_OPTIONS.map((plan) => <option key={plan} value={plan}>{formatPlanName(plan)}</option>)}</select></div>
              <div className="grid gap-4 sm:grid-cols-2"><Input label="Max students" type="number" min="1" name="max_students" value={tenantFormData.max_students} onChange={handleTenantFormChange} required /><Input label="Max teachers" type="number" min="1" name="max_teachers" value={tenantFormData.max_teachers} onChange={handleTenantFormChange} required /></div>
              <Button type="submit" className="w-full" disabled={isCreatingTenant}>{isCreatingTenant ? "Creating..." : "Create tenant"}</Button>
            </form>
          </Card>

          <Card className="p-4 sm:p-5 md:p-6">
            <h2 className="section-title">Invite superadmin</h2>
            <form onSubmit={handleInviteSuperadmin} className="mt-4 space-y-4 sm:mt-5">
              <Input label="Superadmin email" type="email" name="email" value={superadminFormData.email} onChange={handleSuperadminFormChange} error={superadminFieldErrors.email} required />
              <Button type="submit" className="w-full" disabled={isInvitingSuperadmin}><UserPlus className="h-4 w-4" />{isInvitingSuperadmin ? "Sending invite..." : "Invite superadmin"}</Button>
            </form>
          </Card>
        </aside>
      </section>

      <Card className="p-4 sm:p-5 md:p-6">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"><div><h2 className="section-title">Platform administrators</h2><p className="hidden text-sm text-text-muted sm:block">Access status and login activity for platform accounts.</p></div><Badge variant="primary">{superadmins.length} admins</Badge></div>
        {isLoading ? <div className="mt-4 sm:mt-6"><LoadingState label="Loading superadmins..." /></div> : <div className="mt-4 table-wrap sm:mt-6"><table className="data-table"><thead><tr><th>Email</th><th>Status</th><th>Last login</th><th>Created</th></tr></thead><tbody>{superadmins.length === 0 ? <tr><td colSpan="4" className="text-text-muted"><span>No superadmin accounts found.</span></td></tr> : superadmins.map((superadmin) => <tr key={superadmin.id}><td data-label="Email"><span>{superadmin.email}</span></td><td data-label="Status"><Badge variant={superadmin.is_active ? "success" : "default"}>{superadmin.is_active ? "active" : "inactive"}</Badge></td><td data-label="Last login"><span>{superadmin.last_login_at || "Never"}</span></td><td data-label="Created"><span>{superadmin.created_at}</span></td></tr>)}</tbody></table></div>}
      </Card>
    </DashboardLayout>
  );
}

export default SuperadminDashboardPage;
