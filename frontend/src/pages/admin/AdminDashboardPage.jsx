import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  BookOpen,
  GraduationCap,
  PlusCircle,
  Shapes,
  UserCheck,
  Users,
} from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import StatCard from "../../components/shared/StatCard";
import LoadingState from "../../components/shared/LoadingState";
import EmptyState from "../../components/shared/EmptyState";
import AnalyticsBarChart from "../../components/charts/AnalyticsBarChart";
import AnalyticsDonutChart from "../../components/charts/AnalyticsDonutChart";
import AnalyticsLineChart from "../../components/charts/AnalyticsLineChart";
import { dashboardService } from "../../services/dashboard.service";
import { authSession, getErrorMessage } from "../../services/api";
import { academicService } from "../../services/academicService";
import { reportCardService } from "../../services/reportCardService";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { FEATURE_CODES } from "../../features/subscriptions/subscriptionConfig";
import {
  averageBy,
  averageByAcademicPeriod,
  chartFromCounts,
  cleanText,
  completionPercent,
  reportCardStatusChart,
} from "../../utils/academicDashboard";

const statItems = [
  { key: "total_students", label: "Students", description: "registered learners", icon: GraduationCap, tone: "primary" },
  { key: "total_teachers", label: "Teachers", description: "teacher accounts", icon: Users, tone: "success" },
  { key: "total_parents", label: "Parents", description: "parent accounts", icon: UserCheck, tone: "accent" },
  { key: "total_classes", label: "Classes", description: "academic groups", icon: Shapes, tone: "warning" },
  { key: "total_subjects", label: "Subjects", description: "active catalog items", icon: BookOpen, tone: "primary" },
  { key: "student_profiles_incomplete", label: "Incomplete Profiles", description: "students needing updates", icon: UserCheck, tone: "warning" },
];

function AdminDashboardPage() {
  const [analytics, setAnalytics] = useState(null);
  const [academicResults, setAcademicResults] = useState([]);
  const [reportCards, setReportCards] = useState([]);
  const [error, setError] = useState(null);
  const { getFeatureGuard } = useSubscription();
  const user = authSession.getUser();
  const firstName = user?.first_name || user?.firstname || "Admin";
  const advancedAnalyticsGuard = getFeatureGuard(
    FEATURE_CODES.ADVANCED_ANALYTICS
  );

  useEffect(() => {
    let mounted = true;
    let secondaryTimer = null;

    async function loadSecondaryAnalytics() {
      try {
        const [resultResponse, reportCardResponse] = await Promise.all([
          academicService.listAdminResults({ limit: 25 }),
          reportCardService.listAdminReportCards({ limit: 25 }),
        ]);
        if (!mounted) return;
        setAcademicResults(resultResponse?.items || []);
        setReportCards(reportCardResponse?.items || []);
      } catch (err) {
        console.warn("Failed to load secondary dashboard analytics", err);
      }
    }

    async function loadMetrics() {
      try {
        const data = await dashboardService.getTenantAdminAnalytics();
        if (!mounted) return;
        setAnalytics(data);
        secondaryTimer = window.setTimeout(loadSecondaryAnalytics, 500);
      } catch (err) {
        if (mounted) setError(getErrorMessage(err, "Failed to load dashboard analytics."));
      }
    }

    loadMetrics();

    return () => {
      mounted = false;
      if (secondaryTimer) window.clearTimeout(secondaryTimer);
    };
  }, []);

  const teacherSubmissionProgress = useMemo(
    () =>
      averageBy(
        academicResults.map((item) => ({
          ...item,
          completion_score: ["submitted", "published", "locked"].includes(item.status) ? 100 : 0,
        })),
        (item) => item.teacher_name || item.teacher_staff_id || "Teacher",
        "completion_score"
      ),
    [academicResults]
  );

  if (!analytics && !error) {
    return (
      <DashboardLayout role="admin" title="Dashboard">
        <LoadingState label="Loading dashboard..." />
      </DashboardLayout>
    );
  }

  const stats = analytics?.stats || {};
  const charts = analytics?.charts || {};
  const submittedResults = academicResults.filter((item) =>
    ["submitted", "published", "locked"].includes(item.status)
  ).length;
  const resultCompletion = completionPercent(submittedResults, academicResults.length);
  const performanceTrend =
    charts.performance_trend ||
    averageByAcademicPeriod(
      reportCards.length > 0 ? reportCards : academicResults,
      reportCards.length > 0 ? "average_score" : "total_score"
    );

  return (
    <DashboardLayout
      role="admin"
      title={`${firstName}'s Dashboard`}
      actions={
        <Link to="/admin/create-user">
          <Button>
            <PlusCircle className="h-4 w-4" />
            Create user
          </Button>
        </Link>
      }
    >
      {error && (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {error}
        </div>
      )}

      {!error && (
        <>
          <section className="dashboard-grid lg:grid-cols-[minmax(0,1.3fr)_minmax(300px,0.7fr)]">
            <Card className="p-5 sm:p-6">
              <div className="flex flex-col gap-4">
                <div>
                  <h2 className="section-title">School overview</h2>
                  <p className="mt-1 text-sm text-text-muted">
                    Core academic context first, so the larger analytics below feel grounded instead of scattered.
                  </p>
                </div>

                <div className="dashboard-kpi-grid dashboard-kpi-grid-four">
                  <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Active session</p>
                    <p className="mt-2 text-base font-semibold text-text">
                      {cleanText(stats.active_academic_session, "-")}
                    </p>
                  </div>
                  <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Active term</p>
                    <p className="mt-2 text-base font-semibold text-text">
                      {cleanText(stats.active_academic_term, "-")}
                    </p>
                  </div>
                  <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Result completion</p>
                    <p className="mt-2 text-base font-semibold text-text">{resultCompletion}%</p>
                    <p className="mt-1 text-xs text-text-muted">
                      {submittedResults} of {academicResults.length} rows submitted
                    </p>
                  </div>
                  <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Report cards</p>
                    <p className="mt-2 text-base font-semibold text-text">
                      {stats.report_cards_published ?? reportCards.filter((item) => item.status === "published").length}
                    </p>
                    <p className="mt-1 text-xs text-text-muted">
                      {stats.report_cards_generated ?? reportCards.length} generated
                    </p>
                  </div>
                </div>
              </div>
            </Card>

            <Card className="flex h-full flex-col p-5 sm:p-6">
              <h2 className="section-title">Operational snapshot</h2>
              <p className="mt-1 text-sm text-text-muted">
                A compact health readout for onboarding, account status, and publishing readiness.
              </p>
              {analytics ? (
                <div className="dashboard-kpi-grid mt-auto pt-4 lg:grid-cols-1 xl:grid-cols-2">
                  <div className="rounded-[1.1rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Profiles complete</p>
                    <p className="mt-2 text-lg font-semibold text-text">{stats.student_profiles_complete ?? 0}</p>
                  </div>
                  <div className="rounded-[1.1rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Profiles incomplete</p>
                    <p className="mt-2 text-lg font-semibold text-text">{stats.student_profiles_incomplete ?? 0}</p>
                  </div>
                  <div className="rounded-[1.1rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Pending teacher accounts</p>
                    <p className="mt-2 text-lg font-semibold text-text">{stats.pending_teacher_accounts ?? 0}</p>
                  </div>
                  <div className="rounded-[1.1rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Pending parent accounts</p>
                    <p className="mt-2 text-lg font-semibold text-text">{stats.pending_parent_accounts ?? 0}</p>
                  </div>
                </div>
              ) : (
                <EmptyState
                  title="No analytics available"
                  description="Tenant analytics will appear here once the backend responds."
                />
              )}
            </Card>
          </section>

          <section className="stat-grid stat-grid-six">
            {statItems.map((item) => (
              <StatCard
                key={item.key}
                label={item.label}
                value={stats[item.key] ?? 0}
                description={
                  item.key === "student_profiles_incomplete" && Number(stats[item.key] ?? 0) === 0
                    ? "no student records need updates"
                    : item.description
                }
                valueBadge={
                  item.key === "student_profiles_incomplete" && Number(stats[item.key] ?? 0) === 0
                    ? { label: "All up to date", variant: "success" }
                    : null
                }
                icon={item.icon}
                tone={item.tone}
                compact
              />
            ))}
          </section>

          <section className="dashboard-grid xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
            <AnalyticsLineChart
              title="Performance Trend"
              description="Average tenant performance by academic term."
              data={performanceTrend}
              emptyMessage="No term performance trend is available yet."
            />
            <AnalyticsBarChart
              title="Teacher Submission Progress"
              description="Average completion percentage by teacher."
              data={teacherSubmissionProgress}
              emptyMessage="No teacher submission data available yet."
            />
          </section>

          {advancedAnalyticsGuard.allowed ? (
            <section className="dashboard-grid md:grid-cols-2 2xl:grid-cols-3">
              <AnalyticsBarChart
                title="User Population Breakdown"
                description="Students, teachers, and parents currently in this school."
                data={charts.user_population_breakdown || []}
              />
              <AnalyticsDonutChart
                title="Student Profile Completion Rate"
                description="Shows how many student profiles are complete versus still missing required fields."
                data={charts.student_profile_completion_rate || []}
              />
              <AnalyticsBarChart
                title="Account Status Overview"
                description="Active and pending accounts across teachers and parents."
                data={charts.account_status_overview || []}
                emptyMessage="No account status data available yet."
              />
              <AnalyticsDonutChart
                title="Announcements By Category"
                description="Announcement categories posted within this school."
                data={charts.announcements_by_category || []}
                emptyMessage="No announcements have been posted yet."
              />
              <AnalyticsBarChart
                title="Class Population"
                description="Number of enrolled students in each class."
                data={charts.class_population || []}
                emptyMessage="No class population data available yet."
              />
              <AnalyticsDonutChart
                title="Report Card Status"
                description="Generated report-card publishing progress."
                data={reportCardStatusChart(reportCards)}
                emptyMessage="No report cards have been generated yet."
              />
              <AnalyticsBarChart
                title="Subject Performance"
                description="Average score by subject."
                data={charts.subject_performance || averageBy(academicResults, (item) => item.subject_name || item.subject_code || "Subject")}
                emptyMessage="No subject performance data available yet."
              />
              <AnalyticsBarChart
                title="Class Performance"
                description="Average score by class from recorded results."
                data={averageBy(academicResults, (item) => [item.class_name, item.class_arm].filter(Boolean).join(" ") || "Class")}
                emptyMessage="No class performance data available yet."
              />
              <AnalyticsDonutChart
                title="Grade Distribution"
                description="All recorded academic grades in this tenant."
                data={charts.grade_distribution || chartFromCounts(academicResults, "grade", "ungraded")}
                emptyMessage="No grade data has been recorded yet."
              />
              <AnalyticsDonutChart
                title="Result Status"
                description="Draft, submitted, published, and locked result rows."
                data={charts.result_status_distribution || chartFromCounts(academicResults, "status", "draft")}
                emptyMessage="No result status data has been recorded yet."
              />
              <AnalyticsBarChart
                title="Result Completion By Subject"
                description="Average completion signal grouped by subject."
                data={averageBy(
                  academicResults.map((item) => ({
                    ...item,
                    completion_score: ["submitted", "published", "locked"].includes(item.status) ? 100 : 0,
                  })),
                  (item) => item.subject_name || item.subject_code || "Subject",
                  "completion_score"
                )}
                emptyMessage="No subject completion data available yet."
              />
            </section>
          ) : null}
        </>
      )}
    </DashboardLayout>
  );
}

export default AdminDashboardPage;
