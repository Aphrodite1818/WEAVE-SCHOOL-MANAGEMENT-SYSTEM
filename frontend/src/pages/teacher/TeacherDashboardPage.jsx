import {
  BarChart3,
  BookOpen,
  CheckSquare,
  ClipboardList,
  GraduationCap,
  Megaphone,
  Send,
  Users,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import AnalyticsBarChart from "../../components/charts/AnalyticsBarChart";
import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import {
  DashboardFocusCard,
  DashboardListCard,
  DashboardMetricCard,
  DashboardQuickActions,
  DashboardSectionHeader,
  DashboardWelcomePanel,
} from "../../components/dashboard/DashboardPrimitives";
import { academicService } from "../../services/academicService";
import { classService } from "../../services/academicsService";
import { authSession, getErrorMessage, isAbortError } from "../../services/api";
import { dashboardService } from "../../services/dashboard.service";
import { getCachedDashboardBundle, getDashboardSessionCacheKey } from "../../services/dashboardSessionCache";
import { teacherService } from "../../services/teacherService";
import { cleanText } from "../../utils/academicDashboard";

const assignmentClassLabel = (item) =>
  cleanText([item.class_name, item.class_arm].filter(Boolean).join(" "), "");
const classLabel = (item) => cleanText([item.name, item.arm].filter(Boolean).join(" "), "");

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
          const [teacherProfile, subjectResponse, assignmentResponse, classResponse, metricsResponse] = await Promise.all([
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
          setLoadError(getErrorMessage(error, "Failed to load teacher dashboard."));
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
    () => [
      ...new Set(assignments.map((item) => cleanText(item.subject_name || item.subject_code, ""))),
    ].filter(Boolean),
    [assignments],
  );
  const hasClassTeacherDuties = classTeacherClasses.length > 0;
  const hasSubjectTeacherDuties = assignments.length > 0;
  const activeSubjects = subjects.filter((subject) => subject?.is_active !== false).length;
  const pendingSubmissions = Number(stats.pending_score_rows ?? 0);
  const draftResults = Number(stats.result_rows_draft ?? 0);
  const submittedResults = Number(stats.result_rows_submitted ?? stats.results_submitted ?? 0);
  const resultCompletion = Number(stats.result_completion_percent ?? 0);
  const classSizes = charts.class_sizes || [];

  if (isLoading) {
    return (
      <DashboardLayout role="teacher" title={`${firstName}'s Workspace`}>
        <LoadingState label="Loading teacher dashboard..." />
      </DashboardLayout>
    );
  }

  const attentionItems = [
    pendingSubmissions > 0
      ? {
          key: "pending-scores",
          title: "Pending score entries",
          description: `${pendingSubmissions} score row${pendingSubmissions === 1 ? "" : "s"} still need attention.`,
          icon: BarChart3,
          tone: "warning",
          to: "/teacher/score-entry",
          value: pendingSubmissions,
        }
      : null,
    draftResults > 0
      ? {
          key: "draft-scores",
          title: "Draft scores still editable",
          description: `${draftResults} draft row${draftResults === 1 ? "" : "s"} not submitted yet.`,
          icon: ClipboardList,
          tone: "primary",
          to: "/teacher/score-entry",
          value: draftResults,
        }
      : null,
    !teacher?.profile_completed
      ? {
          key: "profile",
          title: "Teacher profile needs attention",
          description: "Complete your profile so school records stay accurate.",
          icon: GraduationCap,
          tone: "warning",
          to: "/profile",
        }
      : null,
    !hasSubjectTeacherDuties && !hasClassTeacherDuties
      ? {
          key: "no-duties",
          title: "No teaching duties assigned yet",
          description: "Your school admin has not attached classes or subjects to this account.",
          icon: Users,
          tone: "neutral",
        }
      : null,
  ].filter(Boolean);

  return (
    <DashboardLayout role="teacher" title={`${firstName}'s Workspace`}>
      {loadError ? (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {loadError}
        </div>
      ) : null}

      {!loadError ? (
        <>
          <DashboardWelcomePanel
            eyebrow="Teacher dashboard"
            title={`Good day, ${teacher?.first_name || firstName}`}
            description="Your workspace now starts with teaching actions first, then deeper analytics only when needed."
            chips={[
              { label: teacher?.profile_completed ? "Profile complete" : "Profile needs attention", tone: teacher?.profile_completed ? "success" : "warning" },
              { label: teacher?.is_verified ? "Verified" : "Pending verification", tone: teacher?.is_verified ? "success" : "warning" },
              { label: cleanText(teacher?.specialization, "Specialization not provided"), tone: "primary" },
            ]}
          />

          <section className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
            <DashboardMetricCard
              label="Subject classes"
              value={subjectTeacherClassLabels.length}
              description="Classes where you teach subjects"
              icon={Users}
              tone={hasSubjectTeacherDuties ? "primary" : "warning"}
              to="/teacher/students"
            />
            <DashboardMetricCard
              label="Class teacher classes"
              value={classTeacherClasses.length}
              description="Classes under your care"
              icon={CheckSquare}
              tone={hasClassTeacherDuties ? "success" : "warning"}
              to="/teacher/classes"
            />
            <DashboardMetricCard
              label="Pending scores"
              value={pendingSubmissions}
              description={`${resultCompletion}% submitted`}
              icon={BarChart3}
              tone={pendingSubmissions > 0 ? "warning" : "success"}
              to="/teacher/score-entry"
            />
            <DashboardMetricCard
              label="Submitted scores"
              value={submittedResults}
              description={`${draftResults} drafts still editable`}
              icon={Send}
              tone="success"
              to="/teacher/analytics"
            />
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)]">
            <DashboardFocusCard
              title="Today’s teaching focus"
              description="Fast paths for the work teachers usually need to do first."
              icon={BookOpen}
              tone="primary"
              primaryAction={{ to: "/teacher/score-entry", label: "Enter scores", icon: Send, disabled: !hasSubjectTeacherDuties }}
              secondaryAction={{ to: "/teacher/attendance", label: "Attendance", icon: CheckSquare, disabled: !hasClassTeacherDuties }}
            >
              <div className="grid grid-cols-2 gap-3">
                <InfoTile label="Assigned subjects" value={assignedSubjectLabels.length || activeSubjects} />
                <InfoTile label="Subject classes" value={subjectTeacherClassLabels.length} />
                <InfoTile label="Class teacher duties" value={classTeacherLabels.length} />
                <InfoTile label="Completion" value={`${resultCompletion}%`} />
              </div>
            </DashboardFocusCard>

            <DashboardListCard
              title="Needs attention"
              description="Only urgent teaching signals stay on the dashboard."
              items={attentionItems}
              emptyTitle="No urgent teaching task"
              emptyDescription="Score entry, profile, and class assignment signals are clear right now."
            />
          </section>

          <section className="space-y-4">
            <DashboardSectionHeader
              title="Teaching snapshot"
              description="A compact preview of your class load. Full charts live on the analytics page."
              action={
                <Link to="/teacher/analytics">
                  <Button variant="outline" size="sm">Open analytics</Button>
                </Link>
              }
            />
            <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)]">
              <AnalyticsBarChart
                title="Subject class sizes"
                description="Students in classes where you teach a subject."
                data={classSizes}
                emptyMessage="No class size data available yet."
              />
              <Card className="p-4 sm:p-6">
                <h3 className="section-title">Assigned work</h3>
                <p className="mt-1 text-sm text-text-muted">Visible assignments stay short here. Open rosters for the full workflow.</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {assignedSubjectLabels.length > 0 ? (
                    assignedSubjectLabels.slice(0, 10).map((label) => (
                      <span key={label} className="rounded-full border border-border/70 bg-surface-muted/20 px-3 py-1.5 text-xs font-semibold text-text-soft">
                        {label}
                      </span>
                    ))
                  ) : (
                    <p className="text-sm text-text-muted">No subjects assigned yet.</p>
                  )}
                </div>
              </Card>
            </div>
          </section>

          <DashboardQuickActions
            title="Quick actions"
            description="Common teacher workflows without a crowded control panel."
            actions={[
              { label: "Score entry", description: "Record or submit scores", to: "/teacher/score-entry", icon: Send, tone: "primary" },
              { label: "Rosters", description: "View teaching students", to: "/teacher/students", icon: Users, tone: "success" },
              { label: "My class", description: "Class teacher area", to: "/teacher/classes", icon: CheckSquare, tone: "warning" },
              { label: "Notices", description: "School updates", to: "/teacher/notices", icon: Megaphone, tone: "accent" },
            ]}
          />
        </>
      ) : null}
    </DashboardLayout>
  );
}

function InfoTile({ label, value }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-surface-muted/20 px-3 py-3 sm:px-4">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-text-muted sm:text-[11px]">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-text">{value}</p>
    </div>
  );
}

export default TeacherDashboardPage;
