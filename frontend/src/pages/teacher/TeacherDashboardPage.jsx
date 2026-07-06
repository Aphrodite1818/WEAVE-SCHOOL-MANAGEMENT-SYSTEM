import {
  BarChart3,
  CheckSquare,
  ClipboardList,
  Send,
  Users,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import AnalyticsBarChart from "../../components/charts/AnalyticsBarChart";
import AnalyticsDonutChart from "../../components/charts/AnalyticsDonutChart";
import AnalyticsLineChart from "../../components/charts/AnalyticsLineChart";
import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
import StatCard from "../../components/shared/StatCard";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import { academicService } from "../../services/academicService";
import { classService } from "../../services/academicsService";
import { authSession, getErrorMessage, isAbortError } from "../../services/api";
import { dashboardService } from "../../services/dashboard.service";
import { getCachedDashboardBundle, getDashboardSessionCacheKey } from "../../services/dashboardSessionCache";
import { teacherService } from "../../services/teacherService";
import { cleanText } from "../../utils/academicDashboard";

const assignmentClassLabel = (item) =>
  cleanText([item.class_name, item.class_arm].filter(Boolean).join(" "), "");
const classLabel = (item) =>
  cleanText([item.name, item.arm].filter(Boolean).join(" "), "");

function TeacherDashboardPage() {
  const [teacher, setTeacher] = useState(null);
  const [subjects, setSubjects] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [classTeacherClasses, setClassTeacherClasses] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const user = authSession.getUser();
  const firstName = user?.first_name || user?.firstname || "Teacher";

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();

    async function loadDashboard() {
      setIsLoading(true);
      setLoadError(null);

      try {
        const cacheKey = getDashboardSessionCacheKey("teacher:dashboard");
        const bundle = await getCachedDashboardBundle(cacheKey, async () => {
          const [
            teacherProfile,
            subjectResponse,
            assignmentResponse,
            classResponse,
            metricsResponse,
          ] = await Promise.all([
            teacherService.getMyTeacher({ signal: controller.signal }),
            teacherService.getMySubjects({ signal: controller.signal }),
            academicService.listMyTeacherAssignments({ signal: controller.signal }),
            classService.getClasses({ limit: 100, active_only: true, signal: controller.signal }),
            dashboardService.getTeacherAnalytics({ signal: controller.signal }),
          ]);

          return {
            teacher: teacherProfile,
            subjects: subjectResponse?.items || [],
            assignments: assignmentResponse?.items || [],
            classTeacherClasses: classResponse?.items || [],
            metrics: metricsResponse,
          };
        });

        if (!mounted || controller.signal.aborted) return;

        setTeacher(bundle.teacher);
        setSubjects(bundle.subjects);
        setAssignments(bundle.assignments);
        setClassTeacherClasses(bundle.classTeacherClasses);
        setMetrics(bundle.metrics);
      } catch (error) {
        if (mounted && !isAbortError(error)) {
          setLoadError(
            getErrorMessage(error, "Failed to load teacher dashboard."),
          );
        }
      } finally {
        if (mounted && !controller.signal.aborted) setIsLoading(false);
      }
    }

    loadDashboard();

    return () => {
      mounted = false;
      controller.abort();
    };
  }, []);

  const charts = metrics?.charts || {};
  const stats = metrics?.stats || {};
  const subjectTeacherClassLabels = useMemo(
    () => [...new Set(assignments.map(assignmentClassLabel))].filter(Boolean),
    [assignments],
  );
  const classTeacherLabels = useMemo(
    () => classTeacherClasses.map(classLabel).filter(Boolean),
    [classTeacherClasses],
  );
  const assignedSubjectLabels = useMemo(
    () =>
      [
        ...new Set(
          assignments.map((item) =>
            cleanText(item.subject_name || item.subject_code, ""),
          ),
        ),
      ].filter(Boolean),
    [assignments],
  );
  const hasClassTeacherDuties = classTeacherClasses.length > 0;
  const hasSubjectTeacherDuties = assignments.length > 0;

  if (isLoading) {
    return (
      <DashboardLayout role="teacher" title={`${firstName}'s Workspace`}>
        <LoadingState label="Loading teacher dashboard..." />
      </DashboardLayout>
    );
  }

  const activeSubjects = subjects.filter(
    (subject) => subject?.is_active !== false,
  ).length;
  const pendingSubmissions = Number(stats.pending_score_rows ?? 0);
  const draftResults = Number(stats.result_rows_draft ?? 0);
  const submittedResults = Number(stats.result_rows_submitted ?? stats.results_submitted ?? 0);
  const resultCompletion = Number(stats.result_completion_percent ?? 0);
  const priorityClasses = charts.pending_scores_by_class || [];
  const performanceTrend = charts.performance_trend || [];

  return (
    <DashboardLayout role="teacher" title={`${firstName}'s Workspace`}>
      {loadError && (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {loadError}
        </div>
      )}

      {!loadError && (
        <>
          <section className="dashboard-grid xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <DutyCard
              title="Subject teacher duties"
              enabled={hasSubjectTeacherDuties}
              enabledLabel={`${assignments.length} active class-subject${assignments.length === 1 ? "" : "s"}`}
              disabledLabel="No class-subject assigned yet"
              primaryTo="/teacher/score-entry"
              primaryLabel="Open Score Entry"
              secondaryTo="/teacher/students"
              secondaryLabel="View Teaching Rosters"
              icon={Send}
            />
            <DutyCard
              title="Class teacher duties"
              enabled={hasClassTeacherDuties}
              enabledLabel={`${classTeacherClasses.length} class${classTeacherClasses.length === 1 ? "" : "es"} under your care`}
              disabledLabel="You are not assigned as a class teacher"
              primaryTo="/teacher/classes"
              primaryLabel="View My Class"
              secondaryTo="/teacher/attendance"
              secondaryLabel="Open Attendance"
              icon={CheckSquare}
            />
          </section>

          <section className="dashboard-grid xl:grid-cols-[minmax(0,1.15fr)_minmax(300px,0.85fr)]">
            <Card className="flex h-full flex-col p-5 sm:p-6">
              <h2 className="section-title">Teaching overview</h2>

              <div className="dashboard-kpi-grid mt-auto pt-4 text-sm text-text-soft">
                <InfoTile
                  label="Profile status"
                  value={
                    teacher?.profile_completed ? "Complete" : "Needs attention"
                  }
                />
                <InfoTile
                  label="Verification"
                  value={
                    teacher?.is_verified ? "Verified" : "Pending verification"
                  }
                />
                <InfoTile
                  label="Specialization"
                  value={teacher?.specialization || "Not provided"}
                />
                <InfoTile
                  label="Staff ID"
                  value={teacher?.staff_id || "Not assigned"}
                />
              </div>

              <div className="mt-5 grid gap-4 xl:grid-cols-3">
                <PillPanel
                  title="Subject classes"
                  count={subjectTeacherClassLabels.length}
                  items={subjectTeacherClassLabels}
                  empty="No subject classes assigned yet."
                />
                <PillPanel
                  title="Assigned subjects"
                  count={assignedSubjectLabels.length}
                  items={assignedSubjectLabels.slice(0, 8)}
                  empty="No subjects assigned yet."
                />
                <PillPanel
                  title="Class teacher classes"
                  count={classTeacherLabels.length}
                  items={classTeacherLabels}
                  empty="No class teacher assignment."
                />
              </div>
            </Card>

            <Card className="flex h-full flex-col p-5 sm:p-6">
              <h2 className="section-title">Score entry centre</h2>

              <div className="mt-auto rounded-[1.2rem] border border-border/70 bg-surface-muted/15 p-4 pt-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-text">
                    Priority subject classes
                  </p>
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
                          <p className="truncate text-sm font-semibold text-text">
                            {item.label}
                          </p>
                          <p className="mt-1 text-xs text-text-muted">
                            Pending score submissions
                          </p>
                        </div>
                        <span className="rounded-full bg-warning-soft px-3 py-1 text-xs font-semibold text-amber-700">
                          {item.value}
                        </span>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-text-muted">
                      No class-subject assignment is currently behind on
                      submitted scores.
                    </p>
                  )}
                </div>
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                <Link to="/teacher/students" className="block">
                  <Button
                    className="w-full"
                    disabled={
                      !hasSubjectTeacherDuties && !hasClassTeacherDuties
                    }
                  >
                    <Users className="h-4 w-4" />
                    Open Rosters
                  </Button>
                </Link>
                <Link to="/teacher/score-entry" className="block">
                  <Button
                    variant="success"
                    className="w-full"
                    disabled={!hasSubjectTeacherDuties}
                  >
                    <Send className="h-4 w-4" />
                    Enter Scores
                  </Button>
                </Link>
              </div>
            </Card>
          </section>

          <section className="stat-grid stat-grid-six">
            <StatCard
              label="Subject Classes"
              value={subjectTeacherClassLabels.length}
              description="classes you teach subjects in"
              icon={Users}
              tone={hasSubjectTeacherDuties ? "primary" : "warning"}
              compact
            />
            <StatCard
              label="Class Teacher Classes"
              value={classTeacherClasses.length}
              description="classes you oversee"
              icon={CheckSquare}
              tone={hasClassTeacherDuties ? "success" : "warning"}
              compact
            />
            <StatCard
              label="Class-Subjects"
              value={assignments.length || activeSubjects}
              description="active subject assignments"
              icon={ClipboardList}
              tone="success"
              compact
            />
            <StatCard
              label="Pending Scores"
              value={pendingSubmissions}
              description={`${resultCompletion}% submitted`}
              icon={BarChart3}
              tone={pendingSubmissions > 0 ? "warning" : "success"}
              compact
            />
            <StatCard
              label="Draft Scores"
              value={draftResults}
              description="still editable"
              icon={ClipboardList}
              tone={draftResults > 0 ? "warning" : "primary"}
              compact
            />
            <StatCard
              label="Submitted Scores"
              value={submittedResults}
              description="locked for admin review"
              icon={Send}
              tone="success"
              compact
            />
          </section>

          <section className="dashboard-grid xl:grid-cols-2">
            <AnalyticsLineChart
              title="Submitted Score Trend"
              description="Average submitted score by academic term."
              data={performanceTrend}
              emptyMessage="No submitted performance trend is available yet."
            />
            <AnalyticsBarChart
              title="Subject Class Sizes"
              description="Number of students in classes where you teach a subject."
              data={charts.class_sizes || []}
              emptyMessage="No class size data available yet."
            />
            <AnalyticsDonutChart
              title="Score Status Breakdown"
              description="Draft vs submitted scores you have entered."
              data={charts.result_status_distribution || []}
              emptyMessage="No score status data available yet."
            />
            <AnalyticsBarChart
              title="Pending Scores By Class"
              description="Estimated pending rows from subject classes and submitted scores."
              data={priorityClasses}
              emptyMessage="No pending score data available yet."
            />
          </section>
        </>
      )}
    </DashboardLayout>
  );
}

function DutyCard({
  title,
  enabled,
  enabledLabel,
  disabledLabel,
  primaryTo,
  primaryLabel,
  secondaryTo,
  secondaryLabel,
  icon: Icon,
}) {
  return (
    <Card className="p-5 sm:p-6">
      <div className="flex items-start gap-4">
        <div
          className={`rounded-2xl p-3 ${enabled ? "bg-primary-soft text-primary" : "bg-surface-muted text-text-muted"}`}
        >
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <h2 className="section-title">{title}</h2>
            <span
              className={`rounded-full px-3 py-1 text-xs font-semibold ${enabled ? "bg-success-soft text-success" : "bg-warning-soft text-amber-700"}`}
            >
              {enabled ? enabledLabel : disabledLabel}
            </span>
          </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            <Link
              to={primaryTo}
              className={
                enabled ? "block" : "pointer-events-none block opacity-50"
              }
              aria-disabled={!enabled}
            >
              <Button className="w-full" disabled={!enabled}>
                {primaryLabel}
              </Button>
            </Link>
            <Link
              to={secondaryTo}
              className={
                enabled ? "block" : "pointer-events-none block opacity-50"
              }
              aria-disabled={!enabled}
            >
              <Button
                variant="secondary"
                className="w-full"
                disabled={!enabled}
              >
                {secondaryLabel}
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </Card>
  );
}

function BadgeCount({ count }) {
  return (
    <span className="rounded-full border border-border/70 bg-surface px-2.5 py-1 text-xs font-semibold text-text-soft">
      {count}
    </span>
  );
}

function InfoTile({ label, value }) {
  return (
    <div className="rounded-2xl border border-border bg-surface px-4 py-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
        {label}
      </p>
      <p className="mt-1 font-semibold text-text">{value}</p>
    </div>
  );
}

function PillPanel({ title, count, items, empty }) {
  return (
    <div className="rounded-[1.2rem] border border-border/70 bg-surface-muted/15 p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-text">{title}</p>
        <BadgeCount count={count} />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {items.length > 0 ? (
          items.map((label) => (
            <span
              key={label}
              className="rounded-full border border-border/70 bg-surface px-3 py-1.5 text-xs font-medium text-text-soft"
            >
              {label}
            </span>
          ))
        ) : (
          <p className="text-sm text-text-muted">{empty}</p>
        )}
      </div>
    </div>
  );
}

export default TeacherDashboardPage;
