import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { BarChart3, CheckSquare, ClipboardList, Send, Users } from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import AnalyticsBarChart from "../../components/charts/AnalyticsBarChart";
import AnalyticsDonutChart from "../../components/charts/AnalyticsDonutChart";
import AnalyticsLineChart from "../../components/charts/AnalyticsLineChart";
import LoadingState from "../../components/shared/LoadingState";
import StatCard from "../../components/shared/StatCard";
import { authSession, getErrorMessage } from "../../services/api";
import { dashboardService } from "../../services/dashboard.service";
import { teacherService } from "../../services/teacherService";
import { academicService } from "../../services/academicService";
import {
  averageByAcademicPeriod,
  chartFromCounts,
  cleanText,
  completionPercent,
} from "../../utils/academicDashboard";

function TeacherDashboardPage() {
  const [teacher, setTeacher] = useState(null);
  const [subjects, setSubjects] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [results, setResults] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const user = authSession.getUser();
  const firstName = user?.first_name || user?.firstname || "Teacher";

  useEffect(() => {
    let mounted = true;

    async function loadDashboard() {
      setIsLoading(true);
      setLoadError(null);

      try {
        const [teacherProfile, subjectResponse, assignmentResponse, resultResponse, metricsResponse] = await Promise.all([
          teacherService.getMyTeacher(),
          teacherService.getMySubjects(),
          academicService.listMyTeacherAssignments(),
          academicService.listTeacherResults(),
          dashboardService.getTeacherAnalytics(),
        ]);

        if (!mounted) return;

        setTeacher(teacherProfile);
        setSubjects(subjectResponse?.items || []);
        setAssignments(assignmentResponse?.items || []);
        setResults(resultResponse?.items || []);
        setMetrics(metricsResponse);
      } catch (error) {
        if (mounted) {
          setLoadError(getErrorMessage(error, "Failed to load teacher dashboard."));
        }
      } finally {
        if (mounted) setIsLoading(false);
      }
    }

    loadDashboard();

    return () => {
      mounted = false;
    };
  }, []);

  const charts = metrics?.charts || {};
  const classSizeByLabel = useMemo(
    () =>
      Object.fromEntries(
        (charts.class_sizes || []).map((item) => [cleanText(item.label), Number(item.value || 0)])
      ),
    [charts.class_sizes]
  );
  const assignedClassLabels = useMemo(
    () =>
      [...new Set(assignments.map((item) => cleanText([item.class_name, item.class_arm].filter(Boolean).join(" "), "")))].filter(Boolean),
    [assignments]
  );
  const assignedSubjectLabels = useMemo(
    () =>
      [...new Set(assignments.map((item) => cleanText(item.subject_name || item.subject_code, "")))].filter(Boolean),
    [assignments]
  );

  if (isLoading) {
    return (
      <DashboardLayout role="teacher" title={`${firstName}'s Workspace`}>
        <LoadingState label="Loading teacher dashboard..." />
      </DashboardLayout>
    );
  }

  const activeSubjects = subjects.filter((subject) => subject?.is_active !== false).length;
  const expectedSubmissions = assignments.reduce((sum, item) => {
    const label = cleanText([item.class_name, item.class_arm].filter(Boolean).join(" "), "");
    return sum + Number(classSizeByLabel[label] || 0);
  }, 0);
  const submittedResults = results.filter((item) =>
    ["submitted", "published", "locked"].includes(item.status)
  ).length;
  const pendingSubmissions = Math.max(expectedSubmissions - submittedResults, 0);
  const resultCompletion = completionPercent(submittedResults, expectedSubmissions);
  const pendingByClass = assignedClassLabels.map((label) => {
    const expected = assignments
      .filter((item) => cleanText([item.class_name, item.class_arm].filter(Boolean).join(" "), "") === label)
      .reduce((sum) => sum + Number(classSizeByLabel[label] || 0), 0);
    const submitted = results.filter(
      (item) =>
        cleanText([item.class_name, item.class_arm].filter(Boolean).join(" "), "") === label &&
        ["submitted", "published", "locked"].includes(item.status)
    ).length;
    return { label, value: Math.max(expected - submitted, 0) };
  });
  const priorityClasses = pendingByClass
    .filter((item) => item.value > 0)
    .sort((left, right) => right.value - left.value)
    .slice(0, 4);
  const performanceTrend = charts.performance_trend || averageByAcademicPeriod(results);

  return (
    <DashboardLayout
      role="teacher"
      title={`${firstName}'s Workspace`}
      description="A cleaner teaching overview with trend data, class pressure points, and only the actions that matter now."
    >
      {loadError && (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {loadError}
        </div>
      )}

      {!loadError && (
        <>
          <section className="dashboard-grid xl:grid-cols-[minmax(0,1.15fr)_minmax(300px,0.85fr)]">
            <Card className="flex h-full flex-col p-5 sm:p-6">
              <h2 className="section-title">Teaching overview</h2>
              <p className="mt-1 text-sm text-text-muted">
                Profile and assignment context, kept separate from execution actions.
              </p>

              <div className="dashboard-kpi-grid mt-auto pt-4 text-sm text-text-soft">
                <div className="rounded-2xl border border-border bg-surface px-4 py-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">Profile status</p>
                  <p className="mt-1 font-semibold text-text">
                    {teacher?.profile_completed ? "Complete" : "Needs attention"}
                  </p>
                </div>
                <div className="rounded-2xl border border-border bg-surface px-4 py-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">Verification</p>
                  <p className="mt-1 font-semibold text-text">
                    {teacher?.is_verified ? "Verified" : "Pending verification"}
                  </p>
                </div>
                <div className="rounded-2xl border border-border bg-surface px-4 py-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">Specialization</p>
                  <p className="mt-1 font-semibold text-text">
                    {teacher?.specialization || "Not provided"}
                  </p>
                </div>
                <div className="rounded-2xl border border-border bg-surface px-4 py-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">Staff ID</p>
                  <p className="mt-1 font-semibold text-text">
                    {teacher?.staff_id || "Not assigned"}
                  </p>
                </div>
              </div>

              <div className="mt-5 grid gap-4 xl:grid-cols-2">
                <div className="rounded-[1.2rem] border border-border/70 bg-surface-muted/15 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-text">Assigned classes</p>
                    <BadgeCount count={assignedClassLabels.length} />
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {assignedClassLabels.length > 0 ? (
                      assignedClassLabels.map((label) => (
                        <span
                          key={label}
                          className="rounded-full border border-border/70 bg-surface px-3 py-1.5 text-xs font-medium text-text-soft"
                        >
                          {label}
                        </span>
                      ))
                    ) : (
                      <p className="text-sm text-text-muted">No classes assigned yet.</p>
                    )}
                  </div>
                </div>

                <div className="rounded-[1.2rem] border border-border/70 bg-surface-muted/15 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-text">Subject mix</p>
                    <BadgeCount count={assignedSubjectLabels.length} />
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {assignedSubjectLabels.length > 0 ? (
                      assignedSubjectLabels.slice(0, 8).map((label) => (
                        <span
                          key={label}
                          className="rounded-full border border-border/70 bg-surface px-3 py-1.5 text-xs font-medium text-text-soft"
                        >
                          {label}
                        </span>
                      ))
                    ) : (
                      <p className="text-sm text-text-muted">No subjects assigned yet.</p>
                    )}
                  </div>
                </div>
              </div>
            </Card>

            <Card className="flex h-full flex-col p-5 sm:p-6">
              <h2 className="section-title">Action centre</h2>
              <p className="mt-1 text-sm text-text-muted">
                Only the next teaching actions stay here. The broader module navigation already lives in the sidebar.
              </p>

              <div className="mt-auto rounded-[1.2rem] border border-border/70 bg-surface-muted/15 p-4 pt-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-text">Priority classes</p>
                  <BadgeCount count={priorityClasses.length} />
                </div>

                <div className="mt-3 space-y-3">
                  {priorityClasses.length > 0 ? (
                    priorityClasses.map((item) => (
                      <div
                        key={item.label}
                        className="flex items-center justify-between gap-3 rounded-[1rem] border border-border/70 bg-surface px-4 py-3"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-text">{item.label}</p>
                          <p className="mt-1 text-xs text-text-muted">Pending result rows</p>
                        </div>
                        <span className="rounded-full bg-warning-soft px-3 py-1 text-xs font-semibold text-amber-700">
                          {item.value}
                        </span>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-text-muted">
                      No classes are currently behind on result submissions.
                    </p>
                  )}
                </div>
              </div>

              <div className="mt-4 space-y-3">
                <Link to="/teacher/attendance" className="block">
                  <Button className="w-full">
                    <CheckSquare className="h-4 w-4" />
                    Open attendance
                  </Button>
                </Link>
                <Link to="/teacher/results" className="block">
                  <Button variant="success" className="w-full">
                    <Send className="h-4 w-4" />
                    Enter scores
                  </Button>
                </Link>
              </div>
            </Card>
          </section>

          <section className="stat-grid stat-grid-six">
            <StatCard
              label="Assigned Classes"
              value={assignedClassLabels.length || metrics?.stats?.total_classes || 0}
              description="classes you teach"
              icon={Users}
              tone={(metrics?.stats?.total_classes ?? 0) > 0 ? "primary" : "warning"}
              compact
            />
            <StatCard
              label="Active Subjects"
              value={assignments.length || activeSubjects}
              description="assigned class-subjects"
              icon={ClipboardList}
              tone="success"
              compact
            />
            <StatCard
              label="Students Taught"
              value={(charts.class_sizes || []).reduce((sum, item) => sum + Number(item.value || 0), 0)}
              description="across assigned classes"
              icon={Users}
              tone="primary"
              compact
            />
            <StatCard
              label="Pending Submissions"
              value={pendingSubmissions}
              description={`${resultCompletion}% complete`}
              icon={BarChart3}
              tone={pendingSubmissions > 0 ? "warning" : "success"}
              compact
            />
            <StatCard
              label="Submitted Results"
              value={submittedResults}
              description="sent for review or publishing"
              icon={Send}
              tone="success"
              compact
            />
            <StatCard
              label="Published Results"
              value={
                metrics?.stats?.results_published ??
                results.filter((item) => ["published", "locked"].includes(item.status)).length
              }
              description="visible to students"
              icon={ClipboardList}
              tone="primary"
              compact
            />
          </section>

          <section className="dashboard-grid xl:grid-cols-2">
            <AnalyticsLineChart
              title="Performance Trend"
              description="Average recorded score by academic term."
              data={performanceTrend}
              emptyMessage="No term performance trend is available yet."
            />
            <AnalyticsBarChart
              title="Class Sizes"
              description="Number of students in each class assigned to you."
              data={charts.class_sizes || []}
              emptyMessage="No class size data available yet."
            />
            <AnalyticsDonutChart
              title="Result Status Breakdown"
              description="Draft, submitted, published, and locked scores you have entered."
              data={chartFromCounts(results, "status", "draft")}
              emptyMessage="No result status data available yet."
            />
            <AnalyticsBarChart
              title="Pending Submissions By Class"
              description="Estimated pending rows from assigned classes and submitted results."
              data={pendingByClass}
              emptyMessage="No pending submission data available yet."
            />
          </section>
        </>
      )}
    </DashboardLayout>
  );
}

function BadgeCount({ count }) {
  return (
    <span className="rounded-full border border-border/70 bg-surface px-2.5 py-1 text-xs font-semibold text-text-soft">
      {count}
    </span>
  );
}

export default TeacherDashboardPage;
