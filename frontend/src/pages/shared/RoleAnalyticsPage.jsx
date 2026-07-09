import { useEffect, useMemo, useState } from "react";
import { BarChart3, LineChart, PieChart, Sparkles } from "lucide-react";

import AnalyticsBarChart from "../../components/charts/AnalyticsBarChart";
import AnalyticsDonutChart from "../../components/charts/AnalyticsDonutChart";
import AnalyticsLineChart from "../../components/charts/AnalyticsLineChart";
import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
import Card from "../../components/ui/Card";
import { FEATURE_CODES } from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { getErrorMessage, isAbortError } from "../../services/api";
import { dashboardService } from "../../services/dashboard.service";
import {
  DashboardMetricCard,
  DashboardSectionHeader,
} from "../../components/dashboard/DashboardPrimitives";

const roleCopy = {
  admin: {
    title: "Advanced Analytics",
    description: "A quieter page for deeper school analytics, so the main dashboard stays simple.",
    load: dashboardService.getTenantAdminAnalytics,
    metricCards: [
      { key: "result_completion_percent", label: "Result completion", suffix: "%" },
      { key: "report_cards_published", label: "Published reports" },
      { key: "student_profiles_incomplete", label: "Incomplete profiles" },
    ],
    charts: [
      { kind: "line", key: "performance_trend", title: "Performance Trend", description: "Average tenant performance by academic term." },
      { kind: "bar", key: "teacher_submission_progress", title: "Teacher Submission Progress", description: "Average completion percentage by teacher." },
      { kind: "bar", key: "user_population_breakdown", title: "User Population Breakdown", description: "Students, teachers, and parents currently in this school." },
      { kind: "donut", key: "student_profile_completion_rate", title: "Student Profile Completion", description: "Complete versus incomplete student profiles." },
      { kind: "bar", key: "account_status_overview", title: "Account Status Overview", description: "Active and pending teacher/parent accounts." },
      { kind: "donut", key: "announcements_by_category", title: "Announcements By Category", description: "Communication categories posted by the school." },
      { kind: "bar", key: "class_population", title: "Class Population", description: "Number of enrolled students in each class." },
      { kind: "donut", key: "report_card_status", title: "Report Card Status", description: "Generated report-card publishing progress." },
      { kind: "bar", key: "subject_performance", title: "Subject Performance", description: "Average score by subject." },
      { kind: "bar", key: "class_performance", title: "Class Performance", description: "Average score by class." },
      { kind: "donut", key: "grade_distribution", title: "Grade Distribution", description: "All recorded academic grades in this tenant." },
      { kind: "donut", key: "result_status_distribution", title: "Result Status Distribution", description: "Draft and submitted result rows." },
      { kind: "bar", key: "result_completion_by_subject", title: "Result Completion By Subject", description: "Average completion signal grouped by subject." },
    ],
  },
  teacher: {
    title: "Teaching Analytics",
    description: "Deeper teaching performance, class size, and score-entry signals.",
    load: dashboardService.getTeacherAnalytics,
    metricCards: [
      { key: "result_completion_percent", label: "Score completion", suffix: "%" },
      { key: "pending_score_rows", label: "Pending scores" },
      { key: "result_rows_submitted", label: "Submitted scores" },
    ],
    charts: [
      { kind: "line", key: "performance_trend", title: "Submitted Score Trend", description: "Average submitted score by academic term." },
      { kind: "bar", key: "class_sizes", title: "Subject Class Sizes", description: "Number of students in classes where you teach a subject." },
      { kind: "donut", key: "result_status_distribution", title: "Score Status Breakdown", description: "Draft versus submitted scores." },
      { kind: "donut", key: "grade_distribution", title: "Grade Distribution", description: "Grades from submitted results you entered." },
      { kind: "donut", key: "announcement_read_vs_acknowledged", title: "Announcement Read vs Acknowledged", description: "Read and acknowledgement status for your announcements." },
      { kind: "donut", key: "announcement_category_breakdown", title: "Announcement Categories", description: "Categories used in your teacher announcements." },
    ],
  },
  student: {
    title: "My Performance",
    description: "A focused view of your academic performance without crowding your main dashboard.",
    load: dashboardService.getStudentAnalytics,
    metricCards: [
      { key: "current_average", label: "Current average", suffix: "%" },
      { key: "published_results", label: "Published results" },
      { key: "pending_results", label: "Pending results" },
    ],
    charts: [
      { kind: "line", key: "performance_trend", title: "Performance Trend", description: "Average score by academic term." },
      { kind: "bar", key: "subject_comparison", title: "Subject Comparison", description: "Published average scores by subject." },
      { kind: "bar", key: "subject_performance", title: "Subject Performance", description: "Published scores by subject." },
      { kind: "donut", key: "grade_distribution", title: "Grade Distribution", description: "Published grade spread across subjects." },
      { kind: "donut", key: "announcement_read_vs_unread", title: "Notices Read vs Unread", description: "Your school update read status." },
    ],
  },
};

const chartData = (charts, key) => {
  const value = charts?.[key];
  return Array.isArray(value) ? value : [];
};

const formatMetric = (value, suffix = "") => {
  if (value === null || value === undefined || value === "") return "-";
  return `${value}${suffix}`;
};

function renderChart(chart, charts) {
  const data = chartData(charts, chart.key);
  if (chart.kind === "donut") {
    return (
      <AnalyticsDonutChart
        key={chart.key}
        title={chart.title}
        description={chart.description}
        data={data}
        emptyMessage="No data is available for this chart yet."
      />
    );
  }

  if (chart.kind === "line") {
    return (
      <AnalyticsLineChart
        key={chart.key}
        title={chart.title}
        description={chart.description}
        data={data}
        emptyMessage="No trend data is available yet."
      />
    );
  }

  return (
    <AnalyticsBarChart
      key={chart.key}
      title={chart.title}
      description={chart.description}
      data={data}
      emptyMessage="No chart data is available yet."
    />
  );
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
        const data = await copy.load({ signal: controller.signal });
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
  }, [copy, shouldGateAdmin]);

  const stats = analytics?.stats || {};
  const charts = analytics?.charts || {};
  const populatedCharts = useMemo(
    () => copy.charts.filter((chart) => chartData(charts, chart.key).length > 0),
    [copy.charts, charts],
  );
  const visibleCharts = populatedCharts.length > 0 ? populatedCharts : copy.charts;

  if (shouldGateAdmin) {
    return (
      <DashboardLayout role={role} title="Advanced Analytics">
        <Card className="p-6 sm:p-8">
          <div className="flex max-w-3xl flex-col gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-warning-soft text-amber-950">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h2 className="section-title">Advanced analytics is not active on this plan</h2>
              <p className="mt-2 text-sm leading-6 text-text-muted">
                Your main dashboard still shows the core school overview. Upgrade when you need deeper performance, population, and reporting charts.
              </p>
            </div>
          </div>
        </Card>
      </DashboardLayout>
    );
  }

  if (!analytics && !error) {
    return (
      <DashboardLayout role={role} title={copy.title} description={copy.description}>
        <LoadingState label="Loading analytics..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout role={role} title={copy.title} description={copy.description}>
      {error ? (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {error}
        </div>
      ) : null}

      {!error ? (
        <>
          <section className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-3">
            {copy.metricCards.map((metric, index) => (
              <DashboardMetricCard
                key={metric.key}
                label={metric.label}
                value={formatMetric(stats[metric.key], metric.suffix)}
                description="Dashboard metric"
                icon={index === 0 ? BarChart3 : index === 1 ? LineChart : PieChart}
                tone={index === 0 ? "primary" : index === 1 ? "success" : "warning"}
              />
            ))}
          </section>

          <section className="space-y-4">
            <DashboardSectionHeader
              title="Deep-dive charts"
              description="Charts live here so the role dashboard can stay clean and fast to understand."
            />
            <div className="grid gap-5 xl:grid-cols-2">
              {visibleCharts.map((chart) => renderChart(chart, charts))}
            </div>
          </section>
        </>
      ) : null}
    </DashboardLayout>
  );
}
