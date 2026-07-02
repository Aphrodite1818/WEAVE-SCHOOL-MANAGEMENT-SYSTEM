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

const isSubmitted = (result) => result?.status === "submitted";
const classLabel = (item) => cleanText([item.class_name, item.class_arm].filter(Boolean).join(" "), "");

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
    () => [...new Set(assignments.map(classLabel))].filter(Boolean),
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
    const label = classLabel(item);
    return sum + Number(classSizeByLabel[label] || 0);
  }, 0);
  const draftResults = results.filter((item) => item.status === "draft").length;
  const submittedResults = results.filter(isSubmitted).length;
  const pendingSubmissions = Math.max(expectedSubmissions - submittedResults, 0);
  const resultCompletion = completionPercent(submittedResults, expectedSubmissions);
  const pendingByClass = assignedClassLabels.map((label) => {
    const expected = assignments
      .filter((item) => classLabel(item) === label)
      .reduce((sum) => sum + Number(classSizeByLabel[label] || 0), 0);
    const submitted = results.filter(
      (item) => classLabel(item) === label && isSubmitted(item)
    ).length;
    return { label, value: Math.max(expected - submitted, 0) };
  });
  const priorityClasses = pendingByClass
    .filter((item) => item.value > 0)
    .sort((left, right) => right.value - left.value)
    .slice(0, 4);
  const performanceTrend = charts.performance_trend || averageByAcademicPeriod(results.filter(isSubmitted));

  return (
    <DashboardLayout
      role="teacher"
      title={`${firstName}'s Workspace`}
      description="Manage only your assigned class-subjects. Draft scores stay editable; submitted scores are locked for admin review."
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
                Class teacher duties are separate from subject teaching assignments. This dashboard only reflects subjects assigned to you.
              </p>

              <div className="dashboard-kpi-grid mt-auto pt-4 text-sm text-text-soft">
                <InfoTile label="Profile status" value={teacher?.profile_completed ? "Complete" : "Needs attention"} />
                <InfoTile label="Verification" value={teacher?.is_verified ? "Verified" : "Pending verification"} />
                <InfoTile label="Specialization" value={teacher?.specialization || "Not provided"} />
                <InfoTile label="Staff ID" value={teacher?.staff_id || "Not assigned"} />
              </div>

              <div className="mt-5 grid gap-4 xl:grid-cols-2">
                <PillPanel title="Assigned classes" count={assignedClassLabels.length} items={assignedClassLabels} empty="No classes assigned yet." />
                <PillPanel title="Assigned subjects" count={assignedSubjectLabels.length} items={assignedSubjectLabels.slice(0, 8)} empty="No subjects assigned yet." />
              </div>
            </Card>

            <Card className="flex h-full flex-col p-5 sm:p-6">
              <h2 className="section-title">Score submission centre</h2>
              <p className="mt-1 text-sm text-text-muted">
                Submit only complete result rows. After submission, corrections must go through the admin.
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
                          <p className="mt-1 text-xs text-text-muted">Pending submissions</p>
                        </div>
                        <span className="rounded-full bg-warning-soft px-3 py-1 text-xs font-semibold text-amber-700">
                          {item.value}
                        </span>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-text-muted">
                      No class-subject assignment is currently behind on submitted scores.
                    </p>
                  )}
                </div>
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                <Link to="/teacher/attendance" className="block">
                  <Button className="w-full">
                    <CheckSquare className="h-4 w-4" />
                    Open attendance
                  </Button>
                </Link>
                <Link to="/teacher/results" className="block">
                  <Button variant="success" className="w-full">
                    <Send className="h-4 w-4" />
                    Enter / submit scores
                  </Button>
                </Link>
              </div>
            </Card>
          </section>

          <section className="stat-grid stat-grid-six">
            <StatCard label="Assigned Classes" value={assignedClassLabels.length || metrics?.stats?.total_classes || 0} description="classes you teach" icon={Users} tone={(metrics?.stats?.total_classes ?? 0) > 0 ? "primary" : "warning"} compact />
            <StatCard label="Class-Subjects" value={assignments.length || activeSubjects} description="active assignments" icon={ClipboardList} tone="success" compact />
            <StatCard label="Students Taught" value={(charts.class_sizes || []).reduce((sum, item) => sum + Number(item.value || 0), 0)} description="across assigned classes" icon={Users} tone="primary" compact />
            <StatCard label="Pending Submissions" value={pendingSubmissions} description={`${resultCompletion}% submitted`} icon={BarChart3} tone={pendingSubmissions > 0 ? "warning" : "success"} compact />
            <StatCard label="Draft Results" value={draftResults} description="still editable" icon={ClipboardList} tone={draftResults > 0 ? "warning" : "primary"} compact />
            <StatCard label="Submitted Results" value={submittedResults} description="locked for admin review" icon={Send} tone="success" compact />
          </section>

          <section className="dashboard-grid xl:grid-cols-2">
            <AnalyticsLineChart title="Submitted Performance Trend" description="Average submitted score by academic term." data={performanceTrend} emptyMessage="No submitted performance trend is available yet." />
            <AnalyticsBarChart title="Class Sizes" description="Number of students in each class assigned to you." data={charts.class_sizes || []} emptyMessage="No class size data available yet." />
            <AnalyticsDonutChart title="Result Status Breakdown" description="Draft vs submitted scores you have entered." data={chartFromCounts(results, "status", "draft")} emptyMessage="No result status data available yet." />
            <AnalyticsBarChart title="Pending Submissions By Class" description="Estimated pending rows from assigned classes and submitted results." data={pendingByClass} emptyMessage="No pending submission data available yet." />
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

function InfoTile({ label, value }) {
  return (
    <div className="rounded-2xl border border-border bg-surface px-4 py-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">{label}</p>
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
            <span key={label} className="rounded-full border border-border/70 bg-surface px-3 py-1.5 text-xs font-medium text-text-soft">
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
