import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  KeyRound,
  LockKeyhole,
  Radar,
  RefreshCw,
  Server,
  Shield,
  ShieldAlert,
  Users,
} from "lucide-react";

import AnalyticsBarChart from "../../components/charts/AnalyticsBarChart";
import AnalyticsDonutChart from "../../components/charts/AnalyticsDonutChart";
import AnalyticsLineChart from "../../components/charts/AnalyticsLineChart";
import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import { getErrorMessage } from "../../services/api";
import { superadminService } from "../../services/superadmin.service";
import { cn } from "../../utils/cn";

const metricNumber = (value, fallback = 0) => {
  const nextValue = Number(value);
  return Number.isFinite(nextValue) ? nextValue : fallback;
};

const chartData = (charts, key) => {
  const value = charts?.[key];
  return Array.isArray(value) ? value : [];
};

const riskTone = (score) => {
  if (score >= 75) return "critical";
  if (score >= 50) return "elevated";
  if (score >= 25) return "guarded";
  return "calm";
};

const severityIcon = (severity) => {
  if (severity === "danger") return ShieldAlert;
  if (severity === "warning") return AlertTriangle;
  if (severity === "success") return CheckCircle2;
  return Shield;
};

function SuperadminAnalyticsPage() {
  const [security, setSecurity] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadSecurityAnalytics = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const securityResult = await superadminService.getSecurityOverview();
      setSecurity(securityResult);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load security analytics."));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(loadSecurityAnalytics, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadSecurityAnalytics]);

  const stats = security?.stats || {};
  const charts = security?.charts || {};
  const findings = useMemo(() => (Array.isArray(security?.findings) ? security.findings : []), [security]);

  const riskScore = metricNumber(stats.platform_risk_score);
  const tone = riskTone(riskScore);
  const riskLevel = String(stats.risk_level || tone).replace(/_/g, " ");
  const securityEvents = metricNumber(stats.security_event_count);
  const activeSessions = metricNumber(stats.active_sessions);
  const sessions24h = metricNumber(stats.sessions_last_24h);
  const distinctIps = metricNumber(stats.distinct_login_ips_7d);
  const tokenReuse = metricNumber(stats.refresh_reuse_last_7d);
  const unusualSignals = metricNumber(stats.unusual_login_signals);
  const sessionPressure = metricNumber(stats.session_pressure_score);
  const staleSuperadmins = metricNumber(stats.stale_superadmins);

  const riskIndicators = [
    {
      label: "Platform risk",
      description: `Current posture: ${riskLevel}`,
      value: riskScore,
      tone,
    },
    {
      label: "Session pressure",
      description: `${sessions24h} sessions in the last 24h from ${distinctIps} IPs`,
      value: sessionPressure,
      tone: riskTone(sessionPressure),
    },
    {
      label: "Token reuse pressure",
      description: `${tokenReuse} refresh-token reuse signals in 7 days`,
      value: Math.min(100, tokenReuse * 25),
      tone: tokenReuse > 0 ? "critical" : "calm",
    },
    {
      label: "Unusual login spread",
      description: `${unusualSignals} actors seen from multiple IPs`,
      value: Math.min(100, unusualSignals * 20),
      tone: unusualSignals > 0 ? "elevated" : "calm",
    },
    {
      label: "Admin staleness",
      description: `${staleSuperadmins} stale superadmin accounts`,
      value: Math.min(100, staleSuperadmins * 20),
      tone: staleSuperadmins > 0 ? "guarded" : "calm",
    },
  ];

  if (isLoading && !security && !error) {
    return (
      <DashboardLayout role="superadmin" title="Security Analytics">
        <LoadingState label="Loading security analytics..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="superadmin"
      title="Security Analytics"
      actions={
        <Button variant="outline" onClick={loadSecurityAnalytics} disabled={isLoading}>
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
          <section className="relative overflow-hidden rounded-2xl border border-border bg-surface px-4 py-5 sm:px-6 sm:py-7">
            <div className="relative grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px] xl:items-center">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/30 bg-cyan-300/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-cyan-700 dark:text-cyan-400">
                  <Radar className="h-3.5 w-3.5" />
                  Security Overview
                </div>
                <h2 className="mt-4 max-w-4xl text-2xl font-semibold leading-tight text-text sm:text-3xl">
                  Platform threat monitoring, session activity, and access-control posture.
                </h2>
                <p className="mt-3 max-w-3xl text-sm leading-6 text-text-muted sm:text-base">
                  Critical findings now stay above the fold so compromised sessions, token reuse, and unusual login spread are visible immediately.
                </p>
              </div>

              <div className="rounded-2xl border border-border bg-surface-muted/30 p-4">
                <p className="text-xs font-bold uppercase tracking-wider text-text-muted">Platform risk score</p>
                <div className="mt-4 flex items-end gap-2">
                  <span className="text-4xl font-semibold tracking-tight text-text sm:text-5xl">{riskScore}</span>
                  <span className="pb-1.5 text-base font-semibold text-text-muted">/100</span>
                </div>
                <RiskBar value={riskScore} tone={tone} className="mt-4" />
                <p className="mt-3 text-sm font-semibold capitalize text-text">Current posture: {riskLevel}</p>
              </div>
            </div>
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(320px,0.82fr)_minmax(0,1fr)]">
            <ThreatFindingsCard findings={findings} />
            <RiskIndicatorsCard indicators={riskIndicators} />
          </section>

          <section className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-6">
            <MissionTile label="Security events" value={securityEvents} icon={ShieldAlert} danger={securityEvents > 0} />
            <MissionTile label="Active sessions" value={activeSessions} icon={Server} />
            <MissionTile label="Sessions 24h" value={sessions24h} icon={BarChart3} />
            <MissionTile label="Distinct IPs" value={distinctIps} icon={Radar} />
            <MissionTile label="Token reuse" value={tokenReuse} icon={KeyRound} danger={tokenReuse > 0} />
            <MissionTile label="Unusual actors" value={unusualSignals} icon={Users} danger={unusualSignals > 0} />
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
            <AnalyticsLineChart
              title="Session creation — 7 day trend"
              description="Daily login-session creation across the platform. Spikes here are the first signal of abnormal auth pressure."
              data={chartData(charts, "session_velocity_7d")}
              emptyMessage="No session data available yet."
            />
            <AnalyticsLineChart
              title="Superadmin access velocity"
              description="Daily superadmin login-session creation. This should stay quiet and intentional."
              data={chartData(charts, "superadmin_session_velocity_7d")}
              emptyMessage="No superadmin access velocity data available yet."
            />
          </section>

          <section className="grid gap-5 xl:grid-cols-2">
            <AnalyticsLineChart
              title="Refresh-token reuse pressure"
              description="Daily refresh-token reuse detections. Any non-zero value deserves review."
              data={chartData(charts, "token_reuse_trend_7d")}
              emptyMessage="No token reuse detected."
            />
            <AnalyticsLineChart
              title="Revoked session trend"
              description="Daily session revocations over the last seven days."
              data={chartData(charts, "revoked_session_trend_7d")}
              emptyMessage="No revoked sessions in the current window."
            />
            <AnalyticsBarChart
              title="Risk distribution"
              description="Composite security pressure across sessions, token reuse, unusual spread, and admin drift."
              data={chartData(charts, "risk_vector")}
              emptyMessage="No risk vector data available yet."
            />
            <AnalyticsBarChart
              title="IP concentration radar"
              description="Top source IPs by session creation count in the last seven days."
              data={chartData(charts, "top_login_ips_7d")}
              emptyMessage="No login IP concentration data available yet."
            />
          </section>

          <section className="grid gap-5 xl:grid-cols-3">
            <AnalyticsBarChart
              title="Actor surface area"
              description="Session distribution by actor type across the last seven days."
              data={chartData(charts, "sessions_by_actor_type_7d")}
              emptyMessage="No actor session data available yet."
            />
            <AnalyticsDonutChart
              title="Session integrity"
              description="Active sessions compared with revoked, compromised, and token-reuse signals."
              data={chartData(charts, "security_session_mix")}
              emptyMessage="No session integrity data available yet."
            />
            <AnalyticsDonutChart
              title="Superadmin account posture"
              description="Inactive, never-used, and stale platform-owner accounts."
              data={chartData(charts, "superadmin_account_posture")}
              emptyMessage="No superadmin account posture data available yet."
            />
          </section>

          <section>
            <AnalyticsBarChart
              title="Unusual login spread"
              description="Actors seen from three or more IP addresses within seven days."
              data={chartData(charts, "unusual_login_signals")}
              emptyMessage="No unusual actor/IP spread detected."
            />
          </section>
        </>
      ) : null}
    </DashboardLayout>
  );
}

function ThreatFindingsCard({ findings }) {
  return (
    <Card className="overflow-hidden p-4 sm:p-6">
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-error-soft text-error">
          <LockKeyhole className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-text">Threat findings</h2>
          <p className="text-sm text-text-muted">Highest-priority items from platform security monitoring.</p>
        </div>
      </div>

      <div className="mt-5 grid gap-3">
        {findings.map((finding, index) => {
          const FindingIcon = severityIcon(finding.severity);
          return (
            <div key={`${finding.title}-${index}`} className="rounded-2xl border border-border/60 bg-surface-muted/30 px-4 py-3">
              <div className="flex items-start gap-3">
                <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-surface-muted/50 text-text-soft">
                  <FindingIcon className="h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold text-text">{finding.title}</p>
                    <span className="rounded-full bg-surface-muted px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-text-soft">
                      {finding.severity || "signal"}
                    </span>
                  </div>
                  <p className="mt-1 text-sm leading-6 text-text-muted">{finding.description}</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function RiskIndicatorsCard({ indicators }) {
  return (
    <Card className="p-4 sm:p-6">
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary-soft text-primary">
          <Radar className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-text">Risk indicators</h2>
          <p className="text-sm text-text-muted">Progress-bar style risk view for fast triage.</p>
        </div>
      </div>

      <div className="mt-5 grid gap-4">
        {indicators.map((indicator) => (
          <ProgressRiskRow key={indicator.label} {...indicator} />
        ))}
      </div>
    </Card>
  );
}

function ProgressRiskRow({ label, description, value, tone }) {
  const normalizedValue = Math.min(Math.max(metricNumber(value), 0), 100);

  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-text">{label}</p>
          <p className="mt-0.5 text-xs leading-5 text-text-muted">{description}</p>
        </div>
        <span className="rounded-full border border-border bg-surface-muted/40 px-2.5 py-1 text-xs font-bold text-text-soft">
          {normalizedValue}/100
        </span>
      </div>
      <RiskBar value={normalizedValue} tone={tone} className="mt-2" />
    </div>
  );
}

function RiskBar({ value, tone, className = "" }) {
  return (
    <div className={cn("h-2.5 overflow-hidden rounded-full bg-slate-200/70 dark:bg-white/10", className)}>
      <div
        className={cn(
          "h-full rounded-full transition-all",
          tone === "critical" && "bg-red-500",
          tone === "elevated" && "bg-orange-400",
          tone === "guarded" && "bg-amber-400",
          tone === "calm" && "bg-emerald-400",
        )}
        style={{ width: `${Math.min(Math.max(metricNumber(value), 0), 100)}%` }}
      />
    </div>
  );
}

function MissionTile({ label, value, icon: Icon, danger = false }) {
  return (
    <Card className="overflow-hidden p-3 sm:p-4">
      <div className="flex items-start justify-between gap-3">
        <div className={cn("flex h-10 w-10 items-center justify-center rounded-2xl", danger ? "bg-error-soft text-error" : "bg-primary-soft text-primary")}>
          <Icon className="h-4 w-4" />
        </div>
        {danger ? <span className="rounded-full bg-error-soft px-2 py-1 text-[10px] font-bold text-error">WATCH</span> : null}
      </div>
      <p className="mt-4 text-[11px] font-bold uppercase tracking-wide text-text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-text">{value}</p>
    </Card>
  );
}

export default SuperadminAnalyticsPage;
