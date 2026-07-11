import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  KeyRound,
  LockKeyhole,
  RefreshCw,
  Shield,
  ShieldAlert,
  Users,
} from "lucide-react";

import {
  DashboardFocusCard,
  DashboardListCard,
  DashboardMetricCard,
  DashboardQuickActions,
  DashboardWelcomePanel,
} from "../../components/dashboard/DashboardPrimitives";
import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
import Button from "../../components/ui/Button";
import { getErrorMessage } from "../../services/api";
import { superadminService } from "../../services/superadmin.service";

const metricNumber = (value, fallback = 0) => {
  const nextValue = Number(value);
  return Number.isFinite(nextValue) ? nextValue : fallback;
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
  const [platformControl, setPlatformControl] = useState(null);
  const [tenants, setTenants] = useState([]);
  const [superadmins, setSuperadmins] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadDashboardData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const [analyticsResult, securityResult, platformControlResult, tenantResult, superadminResult] = await Promise.all([
        superadminService.getAnalyticsOverview(),
        superadminService.getSecurityOverview(),
        superadminService.getPlatformControl(),
        superadminService.getTenants(0, 8),
        superadminService.getSuperadmins(0, 8),
      ]);

      setAnalytics(analyticsResult);
      setSecurity(securityResult);
      setPlatformControl(platformControlResult);
      setTenants(Array.isArray(tenantResult) ? tenantResult : []);
      setSuperadmins(Array.isArray(superadminResult) ? superadminResult : []);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load dashboard data."));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(loadDashboardData, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadDashboardData]);

  const stats = analytics?.stats || {};
  const securityStats = security?.stats || {};
  const lockdownEnabled = Boolean(platformControl?.lockdown_enabled);
  const totalTenants = metricNumber(stats.total_tenants, tenants.length);
  const activeTenants = metricNumber(stats.active_tenants);
  const pendingTenants = metricNumber(stats.pending_tenants ?? stats.pending_verification);
  const activeSessions = metricNumber(securityStats.active_sessions);
  const securityEvents = metricNumber(securityStats.security_event_count);
  const riskScore = metricNumber(securityStats.platform_risk_score);
  const riskLevel = String(securityStats.risk_level || "calm").replace(/_/g, " ");
  const tokenReuse = metricNumber(securityStats.refresh_reuse_last_7d);
  const unusualSignals = metricNumber(securityStats.unusual_login_signals);
  const distinctIps = metricNumber(securityStats.distinct_login_ips_7d);

  const securityFindings = useMemo(() => {
    const findings = Array.isArray(security?.findings) ? security.findings : [];
    return findings.slice(0, 4).map((finding, index) => ({
      key: `${finding.title || "finding"}-${index}`,
      title: finding.title || "Security signal",
      description: finding.description || "Review this signal from the platform security telemetry.",
      icon: findingIcon(finding.severity),
      tone: findingTone(finding.severity),
      value: finding.value,
      to: "/superadmin/analytics",
    }));
  }, [security]);

  if (isLoading && !analytics && !error) {
    return (
      <DashboardLayout role="superadmin" title="Dashboard">
        <LoadingState label="Loading dashboard data..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="superadmin"
      title="Dashboard"
      actions={
        <Button variant="outline" onClick={loadDashboardData} disabled={isLoading}>
          <RefreshCw className="h-4 w-4" />
          Refresh data
        </Button>
      }
    >
      {error ? (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {error}
        </div>
      ) : null}

      {!error ? (
        <>
          <DashboardWelcomePanel
            eyebrow="Superadmin Overview"
            title="Platform Status & Security Posture"
            description="Monitor key security metrics and manage active schools across the platform."
            chips={[
              { label: "Status", value: lockdownEnabled ? "Lockdown active" : "Normal", tone: lockdownEnabled ? "danger" : "success" },
              { label: "Risk Score", value: `${riskScore}/100 · ${riskLevel}`, tone: riskScore >= 50 ? "danger" : riskScore > 0 ? "warning" : "success" },
              { label: "Total Schools", value: totalTenants, tone: "neutral" },
            ]}
          />

          <section className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
            <DashboardMetricCard
              label="Platform mode"
              value={lockdownEnabled ? "Locked" : "Normal"}
              description={lockdownEnabled ? "Only superadmin traffic is allowed" : "All authorized traffic is allowed"}
              icon={LockKeyhole}
              tone={lockdownEnabled ? "danger" : "success"}
              to="/superadmin/settings"
            />
            <DashboardMetricCard
              label="Platform risk score"
              value={`${riskScore}/100`}
              description={`Current posture: ${riskLevel}`}
              icon={ShieldAlert}
              tone={riskScore >= 50 ? "danger" : riskScore > 0 ? "warning" : "success"}
              to="/superadmin/analytics"
            />
            <DashboardMetricCard
              label="Security alerts"
              value={securityEvents}
              description="Critical security events in the last 7 days"
              icon={LockKeyhole}
              tone={securityEvents > 0 ? "danger" : "success"}
              to="/superadmin/analytics"
            />
            <DashboardMetricCard
              label="Active sessions"
              value={activeSessions}
              description={`${distinctIps} IPs observed in 7 days`}
              icon={Activity}
              tone="accent"
              to="/superadmin/analytics"
            />
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.85fr)]">
            <DashboardListCard
              title="Recent security findings"
              description="Highest priority alerts from the platform security monitoring."
              items={securityFindings}
              emptyTitle="No security issues detected"
              emptyDescription="There are no active security alerts or compromised sessions to review."
            />

            <DashboardFocusCard
              title={lockdownEnabled ? "Platform Lockdown Active" : "Platform Controls"}
              description={
                lockdownEnabled
                  ? "Non-admin access is currently blocked. Users will see a maintenance message."
                  : "Manage platform lockdown and emergency settings."
              }
              icon={Shield}
              tone={lockdownEnabled ? "danger" : "success"}
              primaryAction={{ to: "/superadmin/settings", label: lockdownEnabled ? "Manage Lockdown" : "Platform Settings", icon: KeyRound }}
              secondaryAction={{ to: "/superadmin/analytics", label: "Security analytics", icon: BarChart3 }}
            >
              <div className="grid grid-cols-2 gap-3">
                <InfoTile label="Token reuse" value={tokenReuse} />
                <InfoTile label="Unusual actors" value={unusualSignals} />
                <InfoTile label="Sessions 24h" value={metricNumber(securityStats.sessions_last_24h)} />
                <InfoTile label="Superadmin 24h" value={metricNumber(securityStats.superadmin_sessions_last_24h)} />
              </div>
            </DashboardFocusCard>
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(320px,1fr)]">
            <DashboardFocusCard
              title="School Management"
              description="Quick overview of active schools and platform administrators."
              icon={GaugeIcon}
              tone="primary"
            >
              <div className="grid grid-cols-2 gap-3">
                <InfoTile label="Total schools" value={totalTenants} />
                <InfoTile label="Active schools" value={activeTenants} />
                <InfoTile label="Loaded admins" value={superadmins.length} />
                <InfoTile label="Pending schools" value={pendingTenants} />
              </div>
            </DashboardFocusCard>

            <DashboardQuickActions
              title="Quick Actions"
              description="Access commonly used platform management tools."
              actions={[
                { label: "Security Analytics", description: "View detailed security metrics", to: "/superadmin/analytics", icon: BarChart3, tone: "danger" },
                { label: "Platform Settings", description: "Lockdown and platform configuration", to: "/superadmin/settings", icon: KeyRound, tone: lockdownEnabled ? "danger" : "neutral" },
                { label: "School Verification", description: "Review and approve school registrations", to: "/superadmin/verification", icon: Shield, tone: "primary" },
                { label: "Audit Logs", description: "View recent platform activity", to: "/superadmin/activity", icon: Activity, tone: "accent" },
              ]}
            />
          </section>
        </>
      ) : null}
    </DashboardLayout>
  );
}

function GaugeIcon(props) {
  return <Users {...props} />;
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
