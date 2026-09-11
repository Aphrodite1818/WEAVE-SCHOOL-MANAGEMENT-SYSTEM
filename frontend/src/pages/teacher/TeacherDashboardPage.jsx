import {
  AlertTriangle,
  BarChart3,
  BookOpen,
  CheckCircle2,
  CheckSquare,
  FilePenLine,
  MessageSquareText,
  Users,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import AnalyticsBarChart from "../../components/charts/AnalyticsBarChart";
import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
import Card from "../../components/ui/Card";
import {
  DashboardFocusCard,
  DashboardListCard,
  DashboardMetricCard,
  DashboardQuickActions,
  DashboardSectionHeader,
  DashboardWelcomePanel,
} from "../../components/dashboard/DashboardPrimitives";
import DashboardCalendarPanel from "../../features/schoolCalendar/components/DashboardCalendarPanel";
import { useRuntimeConfig } from "../../hooks/useRuntimeConfig";
import { academicService } from "../../services/academicService";
import { authSession, getErrorMessage, isAbortError } from "../../services/api";
import { dashboardService } from "../../services/dashboard.service";
import { reportCommentService } from "../../services/reportCommentService";
import { teacherService } from "../../services/teacherService";
import { cleanText } from "../../utils/academicDashboard";

const assignmentClassLabel = (item) =>
  cleanText([item.class_name, item.class_arm].filter(Boolean).join(" "), "");

function TeacherDashboardPage() {
  const [teacher, setTeacher] = useState(null);
  const [assignments, setAssignments] = useState([]);
  const [commentSummary, setCommentSummary] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const user = authSession.getUser();
  const runtimeConfig = useRuntimeConfig();
  const attendanceEnabled = runtimeConfig?.features?.attendance !== false;
  const firstName = user?.first_name || user?.firstname || "Teacher";
  const calendarScope = `${user?.tenant_id || "global"}:${user?.membership_id || ""}:${user?.id || user?.email || ""}`;

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();

    async function loadDashboard() {
      setIsLoading(true);
      setLoadError(null);
      try {
        const [profile, assignmentResponse, summaryResponse, metricsResponse] =
          await Promise.all([
            teacherService.getMyTeacher({ signal: controller.signal }),
            academicService.listMyTeacherAssignments({
              signal: controller.signal,
            }),
            reportCommentService.getTeacherCommentSummary(),
            dashboardService.getTeacherAnalytics({ signal: controller.signal }),
          ]);
        if (!mounted || controller.signal.aborted) return;
        setTeacher(profile);
        setAssignments(assignmentResponse?.items || []);
        setCommentSummary(summaryResponse);
        setMetrics(metricsResponse);
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
    const handlePullRefresh = () => loadDashboard();
    window.addEventListener("weave:pull-refresh", handlePullRefresh);

    return () => {
      window.removeEventListener("weave:pull-refresh", handlePullRefresh);
      mounted = false;
      controller.abort();
    };
  }, []);

  const charts = metrics?.charts || {};
  const subjectClasses = useMemo(
    () => [...new Set(assignments.map(assignmentClassLabel))].filter(Boolean),
    [assignments],
  );
  const subjectNames = useMemo(
    () => [
      ...new Set(
        assignments
          .map((item) => item.subject_name || item.subject_code)
          .filter(Boolean),
      ),
    ],
    [assignments],
  );
  const hasSubjectAssignments = assignments.length > 0;
  const classTeacherCount = Number(commentSummary?.class_teacher_class_count || 0);
  const hasClassTeacherClasses = classTeacherCount > 0;
  const requiringComments = Number(commentSummary?.students_requiring_comments || 0);
  const draftComments = Number(commentSummary?.draft_comments || 0);
  const submittedComments = Number(commentSummary?.submitted_comments || 0);
  const needsReview = Number(commentSummary?.needs_review_comments || 0);
  const completion = Number(commentSummary?.comment_completion_percent || 0);

  if (isLoading) {
    return (
      <DashboardLayout role="teacher" title={`${firstName}'s Workspace`}>
        <LoadingState label="Loading teacher dashboard..." />
      </DashboardLayout>
    );
  }

  const attentionItems = [
    needsReview > 0
      ? {
          key: "comment-review",
          title: "Submitted comments need review",
          description: `${needsReview} comment${needsReview === 1 ? "" : "s"} became stale after an academic or placement change.`,
          icon: AlertTriangle,
          tone: "warning",
          to: "/teacher/student-comments",
        }
      : null,
    requiringComments > 0
      ? {
          key: "comments-required",
          title: "Students ready for comments",
          description: `${requiringComments} student${requiringComments === 1 ? " is" : "s are"} academically ready and still need a submitted class-teacher comment.`,
          icon: MessageSquareText,
          tone: "primary",
          to: "/teacher/student-comments",
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
            variant="blue"
            eyebrow="Teacher dashboard"
            title={`Good day, ${teacher?.first_name || firstName}`}
            description="Review assigned subjects, teaching rosters, and class-teacher report comments. Scores are managed by school admins."
            profileCompletion={teacher?.profile_completed}
            chips={[
              {
                label: "Staff ID",
                value: cleanText(teacher?.staff_id, "Not assigned"),
                tone: "primary",
              },
              {
                label: teacher?.is_verified
                  ? "Verified"
                  : "Pending verification",
                tone: teacher?.is_verified ? "success" : "warning",
              },
              {
                label: cleanText(
                  teacher?.specialization,
                  "Specialization not provided",
                ),
                tone: "primary",
              },
            ]}
          />

          <section className="dashboard-kpi-grid dashboard-kpi-grid-four grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
            <DashboardMetricCard
              label="Class teacher classes"
              value={classTeacherCount}
              description="Classes explicitly assigned to your care"
              icon={CheckSquare}
              tone={hasClassTeacherClasses ? "success" : "warning"}
              to={hasClassTeacherClasses ? "/teacher/classes" : undefined}
            />
            <DashboardMetricCard
              label="Require comments"
              value={requiringComments}
              description="Academically ready students"
              icon={MessageSquareText}
              tone={requiringComments > 0 ? "warning" : "success"}
              to={hasClassTeacherClasses ? "/teacher/student-comments" : undefined}
            />
            <DashboardMetricCard
              label="Draft comments"
              value={draftComments}
              description="Saved but not submitted"
              icon={FilePenLine}
              tone={draftComments > 0 ? "warning" : "primary"}
              to={hasClassTeacherClasses ? "/teacher/student-comments" : undefined}
            />
            <DashboardMetricCard
              label="Submitted comments"
              value={submittedComments}
              description={`${completion.toFixed(0)}% comment completion`}
              icon={CheckCircle2}
              tone="success"
              to={hasClassTeacherClasses ? "/teacher/student-comments" : undefined}
            />
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)]">
            <DashboardFocusCard
              title="Teaching focus"
              description="Comment actions appear only for explicit class-teacher assignments. Subject results remain read-only."
              icon={BookOpen}
              tone="primary"
              primaryAction={{
                to: "/teacher/student-comments",
                label: "Student comments",
                icon: MessageSquareText,
                disabled: !hasClassTeacherClasses,
              }}
              secondaryAction={
                attendanceEnabled
                  ? {
                      to: "/teacher/attendance",
                      label: "Attendance",
                      icon: CheckSquare,
                      disabled: !hasClassTeacherClasses,
                    }
                  : null
              }
            >
              <div className="grid grid-cols-2 gap-3">
                <InfoTile label="Assigned subjects" value={subjectNames.length} />
                <InfoTile label="Subject classes" value={subjectClasses.length} />
                <InfoTile label="Needs review" value={needsReview} />
                <InfoTile label="Comment completion" value={`${completion.toFixed(0)}%`} />
              </div>
            </DashboardFocusCard>

            <DashboardListCard
              title="Needs attention"
              description="Class-teacher report-comment work that needs action."
              items={attentionItems}
              emptyTitle="No report comment needs attention"
              emptyDescription={
                hasClassTeacherClasses
                  ? "No ready student is waiting for a class-teacher comment right now."
                  : "You are not currently assigned as a class teacher. Subject teaching assignments do not grant report-comment access."
              }
            />
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <DashboardCalendarPanel
              role="teacher"
              actorId={user?.id || user?.email || ""}
              membershipId={user?.membership_id || ""}
              tenantId={user?.tenant_id || calendarScope}
            />
            <DashboardListCard
              title="Calendar notes"
              description="Read-only school schedule context for planning."
              items={[]}
              emptyTitle="No extra calendar action"
              emptyDescription="Calendar setup and lifecycle controls are managed by tenant admins."
            />
          </section>

          <section className="space-y-4">
            <DashboardSectionHeader
              title="Teaching snapshot"
              description="Current subject assignments and class sizes."
            />
            <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)]">
              <AnalyticsBarChart
                title="Subject class sizes"
                description="Students in classes where you teach a subject."
                data={charts.class_sizes || []}
                emptyMessage="No class size data available yet."
              />
              <Card className="p-4 sm:p-6">
                <h3 className="section-title">Assigned subjects</h3>
                <p className="mt-1 text-sm text-text-muted">
                  These assignments provide teaching/read access, not score-entry or class-teacher comment authority.
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {subjectNames.length ? (
                    subjectNames.map((label) => (
                      <span
                        key={label}
                        className="rounded-full border border-border/70 bg-surface-muted/20 px-3 py-1.5 text-xs font-semibold text-text-soft"
                      >
                        {label}
                      </span>
                    ))
                  ) : (
                    <p className="text-sm text-text-muted">No subject assignment is active.</p>
                  )}
                </div>
              </Card>
            </div>
          </section>

          <DashboardQuickActions
            title="Quick actions"
            description="Assignment-scoped teacher workflows."
            actions={[
              {
                label: "Student comments",
                description: "Review finalized performance and submit comments",
                to: "/teacher/student-comments",
                icon: MessageSquareText,
                tone: "success",
                disabled: !hasClassTeacherClasses,
              },
              {
                label: "My comment templates",
                description: "Manage personal class-teacher wording",
                to: "/teacher/comment-templates",
                icon: FilePenLine,
                tone: "warning",
                disabled: !hasClassTeacherClasses,
              },
              {
                label: "Teaching rosters",
                description: "Students in assigned subject classes",
                to: "/teacher/students",
                icon: Users,
                tone: "primary",
                disabled: !hasSubjectAssignments,
              },
              {
                label: "Analytics",
                description: "Read-only class and performance analytics",
                to: "/teacher/analytics",
                icon: BarChart3,
                tone: "accent",
              },
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
      <p className="text-[10px] font-semibold uppercase tracking-wide text-text-muted sm:text-[11px]">
        {label}
      </p>
      <p className="mt-1 truncate text-sm font-semibold text-text">{value}</p>
    </div>
  );
}

export default TeacherDashboardPage;
