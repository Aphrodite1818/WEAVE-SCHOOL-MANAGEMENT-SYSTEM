import {
  BarChart3,
  Bell,
  BookOpen,
  CheckCircle2,
  FileText,
  GraduationCap,
  LineChart,
  PieChart,
  TrendingDown,
  TrendingUp,
  Users,
} from "lucide-react";
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
import { getErrorMessage, isAbortError } from "../../services/api";
import { dashboardService } from "../../services/dashboard.service";
import { formatChartLabel } from "../../utils/academicDashboard";

const roleCopy = {
  admin: {
    title: "Advanced Analytics",
    description: "School performance, result completion, and publishing progress.",
    load: dashboardService.getTenantAdminAnalytics,
    insightLabel: "School performance",
    trendKey: "performance_trend",
    metricCards: [
      { key: "result_completion_percent", label: "Result completion", suffix: "%", icon: CheckCircle2, tone: "success", description: "Submitted result rows" },
      { key: "result_rows_submitted", label: "Submitted results", icon: FileText, tone: "primary", description: "Rows submitted by staff" },
      { key: "report_cards_published", label: "Published reports", icon: BookOpen, tone: "accent", description: "Report cards released" },
      { key: "student_profiles_incomplete", label: "Incomplete profiles", icon: Users, tone: "warning", description: "Student records needing review" },
    ],
    charts: [
      { kind: "line", key: "performance_trend", title: "Performance trend", description: "Average school performance by academic term.", featured: true },
      { kind: "donut", key: "report_card_status", title: "Report card status", description: "Generated report-card publishing progress." },
      { kind: "bar", key: "class_population", title: "Class population", description: "Enrolled students in each class." },
      { kind: "bar", key: "subject_performance", title: "Subject performance", description: "Average score by subject." },
      { kind: "donut", key: "grade_distribution", title: "Grade distribution", description: "Grades from submitted results." },
    ],
  },
  teacher: {
    title: "Teaching Analytics",
    description: "Read-only academic performance across your assigned classes and subjects.",
    load: dashboardService.getTeacherAnalytics,
    insightLabel: "Finalized result average",
    trendKey: "performance_trend",
    metricCards: [
      { key: "result_completion_percent", label: "Result availability", suffix: "%", icon: CheckCircle2, tone: "success", description: "Academic result rows available for review" },
      { key: "pending_score_rows", label: "Pending result rows", icon: FileText, tone: "warning", description: "Result rows not finalized by the school yet" },
      { key: "result_rows_submitted", label: "Finalized result rows", icon: BarChart3, tone: "primary", description: "Completed academic result rows visible to you" },
      { key: "assigned_subjects", label: "Assignments", icon: BookOpen, tone: "accent", description: "Active teaching assignments" },
    ],
    charts: [
      { kind: "line", key: "performance_trend", title: "Academic performance trend", description: "Average finalized performance by academic term.", featured: true },
      { kind: "bar", key: "class_sizes", title: "Subject class sizes", description: "Students in assigned subject classes." },
      { kind: "donut", key: "result_status_distribution", title: "Result status", description: "Academic result rows by current lifecycle state." },
      { kind: "donut", key: "grade_distribution", title: "Grade distribution", description: "Grades from finalized academic results." },
    ],
  },
  student: {
    title: "My Performance",
    description: "Your finalized results and subject performance over time.",
    load: dashboardService.getStudentAnalytics,
    insightLabel: "Your average score",
    trendKey: "performance_trend",
    metricCards: [
      { key: "current_average", label: "Current average", suffix: "%", icon: TrendingUp, tone: "success", description: "Finalized result average" },
      { key: "published_results", label: "Finalized results", icon: CheckCircle2, tone: "primary", description: "Results available to you" },
      { key: "pending_results", label: "Pending results", icon: FileText, tone: "warning", description: "Results not finalized yet" },
      { key: "result_completion_percent", label: "Result availability", suffix: "%", icon: PieChart, tone: "accent", description: "Finalized result rows" },
    ],
    charts: [
      { kind: "line", key: "performance_trend", title: "Performance trend", description: "Average finalized score by academic term.", featured: true },
      { kind: "bar", key: "subject_comparison", title: "Subject comparison", description: "Average finalized score by subject." },
      { kind: "donut", key: "grade_distribution", title: "Grade distribution", description: "Your finalized grade spread." },
    ],
  },
  parent: {
    title: "Family Insights",
    description: "Linked-student access and school communication activity.",
    load: dashboardService.getParentAnalytics,
    insightLabel: "Family account overview",
    metricCards: [
      { key: "linked_students", label: "Linked students", icon: GraduationCap, tone: "primary", description: "Students available in this school" },
      { key: "primary_contacts", label: "Primary contacts", icon: Users, tone: "success", description: "Primary-contact relationships" },
      { key: "unread_count", label: "Unread updates", icon: Bell, tone: "warning", description: "School notifications to review" },
      { key: "feed_total", label: "All updates", icon: FileText, tone: "accent", description: "Notifications in your feed" },
    ],
    charts: [
      { kind: "donut", key: "announcement_read_vs_unread", title: "Notification status", description: "Read and unread school updates.", featured: true },
      { kind: "bar", key: "announcement_category_breakdown", title: "Update categories", description: "School updates grouped by category." },
    ],
  },
};

const chartData = (charts, key) => (Array.isArray(charts?.[key]) ? charts[key] : []);

const formatMetric = (value, suffix = "") =>
  value === null || value === undefined || value === "" ? "-" : `${value}${suffix}`;

const getTrendInsight = (data, label) => {
  if (!Array.isArray(data) || data.length === 0) {
    return { title: `${label} is awaiting data`, detail: "Analytics will appear after finalized records are available.", tone: "neutral", icon: LineChart };
  }

  const latest = data.at(-1);
  const previous = data.at(-2);
  const latestValue = Number(latest?.value);
  const previousValue = Number(previous?.value);

  if (!Number.isFinite(latestValue) || !Number.isFinite(previousValue)) {
    return { title: `${label}: ${formatMetric(latest?.value)}`, detail: `Latest available period: ${formatChartLabel(latest?.label, "Current period")}.`, tone: "neutral", icon: LineChart };
  }

  const difference = Math.round((latestValue - previousValue) * 100) / 100;
  const improved = difference >= 0;
  return {
    title: difference === 0 ? `${label} held steady` : `${label} ${improved ? "improved" : "declined"}`,
    detail: `${improved ? "Up" : "Down"} ${Math.abs(difference)} points from ${formatChartLabel(previous?.label, "the previous period")} to ${formatMetric(latestValue)} in ${formatChartLabel(latest?.label, "the latest period")}.`,
    tone: difference === 0 ? "neutral" : improved ? "success" : "warning",
    icon: difference === 0 ? LineChart : improved ? TrendingUp : TrendingDown,
  };
};

const getSnapshotInsight = (role, stats) => {
  if (role !== "parent") return null;

  const linkedStudents = Number(stats.linked_students) || 0;
  const unreadUpdates = Number(stats.unread_count) || 0;
  return {
    title: `${linkedStudents} linked student${linkedStudents === 1 ? "" : "s"} in this school`,
    detail: unreadUpdates > 0
      ? `${unreadUpdates} school update${unreadUpdates === 1 ? "" : "s"} still need${unreadUpdates === 1 ? "s" : ""} your attention.`
      : "There are no unread school updates waiting for you.",
    tone: unreadUpdates > 0 ? "warning" : "success",
    icon: unreadUpdates > 0 ? Bell : CheckCircle2,
  };
};

function renderChart(chart, charts) {
  const data = chartData(charts, chart.key);
  const commonProps = {
    key: chart.key,
    title: chart.title,
    description: chart.description,
    data,
    emptyMessage: "No finalized data is available for this chart yet.",
  };

  if (chart.kind === "donut") return <AnalyticsDonutChart {...commonProps} />;
  if (chart.kind === "line") return <AnalyticsLineChart {...commonProps} />;
  return <AnalyticsBarChart {...commonProps} />;
}

function AnalyticsInsight({ insight }) {
  const Icon = insight.icon;
  const toneClasses = {
    success: "border-success/20 bg-success-soft text-success",
    warning: "border-warning/30 bg-warning-soft text-amber-950",
    neutral: "border-primary/20 bg-primary-subtle text-primary",
  };

  return (
    <section className="analytics-insight-card rounded-[1.5rem] border border-border bg-surface px-4 py-5 sm:px-6 sm:py-6 lg:px-8">
      <div className="flex items-start gap-4 sm:items-center">
        <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border sm:h-14 sm:w-14 ${toneClasses[insight.tone] || toneClasses.neutral}`}>
          <Icon className="h-6 w-6" />
        </div>
        <div className="min-w-0">
          <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-text-muted">Latest signal</p>
          <h2 className="mt-1 text-xl font-semibold leading-tight text-text sm:text-2xl">{insight.title}</h2>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-text-muted">{insight.detail}</p>
        </div>
      </div>
    </section>
  );
}

export default function RoleAnalyticsPage({ role = "admin" }) {
  const copy = roleCopy[role] || roleCopy.admin;
  const [analytics, setAnalytics] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();

    async function loadAnalytics() {
      setError(null);
      try {
        const data = await copy.load({ signal: controller.signal });
        if (!mounted || controller.signal.aborted) return;
        setAnalytics(data);
      } catch (err) {
        if (!mounted || isAbortError(err)) return;
        setError(getErrorMessage(err, "Failed to load analytics."));
      }
    }

    loadAnalytics();
    return () => {
      mounted = false;
      controller.abort();
    };
  }, [copy]);

  const stats = analytics?.stats || {};
  const charts = analytics?.charts || {};
  const visibleCharts = useMemo(() => copy.charts, [copy.charts]);
  const featuredChart = visibleCharts.find((chart) => chart.featured);
  const supportingCharts = visibleCharts.filter((chart) => !chart.featured);
  const insight = getSnapshotInsight(role, stats)
    || getTrendInsight(chartData(charts, copy.trendKey), copy.insightLabel);

  if (!analytics && !error) {
    return <DashboardLayout role={role} title={copy.title} description={copy.description}><LoadingState label="Loading analytics..." /></DashboardLayout>;
  }

  return (
    <DashboardLayout role={role} title={copy.title} description={copy.description}>
      {error ? <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">{error}</div> : null}
      {!error ? (
        <div className="analytics-page space-y-6 lg:space-y-8">
          <AnalyticsInsight insight={insight} />

          <section className="analytics-metric-grid grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
            {copy.metricCards.map((metric) => (
              <DashboardMetricCard
                key={metric.key}
                label={metric.label}
                value={formatMetric(stats[metric.key], metric.suffix)}
                description={metric.description}
                icon={metric.icon}
                tone={metric.tone}
              />
            ))}
          </section>

          {featuredChart ? (
            <section className="space-y-4">
              <DashboardSectionHeader title="Primary trend" description="The strongest current signal from available records." showDescription />
              {renderChart(featuredChart, charts)}
            </section>
          ) : null}

          {supportingCharts.length ? (
            <section className="space-y-4">
              <DashboardSectionHeader title="Detailed breakdowns" description="Role-specific comparisons from existing backend metrics." showDescription />
              <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
                {supportingCharts.map((chart) => renderChart(chart, charts))}
              </div>
            </section>
          ) : null}
        </div>
      ) : null}
    </DashboardLayout>
  );
}
