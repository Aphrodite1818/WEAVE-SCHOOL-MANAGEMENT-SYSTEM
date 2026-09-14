import { useCallback, useEffect, useState } from "react";
import { Activity, Server, Shield } from "lucide-react";

import AnalyticsDonutChart from "../../components/charts/AnalyticsDonutChart";
import AnalyticsLineChart from "../../components/charts/AnalyticsLineChart";
import DashboardLayout from "../../components/layout/DashboardLayout";
import { DashboardMetricCard } from "../../components/dashboard/DashboardPrimitives";
import LoadingState from "../../components/shared/LoadingState";
import { getErrorMessage } from "../../services/api";
import { superadminService } from "../../services/superadmin.service";

const metricNumber = (value, fallback = 0) => {
  const nextValue = Number(value);
  return Number.isFinite(nextValue) ? nextValue : fallback;
};

const formatChartData = (data = []) => {
  if (!Array.isArray(data)) return [];
  return data.map(item => ({
    label: item.period || item.actor_type || "Unknown",
    value: item.value || 0
  }));
};

function SuperadminTrafficMonitorPage() {
  const [securityData, setSecurityData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await superadminService.getSecurityOverview();
      setSecurityData(data);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load traffic data."));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(loadData, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadData]);

  const stats = securityData?.stats || {};
  const charts = securityData?.charts || {};

  const activeSessions = metricNumber(stats.active_sessions);
  const sessions24h = metricNumber(stats.sessions_last_24h);
  const distinctIps = metricNumber(stats.distinct_login_ips_7d);

  if (isLoading && !securityData && !error) {
    return (
      <DashboardLayout role="superadmin" title="Traffic Monitor">
        <LoadingState label="Loading traffic data..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="superadmin"
      title="Traffic Monitor"
    >
      {error && (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error mb-5">
          {error}
        </div>
      )}

      <div className="mb-6">
         <h1 className="text-2xl font-semibold text-text mb-2">Platform Traffic Overview</h1>
         <p className="text-sm text-text-muted">
            Monitor real-time active sessions and login trends to understand platform utilization.
         </p>
      </div>

      <section className="grid grid-cols-2 gap-4 sm:grid-cols-3 mb-6">
        <DashboardMetricCard
          label="Active Sessions"
          value={activeSessions}
          description="Currently valid auth tokens"
          icon={Activity}
          tone="success"
        />
        <DashboardMetricCard
          label="Logins (24h)"
          value={sessions24h}
          description="Total sessions created today"
          icon={Server}
          tone="primary"
        />
        <DashboardMetricCard
          label="Distinct IPs (7d)"
          value={distinctIps}
          description="Unique networks accessing the app"
          icon={Shield}
          tone="neutral"
        />
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,1fr)]">
        <AnalyticsLineChart
          title="Authentication Traffic (7 Days)"
          description="Daily login volume across all users."
          data={formatChartData(charts.session_velocity_7d)}
          emptyMessage="No traffic data recorded in the last 7 days."
        />
        <AnalyticsDonutChart
          title="Traffic by Actor Type"
          description="Session breakdown by user roles."
          data={formatChartData(charts.sessions_by_actor_type_7d)}
          emptyMessage="No actor distribution data available."
        />
      </section>
    </DashboardLayout>
  );
}

export default SuperadminTrafficMonitorPage;
