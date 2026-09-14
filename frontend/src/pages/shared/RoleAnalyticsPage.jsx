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
import { academicService } from "../../services/academicService";
import { getErrorMessage, isAbortError } from "../../services/api";
import { dashboardService } from "../../services/dashboard.service";
import { parentService } from "../../services/parentService";
import { reportCardService } from "../../services/reportCardService";
import { averageScore, formatChartLabel } from "../../utils/academicDashboard";
import { displayName } from "../../utils/user";
import { normalizeParentChildRecord } from "../parent/parentPageUtils";

const asItems = (response) => (Array.isArray(response?.items) ? response.items : []);

const latestPeriodAverage = (results = []) => {
  if (!Array.isArray(results) || results.length === 0) return null;

  const latest = results[0];
  const samePeriod = results.filter((item) => {
    if (latest?.academic_session_id && latest?.academic_term_id) {
      return (
        item?.academic_session_id === latest.academic_session_id
        && item?.academic_term_id === latest.academic_term_id
      );
    }

    return (
      item?.academic_session_name === latest?.academic_session_name
      && item?.academic_term_name === latest?.academic_term_name
    );
  });

  return samePeriod.length > 0 ? averageScore(samePeriod) : null;
};

const parentChildLabel = (entry, index) => {
  const { student } = normalizeParentChildRecord(entry);
  return displayName(student) || `Child ${index + 1}`;
};

const loadParentFamilyInsights = async (requestOptions = {}) => {
  const [childrenResponse, communicationMetrics] = await Promise.all([
    parentService.getMyStudents(requestOptions),
    dashboardService.getParentAnalytics(requestOptions),
  ]);
  const children = asItems(childrenResponse);

  const childSummaries = await Promise.all(
    children.map(async (entry, index) => {
      const { student } = normalizeParentChildRecord(entry);
      if (!student?.id) {
        return {
          label: parentChildLabel(entry, index),
          results: [],
          reportCards: [],
          unavailable: true,
        };
      }

      try {
        const [resultResponse, reportCardResponse] = await Promise.all([
          academicService.listChildResults(student.id, requestOptions),
          reportCardService.listChildReportCards(student.id, {}, requestOptions),
        ]);
        return {
          label: parentChildLabel(entry, index),
          results: asItems(resultResponse),
          reportCards: asItems(reportCardResponse),
          unavailable: false,
        };
      } catch (error) {
        if (isAbortError(error)) throw error;
        return {
          label: parentChildLabel(entry, index),
          results: [],
          reportCards: [],
          unavailable: true,
        };
      }
    }),
  );

  const childrenWithResults = childSummaries.filter((item) => item.results.length > 0).length;
  const childrenWithReports = childSummaries.filter((item) => item.reportCards.length > 0).length;
  const publishedReportCards = childSummaries.reduce(
    (total, item) => total + item.reportCards.length,
    0,
  );
  const unavailableChildren = childSummaries.filter((item) => item.unavailable).length;

  const latestAverage = childSummaries.flatMap((item) => {
    const reportAverage = Number(item.reportCards[0]?.average_score);
    const fallbackAverage = latestPeriodAverage(item.results);
    const value = Number.isFinite(reportAverage) ? reportAverage : fallbackAverage;
    if (!Number.isFinite(Number(value))) return [];
    return [{ label: item.label, value: Math.round(Number(value) * 10) / 10 }];
  });

  const reportCardsByChild = childSummaries.map((item) => ({
    label: item.label,
    value: item.reportCards.length,
  }));

  const communicationStats = communicationMetrics?.stats || {};
  return {
    stats: {
      linked_students: children.length,
      children_with_results: childrenWithResults,
      children_with_published_reports: childrenWithReports,
      published_report_cards: publishedReportCards,
      unread_count: Number(communicationStats.unread_count) || 0,
      primary_contacts: Number(communicationStats.primary_contacts) || 0,
      unavailable_children: unavailableChildren,
    },
    charts: {
      child_latest_average: latestAverage,
      report_card_coverage: children.length > 0
        ? [
            { label: "Report available", value: childrenWithReports },
            { label: "Awaiting report", value: Math.max(children.length - childrenWithReports, 0) },
          ]
        : [],
      report_cards_by_child: reportCardsByChild,
    },
  };
};

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
    description: "A family-wide view of linked children, academic availability, and items that may need your attention.",
    load: loadParentFamilyInsights,
    insightLabel: "Family overview",
    featuredSectionTitle: "Family comparison",
    featuredSectionDescription: "A simple side-by-side view across your linked children.",
    supportingSectionTitle: "Family coverage",
    supportingSectionDescription: "Report availability across the children linked to this school.",
    metricCards: [
      { key: "linked_students", label: "Linked children", icon: GraduationCap, tone: "primary", description: "Children available in this school" },
      { key: "children_with_results", label: "Results available", icon: CheckCircle2, tone: "success", description: "Children with finalized results" },
      { key: "published_report_cards", label: "Published reports", icon: FileText, tone: "accent", description: "Report cards available across the family" },
      { key: "unread_count", label: "School updates", icon: Bell, tone: "warning", description: "Unread items that may need attention" },
    ],
    charts: [
      {
        kind: "bar",
        key: "child_latest_average",
        title: "Latest academic average by child",
        description: "Latest published report average, with finalized current-period results used when a report is not available yet.",
        emptyMessage: "Academic averages will appear when finalized results or published reports are available.",
        featured: true,
      },
      {
        kind: "donut",
        key: "report_card_coverage",
        title: "Report availability",
        description: "How many linked children currently have at least one published report card.",
        emptyMessage: "Link a child to see family report availability.",
      },
      {
        kind: "bar",
        key: "report_cards_by_child",
        title: "Published reports by child",
        description: "Published report-card history available for each linked child.",
        emptyMessage: "Published report cards will appear here after the school releases them.",
      },
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
  const childrenWithResults = Number(stats.children_with_results) || 0;
  const childrenWithReports = Number(stats.children_with_published_reports) || 0;
  const publishedReports = Number(stats.published_report_cards) || 0;
  const unreadUpdates = Number(stats.unread_count) || 0;
  const unavailableChildren = Number(stats.unavailable_children) || 0;

  if (linkedStudents === 0) {
    return {
      eyebrow: "Family snapshot",
      title: "Link a child to unlock family insights",
      detail: "Once a student is linked, this page will summarize academic availability across your family.",
      tone: "neutral",
      icon: GraduationCap,
    };
  }

  if (childrenWithResults === 0 && childrenWithReports === 0) {
    return {
      eyebrow: "Family snapshot",
      title: `${linkedStudents} linked child${linkedStudents === 1 ? "" : "ren"} ready for updates`,
      detail: "Finalized results and published report cards will appear here as the school releases them.",
      tone: unavailableChildren > 0 ? "warning" : "neutral",
      icon: GraduationCap,
    };
  }

  const academicChildren = Math.max(childrenWithResults, childrenWithReports);
  const reportCopy = `${publishedReports} published report card${publishedReports === 1 ? "" : "s"} available across your family.`;
  const updateCopy = unreadUpdates > 0
    ? ` ${unreadUpdates} unread school update${unreadUpdates === 1 ? "" : "s"} may need your attention.`
    : " No unread school updates need attention right now.";
  const availabilityCopy = unavailableChildren > 0
    ? ` ${unavailableChildren} child summary could not be loaded and may be temporarily unavailable.`
    : "";

  return {
    eyebrow: "Family snapshot",
    title: `${academicChildren} of ${linkedStudents} linked child${linkedStudents === 1 ? "" : "ren"} have academic records available`,
    detail: `${reportCopy}${updateCopy}${availabilityCopy}`,
    tone: unreadUpdates > 0 || unavailableChildren > 0 ? "warning" : "success",
    icon: unreadUpdates > 0 || unavailableChildren > 0 ? Bell : CheckCircle2,
  };
};

function renderChart(chart, charts) {
  const data = chartData(charts, chart.key);
  const commonProps = {
    key: chart.key,
    title: chart.title,
    description: chart.description,
    data,
    emptyMessage: chart.emptyMessage || "No finalized data is available for this chart yet.",
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
          <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-text-muted">{insight.eyebrow || "Latest signal"}</p>
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
              <DashboardSectionHeader
                title={copy.featuredSectionTitle || "Primary trend"}
                description={copy.featuredSectionDescription || "The strongest current signal from available records."}
                showDescription
              />
              {renderChart(featuredChart, charts)}
            </section>
          ) : null}

          {supportingCharts.length ? (
            <section className="space-y-4">
              <DashboardSectionHeader
                title={copy.supportingSectionTitle || "Detailed breakdowns"}
                description={copy.supportingSectionDescription || "Role-specific comparisons from existing backend metrics."}
                showDescription
              />
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
