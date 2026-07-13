import { useCallback, useEffect, useState } from "react";
import { Activity, RefreshCw } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import DashboardLayout from "../../components/layout/DashboardLayout";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import {
  formatLimitValue,
  formatPlanName,
  formatUsageValue,
} from "../../features/subscriptions/subscriptionConfig";
import { getErrorMessage } from "../../services/api";
import { superadminService } from "../../services/superadmin.service";
import { formatChartLabel } from "../../utils/academicDashboard";

const USAGE_FIELDS = [
  { key: "students", label: "Students" },
  { key: "teachers", label: "Teachers" },
  { key: "parents", label: "Parents" },
  { key: "classes", label: "Classes" },
  { key: "subjects", label: "Subjects" },
];

function getUsagePercent(usage) {
  if (!usage || usage.is_unlimited || usage.limit === null || usage.limit === undefined) {
    return null;
  }
  const used = Number(usage.used || 0);
  const limit = Number(usage.limit || 0);
  if (!Number.isFinite(used) || !Number.isFinite(limit) || limit <= 0) return 0;
  return Math.min(100, Math.round((used / limit) * 100));
}

function buildUsageItems(entitlements) {
  return USAGE_FIELDS.map((field) => {
    const usage = entitlements?.usage?.[field.key];
    if (!usage) return null;

    const used = Number(usage.used || 0);
    const limit = usage.limit === null || usage.limit === undefined ? null : Number(usage.limit);

    return {
      ...field,
      usage,
      used: Number.isFinite(used) ? used : 0,
      limit: Number.isFinite(limit) ? limit : null,
      percent: getUsagePercent(usage),
    };
  }).filter(Boolean);
}

function UsageProgressCard({ item }) {
  const percent = item.percent;

  return (
    <div className="usage-progress-card min-w-0 w-full rounded-[1.2rem] border border-border/70 bg-surface-muted/25 px-4 py-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-text">{item.label}</h3>
          <p className="mt-1 text-xs text-text-muted">{formatUsageValue(item.usage)}</p>
        </div>
        <Badge variant={item.usage?.limit_reached ? "warning" : "default"}>
          {item.usage?.is_unlimited ? "Unlimited" : `${percent ?? 0}%`}
        </Badge>
      </div>
      <div className="mt-4 h-2.5 overflow-hidden rounded-full bg-surface-subtle">
        <div
          className="h-full rounded-full bg-primary transition-all"
          style={{ width: item.usage?.is_unlimited ? "100%" : `${percent ?? 0}%` }}
        />
      </div>
      <div className="mt-3 flex items-center justify-between gap-3 text-xs text-text-muted">
        <span>Used: {item.used.toLocaleString()}</span>
        <span>Limit: {formatLimitValue(item.usage?.limit)}</span>
      </div>
    </div>
  );
}

function SuperadminTenantUsagePage() {
  const [tenants, setTenants] = useState([]);
  const [selectedTenantId, setSelectedTenantId] = useState("");
  const [tenantUsage, setTenantUsage] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUsageLoading, setIsUsageLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadTenants = useCallback(async () => {
    setIsLoading(true);
    try {
      const tenantResult = await superadminService.getTenants(0, 100);
      const tenantsList = Array.isArray(tenantResult) ? tenantResult : [];
      setTenants(tenantsList);
      if (tenantsList.length > 0 && !selectedTenantId) {
        setSelectedTenantId(tenantsList[0].id);
      }
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load tenants."));
    } finally {
      setIsLoading(false);
    }
  }, [selectedTenantId]);

  const loadUsage = useCallback(async (tenantId) => {
    if (!tenantId) {
      setTenantUsage(null);
      return;
    }
    setIsUsageLoading(true);
    try {
      setTenantUsage(await superadminService.getTenantUsage(tenantId));
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load tenant usage."));
    } finally {
      setIsUsageLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTenants();
  }, [loadTenants]);

  useEffect(() => {
    if (selectedTenantId) {
      loadUsage(selectedTenantId);
    }
  }, [loadUsage, selectedTenantId]);

  const usageItems = buildUsageItems(tenantUsage?.entitlements);
  const limitedUsageItems = usageItems.filter((item) => item.limit !== null);

  if (isLoading && !tenants.length && !error) {
    return (
      <DashboardLayout role="superadmin" title="Tenant Usage Tracking">
        <LoadingState label="Loading tenant data..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="superadmin"
      title="Tenant Usage Tracking"
      actions={
        <Button variant="outline" onClick={() => selectedTenantId && loadUsage(selectedTenantId)} disabled={isUsageLoading || !selectedTenantId}>
          <RefreshCw className={`h-4 w-4 ${isUsageLoading ? "animate-spin" : ""}`} />
          Refresh usage
        </Button>
      }
    >
      {error ? (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error mb-5">
          {error}
        </div>
      ) : null}

      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between rounded-[1.5rem] border border-border/70 bg-surface p-5 sm:p-6 shadow-sm">
         <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
            <div>
               <h2 className="text-sm font-semibold text-text uppercase tracking-wider">Select Tenant</h2>
               <select
                 className="input-base mt-1.5 min-w-[260px] py-2 text-sm font-medium"
                 value={selectedTenantId}
                 onChange={(event) => setSelectedTenantId(event.target.value)}
               >
                 <option value="">Select a tenant to view limits...</option>
                 {tenants.map((tenant) => (
                   <option key={tenant.id} value={tenant.id}>
                     {tenant.school_name || tenant.email || tenant.id}
                   </option>
                 ))}
               </select>
            </div>
         </div>
         {tenantUsage && !isUsageLoading && (
            <div className="flex flex-wrap items-center gap-4 lg:gap-6 rounded-xl border border-border bg-surface-muted/30 px-5 py-3">
               <div>
                 <p className="text-[10px] uppercase text-text-muted font-bold tracking-wider">School</p>
                 <p className="text-sm font-semibold text-text mt-0.5">{tenantUsage.tenant?.school_name}</p>
               </div>
               <div>
                 <p className="text-[10px] uppercase text-text-muted font-bold tracking-wider">Plan</p>
                 <Badge variant="default" className="mt-0.5">{formatPlanName(tenantUsage.entitlements?.plan)}</Badge>
               </div>
               <div>
                 <p className="text-[10px] uppercase text-text-muted font-bold tracking-wider">Status</p>
                 <Badge variant="primary" className="mt-0.5">{tenantUsage.entitlements?.subscription_status || "unknown"}</Badge>
               </div>
            </div>
         )}
      </div>

      {!selectedTenantId ? (
         <EmptyState
            icon={Activity}
            title="Select a tenant"
            description="Usage cards and charts will appear once a tenant is selected."
         />
      ) : isUsageLoading ? (
         <LoadingState label="Loading tenant usage..." />
      ) : usageItems.length === 0 ? (
        <EmptyState
          icon={Activity}
          title="No usage metrics available"
          description="Usage cards and charts will appear once the backend entitlement response includes resource usage."
        />
      ) : (
        <div className="space-y-5">
          <section className="usage-metrics-grid grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-5">
            {usageItems.map((item) => (
              <UsageProgressCard key={item.key} item={item} />
            ))}
          </section>

          <section className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(320px,0.55fr)]">
            <Card className="min-w-0 flex h-[28rem] flex-col p-5 sm:p-6">
              <div>
                <h2 className="text-lg font-semibold text-text">
                  Limit and actual used
                </h2>
                <p className="mt-1 text-sm text-text-muted">
                  Side-by-side comparison for resources with finite limits.
                </p>
              </div>
              {limitedUsageItems.length > 0 ? (
                <div className="mt-5 min-h-0 flex-1">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={limitedUsageItems}
                      margin={{ left: 0, right: 12, top: 8, bottom: 24 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        vertical={false}
                        stroke="rgba(148, 163, 184, 0.25)"
                      />
                      <XAxis
                        dataKey="label"
                        tickLine={false}
                        axisLine={false}
                        tickMargin={10}
                        tickFormatter={formatChartLabel}
                        angle={-30}
                        textAnchor="end"
                        height={84}
                      />
                      <YAxis
                        allowDecimals={false}
                        tickLine={false}
                        axisLine={false}
                        width={42}
                      />
                      <Tooltip />
                      <Bar dataKey="used" name="Used" fill="#1D4ED8" radius={[10, 10, 0, 0]} />
                      <Bar dataKey="limit" name="Limit" fill="#94A3B8" radius={[10, 10, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="mt-5 flex min-h-0 flex-1 items-center justify-center rounded-2xl border border-dashed border-border bg-surface-muted/40 px-4 py-10 text-center text-sm text-text-muted">
                  All returned resources are unlimited, so there is no finite limit chart to draw.
                </div>
              )}
            </Card>

            <Card className="p-5 sm:p-6">
              <h2 className="text-lg font-semibold text-text">
                Usage table
              </h2>
              <p className="mt-1 text-sm text-text-muted">
                Exact values from the entitlement payload.
              </p>
              <div className="mt-5 divide-y divide-border overflow-hidden rounded-2xl border border-border">
                {usageItems.map((item) => (
                  <div
                    key={item.key}
                    className="grid grid-cols-[1fr_auto] gap-3 px-4 py-3 text-sm"
                  >
                    <div>
                      <p className="font-semibold text-text">
                        {item.label}
                      </p>
                      <p className="mt-0.5 text-xs text-text-muted">
                        Remaining: {formatLimitValue(item.usage?.remaining)}
                      </p>
                    </div>
                    <p className="text-right font-semibold text-text">
                      {formatUsageValue(item.usage)}
                    </p>
                  </div>
                ))}
              </div>
            </Card>
          </section>
        </div>
      )}
    </DashboardLayout>
  );
}

export default SuperadminTenantUsagePage;
