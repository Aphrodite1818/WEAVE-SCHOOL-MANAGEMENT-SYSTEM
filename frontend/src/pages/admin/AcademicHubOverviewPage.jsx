import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BarChart3,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  FileText,
  GitBranch,
  GraduationCap,
  Ruler,
  School,
  Users,
} from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import {
  AcademicBlockerList,
  AcademicNextActionCard,
  AcademicOverviewCard,
} from "../../features/academic-admin/AcademicWorkspacePrimitives";
import { chooseAcademicHubNextAction } from "../../features/academic-admin/academicHubGuidance";
import { academicWorkflowConfig, academicWorkflowOrder } from "../../features/academic-admin/academicWorkflowConfig";
import { getErrorMessage, isAbortError } from "../../services/api";
import { dashboardService } from "../../services/dashboard.service";
import {
  getCachedDashboardBundle,
  getDashboardSessionCacheKey,
} from "../../services/dashboardSessionCache";
import { cleanText } from "../../utils/academicDashboard";

const ACADEMIC_HUB_CACHE_KEY = getDashboardSessionCacheKey(
  "admin:academic-hub-overview",
);

const metricNumber = (value, fallback = "-") => {
  const nextValue = Number(value);
  return Number.isFinite(nextValue) ? nextValue : fallback;
};

const percentLabel = (value) =>
  Number.isFinite(Number(value)) ? `${Number(value)}%` : "-";

function scheduleBackgroundTask(callback) {
  if (typeof window === "undefined") return undefined;
  if (typeof window.requestIdleCallback === "function") {
    const id = window.requestIdleCallback(callback, { timeout: 1200 });
    return () => window.cancelIdleCallback(id);
  }
  const id = window.setTimeout(callback, 250);
  return () => window.clearTimeout(id);
}

function AcademicHubOverviewPage() {
  const navigate = useNavigate();
  const [analytics, setAnalytics] = useState(null);
  const [metricsError, setMetricsError] = useState(null);
  const [isMetricsRefreshing, setIsMetricsRefreshing] = useState(false);

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();

    const cancelIdleTask = scheduleBackgroundTask(async () => {
      if (!mounted) return;
      setIsMetricsRefreshing(true);
      setMetricsError(null);
      try {
        const data = await getCachedDashboardBundle(ACADEMIC_HUB_CACHE_KEY, () =>
          dashboardService.getTenantAdminAnalytics({ signal: controller.signal }),
        );
        if (!mounted || controller.signal.aborted) return;
        setAnalytics(data);
      } catch (err) {
        if (!mounted || isAbortError(err)) return;
        setMetricsError(getErrorMessage(err, "Academic metrics could not be loaded."));
      } finally {
        if (mounted) setIsMetricsRefreshing(false);
      }
    });

    return () => {
      mounted = false;
      controller.abort();
      if (typeof cancelIdleTask === "function") cancelIdleTask();
    };
  }, []);

  const stats = analytics?.stats || {};
  const hasMetrics = Boolean(analytics?.stats);
  const nextAction = useMemo(() => chooseAcademicHubNextAction(stats, hasMetrics), [hasMetrics, stats]);
  const currentSession = cleanText(stats.active_academic_session, hasMetrics ? "Not set" : "Loading");
  const currentTerm = cleanText(stats.active_academic_term, hasMetrics ? "Not set" : "Loading");
  const submittedResults = metricNumber(stats.result_rows_submitted, 0);
  const totalResults = metricNumber(stats.result_rows_total, 0);
  const reportCardsGenerated = metricNumber(stats.report_cards_generated, 0);
  const reportCardsPublished = metricNumber(stats.report_cards_published, 0);
  const blockers = [
    !stats.active_academic_session
      ? {
          key: "session",
          label: "No current academic session",
          description: "Open a session before managing terms, calendars, results, and report cards.",
        }
      : null,
    !stats.active_academic_term
      ? {
          key: "term",
          label: "No current academic term",
          description: "Open a term so academic work is attached to the correct period.",
        }
      : null,
    metricNumber(stats.total_classes, 0) === 0
      ? {
          key: "classes",
          label: "No classes have been created",
          description: "Create level + arm class groups for student and teacher placement. Curriculum subjects attach to levels separately.",
        }
      : null,
    metricNumber(stats.total_subjects, 0) === 0
      ? {
          key: "subjects",
          label: "No subjects have been created",
          description: "Create the school-wide subject pool before attaching subjects to level curricula.",
        }
      : null,
    submittedResults > 0
      ? {
          key: "results",
          label: `${submittedResults} submitted result${submittedResults === 1 ? "" : "s"} need review`,
          description: "Approve or return submitted results before locking report cards.",
        }
      : null,
  ];

  const sections = academicWorkflowOrder.map((key) => ({
    key,
    ...academicWorkflowConfig[key],
    to: `/admin/academic/${key}`,
  }));

  return (
    <DashboardLayout role="admin" title="Academic Hub">
      <section className="space-y-4 sm:space-y-5">
        <Card className="p-3 sm:p-6">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-3">
                <div className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-primary-soft text-primary sm:h-12 sm:w-12">
                  <GraduationCap className="h-5 w-5 sm:h-6 sm:w-6" />
                </div>
                <div className="min-w-0">
                  <h2 className="text-xl font-semibold leading-tight text-text sm:text-3xl">
                    Academic Hub
                  </h2>
                  <p className="mt-1 max-w-3xl text-xs leading-5 text-text-muted sm:text-sm sm:leading-6">
                    A guided workspace for sessions, terms, levels, classes, curricula, teachers, results, calendars, and report cards.
                  </p>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2 sm:mt-4">
                <Badge variant={stats.active_academic_session ? "success" : "warning"}>
                  Session: {currentSession}
                </Badge>
                <Badge variant={stats.active_academic_term ? "primary" : "warning"}>
                  Term: {currentTerm}
                </Badge>
                {isMetricsRefreshing ? <Badge variant="default">Refreshing</Badge> : null}
                {metricsError ? <Badge variant="error">Metrics unavailable</Badge> : null}
              </div>
              {metricsError ? (
                <p className="mt-3 max-w-2xl text-sm font-medium text-error">
                  {metricsError}
                </p>
              ) : null}
            </div>
            <Button
              type="button"
              size="small"
              variant="outline"
              className="w-full justify-center sm:w-auto"
              onClick={() => navigate("/admin/academic/sessions")}
            >
              Manage academic year
            </Button>
          </div>
        </Card>

        <AcademicNextActionCard
          action={nextAction.action}
          description={nextAction.description}
          buttonLabel={nextAction.buttonLabel}
          onAction={() => navigate(nextAction.to)}
        />

        <div className="grid grid-cols-2 gap-2 sm:gap-3 xl:grid-cols-4">
          <AcademicOverviewCard
            icon={CalendarDays}
            label="Current Session"
            value={currentSession}
            status={stats.active_academic_session ? "open" : "needs attention"}
            description="The school year currently receiving academic work."
          />
          <AcademicOverviewCard
            icon={CalendarDays}
            label="Current Term"
            value={currentTerm}
            status={stats.active_academic_term ? "open" : "needs attention"}
            description="The term used for calendars, results, and report cards."
          />
          <AcademicOverviewCard
            icon={School}
            label="Active Classes"
            value={metricNumber(stats.total_classes)}
            status={metricNumber(stats.total_classes, 0) > 0 ? "ready" : "needs attention"}
            description="Concrete level + arm groups used for student and teacher placement."
          />
          <AcademicOverviewCard
            icon={BookOpen}
            label="Active Subjects"
            value={metricNumber(stats.total_subjects)}
            status={metricNumber(stats.total_subjects, 0) > 0 ? "ready" : "needs attention"}
            description="The school-wide subject pool used by level curricula."
          />
          <AcademicOverviewCard
            icon={Users}
            label="Teacher Assignments"
            value={metricNumber(stats.total_teachers)}
            status={metricNumber(stats.total_teachers, 0) > 0 ? "ready" : "needs attention"}
            description="Active teachers available for class and subject responsibilities."
          />
          <AcademicOverviewCard
            icon={Ruler}
            label="Grading"
            value={percentLabel(stats.result_completion_percent)}
            status={totalResults > 0 ? "active" : "not started"}
            description="Result completion based on submitted rows."
          />
          <AcademicOverviewCard
            icon={BarChart3}
            label="Results"
            value={`${submittedResults}/${totalResults}`}
            status={submittedResults > 0 ? "submitted" : "draft"}
            description="Submitted results waiting in the academic workflow."
          />
          <AcademicOverviewCard
            icon={FileText}
            label="Report Cards"
            value={`${reportCardsPublished}/${reportCardsGenerated}`}
            status={reportCardsGenerated > reportCardsPublished ? "needs attention" : "ready"}
            description="Published report cards out of generated cards."
          />
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(20rem,0.8fr)]">
          <Card className="p-3 sm:p-5">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-success" />
              <h3 className="section-title">Academic Workspaces</h3>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 sm:mt-4 sm:gap-3 xl:grid-cols-3">
              {sections.map((section) => {
                const Icon = section.icon || GitBranch;
                return (
                  <button
                    key={section.key}
                    type="button"
                    onClick={() => navigate(section.to)}
                    className="min-h-[6.75rem] rounded-2xl border border-border/70 bg-surface px-3 py-3 text-left transition hover:border-primary/40 hover:bg-primary-soft/20 sm:min-h-[8.75rem] sm:px-4 sm:py-4"
                  >
                    <div className="flex h-full flex-col gap-2 sm:flex-row sm:items-start sm:gap-3">
                      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-surface-muted text-text-soft sm:h-9 sm:w-9">
                        <Icon className="h-4 w-4" />
                      </span>
                      <span className="min-w-0">
                        <span className="block text-sm font-semibold leading-tight text-text sm:text-base">
                          {section.title}
                        </span>
                        <span className="mt-1 hidden text-sm leading-5 text-text-muted sm:line-clamp-3 sm:block">
                          {section.description}
                        </span>
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </Card>

          <AcademicBlockerList blockers={blockers} />
        </div>
      </section>
    </DashboardLayout>
  );
}

export default AcademicHubOverviewPage;
