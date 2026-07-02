import { useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  BookOpen,
  ClipboardList,
  FileText,
  GraduationCap,
  Link2,
  UserRound,
} from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import AnalyticsBarChart from "../../components/charts/AnalyticsBarChart";
import AnalyticsDonutChart from "../../components/charts/AnalyticsDonutChart";
import AnalyticsLineChart from "../../components/charts/AnalyticsLineChart";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import StatCard from "../../components/shared/StatCard";
import { authSession, getErrorMessage } from "../../services/api";
import { dashboardService } from "../../services/dashboard.service";
import { studentService } from "../../services/studentService";
import { academicService } from "../../services/academicService";
import { reportCardService } from "../../services/reportCardService";
import { displayName } from "../../utils/user";
import {
  averageByAcademicPeriod,
  averageScore,
  bestAndWeakestSubject,
  chartFromCounts,
  cleanText,
  subjectPerformanceChart,
} from "../../utils/academicDashboard";
import {
  formatMetricNumber,
  getAcademicContext,
  hasValue,
  isPublishedResult,
  statusVariant,
} from "./studentPageUtils";

function StudentDashboardPage() {
  const [student, setStudent] = useState(null);
  const [parentLinks, setParentLinks] = useState([]);
  const [parentLinkRequests, setParentLinkRequests] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [academicResults, setAcademicResults] = useState([]);
  const [reportCards, setReportCards] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const user = authSession.getUser();
  const firstName = user?.first_name || user?.firstname || "Student";

  useEffect(() => {
    let mounted = true;

    async function loadDashboard() {
      setIsLoading(true);
      setLoadError(null);

      try {
        const [
          studentProfile,
          linksResponse,
          requestsResponse,
          metricsResponse,
          resultResponse,
          reportCardResponse,
        ] = await Promise.all([
          studentService.getMyStudent(),
          studentService.getMyParentLinks(),
          studentService.getMyParentLinkRequests(),
          dashboardService.getStudentAnalytics(),
          academicService.listMyResults(),
          reportCardService.listMyReportCards(),
        ]);

        if (!mounted) return;
        setStudent(studentProfile);
        setParentLinks(linksResponse?.items || []);
        setParentLinkRequests(requestsResponse?.items || []);
        setMetrics(metricsResponse);
        setAcademicResults(resultResponse?.items || []);
        setReportCards(reportCardResponse?.items || []);
      } catch (error) {
        if (mounted) setLoadError(getErrorMessage(error, "Failed to load student dashboard."));
      } finally {
        if (mounted) setIsLoading(false);
      }
    }

    loadDashboard();

    return () => {
      mounted = false;
    };
  }, []);

  const dashboardData = useMemo(() => {
    const stats = metrics?.stats || {};
    const publishedResults = academicResults.filter(isPublishedResult);
    const pendingResults = academicResults.filter((result) => !isPublishedResult(result));
    const subjectHighlights = bestAndWeakestSubject(publishedResults);
    const context = getAcademicContext(academicResults, reportCards);
    const uniqueSubjects = new Set(
      academicResults
        .map((result) => result.subject_id || result.subject_name || result.subject_code)
        .filter(Boolean)
    );
    const currentAverage = hasValue(stats.current_average)
      ? stats.current_average
      : publishedResults.length > 0
        ? averageScore(publishedResults)
        : null;
    const chartSource = metrics?.charts || {};
    const performanceTrend =
      chartSource.performance_trend ||
      averageByAcademicPeriod(
        reportCards.length > 0 ? reportCards : publishedResults,
        reportCards.length > 0 ? "average_score" : "total_score"
      );
    const chartWidgets = [
      {
        kind: "line",
        title: "Performance Trend",
        description: "Average performance across published academic terms.",
        data: performanceTrend,
      },
      {
        kind: "bar",
        title: "Subject Performance",
        description: "Published scores by subject.",
        data:
          chartSource.subject_performance ||
          chartSource.subject_comparison ||
          subjectPerformanceChart(publishedResults),
      },
      {
        kind: "donut",
        title: "Grade Distribution",
        description: "Published grade spread across subjects.",
        data:
          chartSource.grade_distribution ||
          chartFromCounts(publishedResults, "grade", "ungraded"),
      },
    ].filter((chart) => Array.isArray(chart.data) && chart.data.length > 0);

    return {
      currentAverage,
      publishedResults,
      pendingResults,
      subjectHighlights,
      subjectsCount: hasValue(stats.subjects_count) ? stats.subjects_count : uniqueSubjects.size,
      context,
      latestReportCard: reportCards[0],
      pendingParentRequests: parentLinkRequests.filter((request) => request.status === "pending"),
      performanceTrend,
      chartWidgets,
    };
  }, [academicResults, metrics, parentLinkRequests, reportCards]);

  if (isLoading) {
    return (
      <DashboardLayout role="student" title={`${firstName}'s Portal`}>
        <LoadingState label="Loading student dashboard..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="student"
      title={`${firstName}'s Portal`}
      description="A clean academic snapshot. Detailed workflows stay in their own pages so this overview remains easy to scan."
    >
      {loadError && (
        <div className="rounded-[1.35rem] border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {loadError}
        </div>
      )}

      {!loadError && !student && (
        <EmptyState
          icon={UserRound}
          title="No student profile found"
          description="Your account exists, but the school has not created your student academic profile yet."
        />
      )}

      {!loadError && student && (
        <>
          <section className="dashboard-grid xl:grid-cols-[minmax(0,1.2fr)_minmax(300px,0.8fr)]">
            <Card className="overflow-hidden p-5 sm:p-6">
              <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={statusVariant(student.profile_status)}>
                      {cleanText(student.profile_status, "profile pending")}
                    </Badge>
                    <Badge variant="info">
                      {cleanText(dashboardData.context.sessionLabel, "No session")} /{" "}
                      {cleanText(dashboardData.context.termLabel, "No term")}
                    </Badge>
                  </div>
                  <h2 className="mt-3 text-xl font-semibold leading-tight text-text sm:text-2xl">
                    Welcome back, {displayName(student) || firstName}
                  </h2>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-text-muted">
                    {cleanText(
                      dashboardData.context.classLabel,
                      student.class_id ? "Class assigned" : "No class assigned"
                    )}
                  </p>
                </div>

                <div className="dashboard-kpi-grid xl:grid-cols-1">
                  <div className="rounded-[1.2rem] border border-border/70 bg-surface-muted/25 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                      Current class
                    </p>
                    <p className="mt-2 text-sm font-semibold text-text">
                      {cleanText(dashboardData.context.classLabel, "Not assigned")}
                    </p>
                  </div>
                  <div className="rounded-[1.2rem] border border-border/70 bg-surface-muted/25 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                      Latest term
                    </p>
                    <p className="mt-2 text-sm font-semibold text-text">
                      {cleanText(dashboardData.context.termLabel, "No term")}
                    </p>
                  </div>
                  <div className="rounded-[1.2rem] border border-border/70 bg-surface-muted/25 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                      Parent approvals
                    </p>
                    <p className="mt-2 text-sm font-semibold text-text">
                      {dashboardData.pendingParentRequests.length} pending
                    </p>
                  </div>
                </div>
              </div>
            </Card>

            <Card className="flex h-full flex-col p-5 sm:p-6">
              <div>
                <h3 className="section-title">Academic snapshot</h3>
                <p className="mt-1 text-sm text-text-muted">
                  A focused summary card so the dashboard opens with context before deeper charts.
                </p>
              </div>

              <div className="dashboard-kpi-grid mt-auto pt-4 xl:grid-cols-1 2xl:grid-cols-2">
                <div className="rounded-[1.2rem] border border-border/70 bg-surface-muted/25 px-4 py-3">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                    Current average
                  </p>
                  <p className="mt-2 text-lg font-semibold text-text">
                    {hasValue(dashboardData.currentAverage)
                      ? formatMetricNumber(dashboardData.currentAverage)
                      : "-"}
                  </p>
                </div>
                <div className="rounded-[1.2rem] border border-border/70 bg-surface-muted/25 px-4 py-3">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                    Subjects tracked
                  </p>
                  <p className="mt-2 text-lg font-semibold text-text">{dashboardData.subjectsCount}</p>
                </div>
                <div className="rounded-[1.2rem] border border-border/70 bg-surface-muted/25 px-4 py-3">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                    Published results
                  </p>
                  <p className="mt-2 text-lg font-semibold text-text">
                    {dashboardData.publishedResults.length}
                  </p>
                </div>
                <div className="rounded-[1.2rem] border border-border/70 bg-surface-muted/25 px-4 py-3">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                    Latest report
                  </p>
                  <p className="mt-2 text-lg font-semibold text-text">
                    {dashboardData.latestReportCard
                      ? cleanText(dashboardData.latestReportCard.academic_term_name, "Published")
                      : "Awaiting release"}
                  </p>
                </div>
              </div>
            </Card>
          </section>

          <section className="stat-grid stat-grid-six">
            <StatCard
              label="Profile"
              value={student.profile_status === "complete" ? "Complete" : "Incomplete"}
              description="academic record"
              icon={UserRound}
              tone={student.profile_status === "complete" ? "success" : "warning"}
              compact
            />
            {hasValue(dashboardData.currentAverage) && (
              <StatCard
                label="Current Average"
                value={formatMetricNumber(dashboardData.currentAverage)}
                description="published subjects"
                icon={BarChart3}
                tone="success"
                compact
              />
            )}
            <StatCard
              label="Subjects"
              value={dashboardData.subjectsCount}
              description="records available"
              icon={BookOpen}
              tone="primary"
              compact
            />
            <StatCard
              label="Parent Links"
              value={parentLinks.length}
              description={`${dashboardData.pendingParentRequests.length} pending request${dashboardData.pendingParentRequests.length === 1 ? "" : "s"}`}
              icon={Link2}
              tone={parentLinks.length > 0 ? "success" : "warning"}
              compact
            />
            <StatCard
              label="Best Subject"
              value={dashboardData.subjectHighlights.best?.label || "-"}
              description={
                dashboardData.subjectHighlights.best
                  ? `${dashboardData.subjectHighlights.best.value} average score`
                  : "awaiting results"
              }
              icon={GraduationCap}
              tone={dashboardData.subjectHighlights.best ? "success" : "warning"}
              compact
            />
            <StatCard
              label="Needs Attention"
              value={dashboardData.subjectHighlights.weakest?.label || "-"}
              description={
                dashboardData.subjectHighlights.weakest
                  ? `${dashboardData.subjectHighlights.weakest.value} average score`
                  : "awaiting results"
              }
              icon={ClipboardList}
              tone={dashboardData.subjectHighlights.weakest ? "warning" : "primary"}
              compact
            />
          </section>

          {dashboardData.chartWidgets.length > 0 && (
            <section className="dashboard-grid xl:grid-cols-2">
              {dashboardData.chartWidgets.map((chart) =>
                chart.kind === "donut" ? (
                  <AnalyticsDonutChart
                    key={chart.title}
                    title={chart.title}
                    description={chart.description}
                    data={chart.data}
                  />
                ) : chart.kind === "line" ? (
                  <AnalyticsLineChart
                    key={chart.title}
                    title={chart.title}
                    description={chart.description}
                    data={chart.data}
                  />
                ) : (
                  <AnalyticsBarChart
                    key={chart.title}
                    title={chart.title}
                    description={chart.description}
                    data={chart.data}
                  />
                )
              )}
            </section>
          )}

          <section className="dashboard-grid xl:grid-cols-[minmax(0,1.2fr)_minmax(300px,0.8fr)]">
            <Card className="flex h-full flex-col p-5 sm:p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="section-title">Latest Report Card</h3>
                  <p className="mt-1 text-sm text-text-muted">
                    The newest published term, arranged as a summary instead of a second navigation menu.
                  </p>
                </div>
                {dashboardData.latestReportCard && (
                  <Badge variant={statusVariant(dashboardData.latestReportCard.status)}>
                    {cleanText(dashboardData.latestReportCard.status)}
                  </Badge>
                )}
              </div>

              {dashboardData.latestReportCard ? (
                <>
                  <div className="dashboard-kpi-grid mt-auto pt-4 sm:grid-cols-3">
                    <div className="rounded-[1.2rem] border border-border/70 bg-surface-muted/25 px-4 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Average</p>
                      <p className="mt-2 text-xl font-semibold text-text">
                        {cleanText(dashboardData.latestReportCard.average_score)}
                      </p>
                    </div>
                    <div className="rounded-[1.2rem] border border-border/70 bg-surface-muted/25 px-4 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Subjects</p>
                      <p className="mt-2 text-xl font-semibold text-text">
                        {dashboardData.latestReportCard.lines?.length || 0}
                      </p>
                    </div>
                    <div className="rounded-[1.2rem] border border-border/70 bg-surface-muted/25 px-4 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Position</p>
                      <p className="mt-2 text-xl font-semibold text-text">
                        {cleanText(dashboardData.latestReportCard.position, "-")}
                      </p>
                    </div>
                  </div>

                  <div className="mt-4 rounded-[1.3rem] border border-border/70 bg-surface-muted/15 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-text">
                        {cleanText(dashboardData.latestReportCard.academic_session_name, "Session")} /{" "}
                        {cleanText(dashboardData.latestReportCard.academic_term_name, "Term")}
                      </p>
                      <p className="text-xs font-medium text-text-muted">
                        Previewing recent subject lines
                      </p>
                    </div>

                    <div className="mt-4 grid gap-3">
                      {(dashboardData.latestReportCard.lines || []).slice(0, 3).map((line) => (
                        <div
                          key={line.id}
                          className="rounded-[1.2rem] border border-border/70 bg-surface p-4 shadow-sm"
                        >
                          <div className="flex flex-col gap-4">
                            <div className="min-w-0 rounded-[1rem] border border-border/60 bg-surface-muted/15 px-4 py-3">
                              <p className="truncate text-base font-semibold text-text">
                                {cleanText(line.subject_name, "Subject")}
                              </p>
                              <p className="mt-1 text-xs text-text-muted">
                                Teacher: {cleanText(line.teacher_name)}
                              </p>
                            </div>

                            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                              <div className="rounded-xl border border-border/60 bg-surface-muted/25 px-3 py-2 text-center">
                                <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Test</p>
                                <p className="mt-1 text-sm font-semibold text-text">{cleanText(line.test_score)}</p>
                              </div>
                              <div className="rounded-xl border border-border/60 bg-surface-muted/25 px-3 py-2 text-center">
                                <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Assess.</p>
                                <p className="mt-1 text-sm font-semibold text-text">{cleanText(line.assessment_score)}</p>
                              </div>
                              <div className="rounded-xl border border-border/60 bg-surface-muted/25 px-3 py-2 text-center">
                                <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Exam</p>
                                <p className="mt-1 text-sm font-semibold text-text">{cleanText(line.exam_score)}</p>
                              </div>
                              <div className="rounded-xl border border-border/60 bg-surface-muted/25 px-3 py-2 text-center">
                                <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Total</p>
                                <p className="mt-1 text-sm font-semibold text-text">{cleanText(line.total_score)}</p>
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <p className="mt-4 text-sm text-text-muted">
                  No report card has been published yet. When the next term closes, the latest summary will show here.
                </p>
              )}
            </Card>

            <Card className="flex h-full flex-col p-5 sm:p-6">
              <div className="flex items-start gap-3">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                  <FileText className="h-5 w-5" />
                </span>
                <div>
                  <h3 className="section-title">Academic Pulse</h3>
                  <p className="mt-1 text-sm text-text-muted">
                    This keeps the dashboard focused on changes and signals, while the sidebar handles navigation.
                  </p>
                </div>
              </div>

              <div className="dashboard-kpi-grid mt-auto pt-4">
                <div className="rounded-[1.2rem] border border-border/70 bg-surface-muted/25 px-4 py-3">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                    Published results
                  </p>
                  <p className="mt-2 text-lg font-semibold text-text">
                    {dashboardData.publishedResults.length}
                  </p>
                </div>
                <div className="rounded-[1.2rem] border border-border/70 bg-surface-muted/25 px-4 py-3">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                    Awaiting publication
                  </p>
                  <p className="mt-2 text-lg font-semibold text-text">
                    {dashboardData.pendingResults.length}
                  </p>
                </div>
                <div className="rounded-[1.2rem] border border-border/70 bg-surface-muted/25 px-4 py-3">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                    Linked parents
                  </p>
                  <p className="mt-2 text-lg font-semibold text-text">{parentLinks.length}</p>
                </div>
                <div className="rounded-[1.2rem] border border-border/70 bg-surface-muted/25 px-4 py-3">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                    Trend points
                  </p>
                  <p className="mt-2 text-lg font-semibold text-text">
                    {dashboardData.performanceTrend.length}
                  </p>
                </div>
              </div>

              <div className="mt-4 rounded-[1.3rem] border border-border/70 bg-surface-muted/15 p-4">
                <p className="text-sm font-semibold text-text">Subject highlights</p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-[1.05rem] border border-border/60 bg-surface px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                      Best subject
                    </p>
                    <p className="mt-2 text-sm font-semibold text-text">
                      {dashboardData.subjectHighlights.best?.label || "Awaiting published scores"}
                    </p>
                    {dashboardData.subjectHighlights.best && (
                      <p className="mt-1 text-xs text-text-muted">
                        {dashboardData.subjectHighlights.best.value} average score
                      </p>
                    )}
                  </div>
                  <div className="rounded-[1.05rem] border border-border/60 bg-surface px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                      Needs attention
                    </p>
                    <p className="mt-2 text-sm font-semibold text-text">
                      {dashboardData.subjectHighlights.weakest?.label || "No weak spot yet"}
                    </p>
                    {dashboardData.subjectHighlights.weakest && (
                      <p className="mt-1 text-xs text-text-muted">
                        {dashboardData.subjectHighlights.weakest.value} average score
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </Card>
          </section>
        </>
      )}
    </DashboardLayout>
  );
}

export default StudentDashboardPage;
