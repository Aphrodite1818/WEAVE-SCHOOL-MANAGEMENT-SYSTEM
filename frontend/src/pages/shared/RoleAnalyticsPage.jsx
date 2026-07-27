import { BarChart3, LineChart, PieChart, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import AnalyticsBarChart from "../../components/charts/AnalyticsBarChart";
import AnalyticsDonutChart from "../../components/charts/AnalyticsDonutChart";
import AnalyticsLineChart from "../../components/charts/AnalyticsLineChart";
import {
  DashboardMetricCard,
  DashboardSectionHeader,
} from "../../components/dashboard/DashboardPrimitives";
import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
import Card from "../../components/ui/Card";
import { FEATURE_CODES } from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { academicService } from "../../services/academicService";
import { getErrorMessage, isAbortError } from "../../services/api";
import { dashboardService } from "../../services/dashboard.service";

const roleCopy = {
  admin: {
    title: "Advanced Analytics",
    description: "Deeper school performance and operational analytics.",
    load: dashboardService.getTenantAdminAnalytics,
    metricCards: [
      { key: "result_completion_percent", label: "Result completion", suffix: "%" },
      { key: "report_cards_published", label: "Published reports" },
      { key: "student_profiles_incomplete", label: "Incomplete profiles" },
    ],
    charts: [
      { kind: "line", key: "performance_trend", title: "Performance Trend", description: "Average tenant performance by academic term." },
      { kind: "donut", key: "report_card_status", title: "Report Card Status", description: "Generated report-card publishing progress." },
      { kind: "bar", key: "class_population", title: "Class Population", description: "Number of enrolled students in each class." },
      { kind: "bar", key: "subject_performance", title: "Subject Performance", description: "Average score by subject." },
      { kind: "donut", key: "grade_distribution", title: "Grade Distribution", description: "Academic grade distribution." },
    ],
  },
  teacher: {
    title: "Teaching Analytics",
    description: "Teaching performance, class size, and submission signals.",
    load: dashboardService.getTeacherAnalytics,
    metricCards: [
      { key: "result_completion_percent", label: "Score completion", suffix: "%" },
      { key: "pending_score_rows", label: "Pending scores" },
      { key: "result_rows_submitted", label: "Submitted scores" },
    ],
    charts: [
      { kind: "line", key: "performance_trend", title: "Submitted Score Trend", description: "Average submitted score by academic term." },
      { kind: "bar", key: "class_sizes", title: "Subject Class Sizes", description: "Students in assigned subject classes." },
      { kind: "donut", key: "result_status_distribution", title: "Score Status Breakdown", description: "Draft versus submitted scores." },
      { kind: "donut", key: "grade_distribution", title: "Grade Distribution", description: "Grades from submitted results." },
    ],
  },
  student: {
    title: "My Performance",
    description: "Academic performance from finalized results.",
    load: dashboardService.getStudentAnalytics,
    metricCards: [
      { key: "current_average", label: "Current average", suffix: "%" },
      { key: "published_results", label: "Finalized results" },
      { key: "pending_results", label: "Pending results" },
    ],
    charts: [
      { kind: "line", key: "performance_trend", title: "Performance Trend", description: "Average score by academic term." },
      { kind: "bar", key: "subject_comparison", title: "Subject Comparison", description: "Finalized scores by subject." },
      { kind: "donut", key: "grade_distribution", title: "Grade Distribution", description: "Finalized grade spread." },
    ],
  },
};

const chartData = (charts, key) => (Array.isArray(charts?.[key]) ? charts[key] : []);
const formatMetric = (value, suffix = "") =>
  value === null || value === undefined || value === "" ? "-" : `${value}${suffix}`;

const periodLabel = (result) =>
  `${result.academic_session_name || "Session"} / ${String(result.academic_term_name || "Term").replaceAll("_", " ")}`;

const buildStudentAnalytics = (items = []) => {
  const finalized = items.filter((item) => item.status === "locked");
  const pending = items.filter((item) => item.status !== "locked");
  const average = finalized.length
    ? finalized.reduce((sum, item) => sum + Number(item.total_score || 0), 0) / finalized.length
    : 0;
  const byPeriod = new Map();
  const bySubject = new Map();
  const grades = new Map();

  finalized.forEach((item) => {
    const period = periodLabel(item);
    const subject = item.subject_name || item.subject_code || "Subject";
    byPeriod.set(period, [...(byPeriod.get(period) || []), Number(item.total_score || 0)]);
    bySubject.set(subject, [...(bySubject.get(subject) || []), Number(item.total_score || 0)]);
    const grade = item.grade || "Ungraded";
    grades.set(grade, (grades.get(grade) || 0) + 1);
  });

  const averages = (source) =>
    [...source.entries()].map(([label, values]) => ({
      label,
      value: Math.round((values.reduce((sum, value) => sum + value, 0) / values.length) * 100) / 100,
    }));

  return {
    stats: {
      current_average: Math.round(average * 100) / 100,
      published_results: finalized.length,
      pending_results: pending.length,
    },
    charts: {
      performance_trend: averages(byPeriod),
      subject_comparison: averages(bySubject),
      grade_distribution: [...grades.entries()].map(([label, value]) => ({ label, value })),
    },
  };
};

function renderChart(chart, charts) {
  const data = chartData(charts, chart.key);
  if (chart.kind === "donut") {
    return <AnalyticsDonutChart key={chart.key} title={chart.title} description={chart.description} data={data} emptyMessage="No finalized result data is available for this chart yet." />;
  }
  if (chart.kind === "line") {
    return <AnalyticsLineChart key={chart.key} title={chart.title} description={chart.description} data={data} emptyMessage="No finalized result trend is available yet." />;
  }
  return <AnalyticsBarChart key={chart.key} title={chart.title} description={chart.description} data={data} emptyMessage="No finalized result data is available for this chart yet." />;
}

export default function RoleAnalyticsPage({ role = "admin" }) {
  const copy = roleCopy[role] || roleCopy.admin;
  const [analytics, setAnalytics] = useState(null);
  const [error, setError] = useState(null);
  const { getFeatureGuard, isTenantAdmin } = useSubscription();
  const advancedAnalyticsGuard = getFeatureGuard(FEATURE_CODES.ADVANCED_ANALYTICS);
  const shouldGateAdmin = role === "admin" && isTenantAdmin && !advancedAnalyticsGuard.allowed;

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();

    async function loadAnalytics() {
      setError(null);
      try {
        const data = role === "student"
          ? buildStudentAnalytics(
              (await academicService.listMyResults({ signal: controller.signal }))?.items || [],
            )
          : await copy.load({ signal: controller.signal });

        if (!mounted || controller.signal.aborted) return;
        setAnalytics(data);
      } catch (err) {
        if (!mounted || isAbortError(err)) return;
        setError(getErrorMessage(err, "Failed to load analytics."));
      }
    }

    if (!shouldGateAdmin) loadAnalytics();
    return () => {
      mounted = false;
      controller.abort();
    };
  }, [copy, role, shouldGateAdmin]);

  const stats = analytics?.stats || {};
  const charts = analytics?.charts || {};
  const visibleCharts = useMemo(() => copy.charts, [copy.charts]);

  if (shouldGateAdmin) {
    return (
      <DashboardLayout role={role} title="Advanced Analytics">
        <Card className="p-6 sm:p-8">
          <div className="flex max-w-3xl flex-col gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-warning-soft text-amber-950"><Sparkles className="h-5 w-5" /></div>
            <div><h2 className="section-title">Advanced analytics is not active on this plan</h2><p className="mt-2 text-sm leading-6 text-text-muted">Upgrade when deeper analytics are required.</p></div>
          </div>
        </Card>
      </DashboardLayout>
    );
  }

  if (!analytics && !error) {
    return <DashboardLayout role={role} title={copy.title} description={copy.description}><LoadingState label="Loading analytics..." /></DashboardLayout>;
  }

  const trendCharts = visibleCharts.filter((chart) => chart.kind === "line");
  const distributionCharts = visibleCharts.filter((chart) => chart.kind === "donut");
  const comparisonCharts = visibleCharts.filter((chart) => chart.kind === "bar");

  return (
    <DashboardLayout role={role} title={copy.title} description={copy.description}>
      {error ? <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">{error}</div> : null}
      {!error ? (
        <>
          <section className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-3">
            {copy.metricCards.map((metric, index) => (
              <DashboardMetricCard key={metric.key} label={metric.label} value={formatMetric(stats[metric.key], metric.suffix)} description="Academic metric" icon={index === 0 ? BarChart3 : index === 1 ? LineChart : PieChart} tone={index === 0 ? "primary" : index === 1 ? "success" : "warning"} />
            ))}
          </section>
          {trendCharts.length ? <section className="space-y-4"><DashboardSectionHeader title="Trend signals" description="Performance movement across academic periods." /><div className="grid grid-cols-1 gap-5 lg:grid-cols-2">{trendCharts.map((chart) => renderChart(chart, charts))}</div></section> : null}
          {distributionCharts.length ? <section className="space-y-4"><DashboardSectionHeader title="Breakdowns" description="Grade and status distribution." /><div className="grid grid-cols-1 gap-5 lg:grid-cols-2">{distributionCharts.map((chart) => renderChart(chart, charts))}</div></section> : null}
          {comparisonCharts.length ? <section className="space-y-4"><DashboardSectionHeader title="Comparisons" description="Subject and class comparisons." /><div className="grid grid-cols-1 gap-5 lg:grid-cols-2">{comparisonCharts.map((chart) => renderChart(chart, charts))}</div></section> : null}
        </>
      ) : null}
    </DashboardLayout>
  );
}
