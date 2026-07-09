import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  BarChart3,
  BookOpen,
  ClipboardList,
  FileSearch,
  FileText,
  GraduationCap,
  Library,
  Pencil,
  Users,
} from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
import Button from "../../components/ui/Button";
import {
  DashboardFocusCard,
  DashboardListCard,
  DashboardMetricCard,
  DashboardQuickActions,
  DashboardWelcomePanel,
} from "../../components/dashboard/DashboardPrimitives";
import { getErrorMessage, isAbortError } from "../../services/api";
import { dashboardService } from "../../services/dashboard.service";
import { getCachedDashboardBundle, getDashboardSessionCacheKey } from "../../services/dashboardSessionCache";
import { cleanText } from "../../utils/academicDashboard";

const ACADEMIC_HUB_CACHE_KEY = getDashboardSessionCacheKey("admin:academic-hub-overview");

const metricNumber = (value, fallback = 0) => {
  const nextValue = Number(value);
  return Number.isFinite(nextValue) ? nextValue : fallback;
};

function AcademicHubOverviewPage() {
  const [analytics, setAnalytics] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();

    async function loadOverview() {
      try {
        const data = await getCachedDashboardBundle(ACADEMIC_HUB_CACHE_KEY, () =>
          dashboardService.getTenantAdminAnalytics({ signal: controller.signal }),
        );
        if (!mounted || controller.signal.aborted) return;
        setAnalytics(data);
      } catch (err) {
        if (!mounted || isAbortError(err)) return;
        setError(getErrorMessage(err, "Failed to load academic hub overview."));
      }
    }

    loadOverview();

    return () => {
      mounted = false;
      controller.abort();
    };
  }, []);

  if (!analytics && !error) {
    return (
      <DashboardLayout role="admin" title="Academic Hub">
        <LoadingState label="Loading academic hub..." />
      </DashboardLayout>
    );
  }

  const stats = analytics?.stats || {};
  const resultCompletion = metricNumber(stats.result_completion_percent);
  const reportCardsPublished = metricNumber(stats.report_cards_published);
  const reportCardsGenerated = metricNumber(stats.report_cards_generated);
  const incompleteProfiles = metricNumber(stats.student_profiles_incomplete);
  const needsSetup = !stats.active_academic_session || !stats.active_academic_term;

  const attentionItems = [
    needsSetup
      ? {
          key: "setup",
          title: "Academic period needs setup",
          description: "Set the active session and term before recording results.",
          icon: BookOpen,
          tone: "warning",
          to: "/admin/academic/manage",
        }
      : null,
    incompleteProfiles > 0
      ? {
          key: "profiles",
          title: "Incomplete student profiles",
          description: `${incompleteProfiles} student profile${incompleteProfiles === 1 ? "" : "s"} need updates.`,
          icon: GraduationCap,
          tone: "warning",
          to: "/admin/students",
          value: incompleteProfiles,
        }
      : null,
    reportCardsGenerated > reportCardsPublished
      ? {
          key: "reports",
          title: "Report cards pending publication",
          description: `${reportCardsPublished} published from ${reportCardsGenerated} generated.`,
          icon: FileText,
          tone: "warning",
          to: "/admin/academic/manage",
        }
      : null,
  ].filter(Boolean);

  return (
    <DashboardLayout
      role="admin"
      title="Academic Hub"
      description="A simpler academic command centre for setup, assignments, results, and report cards."
    >
      {error ? (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {error}
        </div>
      ) : null}

      {!error ? (
        <>
          <DashboardWelcomePanel
            eyebrow="Academic workflow"
            title="Manage academics without the control-panel overload"
            description="Start with what you need to do, then open the full workbench only when you are ready to edit records."
            chips={[
              { label: "Session", value: cleanText(stats.active_academic_session, "Not set"), tone: stats.active_academic_session ? "success" : "warning" },
              { label: "Term", value: cleanText(stats.active_academic_term, "Not set"), tone: stats.active_academic_term ? "primary" : "warning" },
            ]}
          />

          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <DashboardMetricCard
              label="Students"
              value={metricNumber(stats.total_students)}
              description="Learners attached to this school"
              icon={GraduationCap}
              tone="primary"
              to="/admin/students"
            />
            <DashboardMetricCard
              label="Subjects"
              value={metricNumber(stats.total_subjects)}
              description="Catalog items available"
              icon={BookOpen}
              tone="success"
              to="/admin/subjects"
            />
            <DashboardMetricCard
              label="Result completion"
              value={`${resultCompletion}%`}
              description="Submitted result rows"
              icon={BarChart3}
              tone={resultCompletion >= 80 ? "success" : resultCompletion > 0 ? "warning" : "neutral"}
              to="/admin/academic/manage"
            />
            <DashboardMetricCard
              label="Report cards"
              value={reportCardsPublished}
              description={`${reportCardsGenerated} generated`}
              icon={FileText}
              tone={reportCardsGenerated > reportCardsPublished ? "warning" : "success"}
              to="/admin/academic/manage"
            />
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)]">
            <DashboardFocusCard
              title="Academic workbench"
              description="Use the full workbench for session setup, teacher assignments, result corrections, report-card generation, and search."
              icon={ClipboardList}
              tone="primary"
              primaryAction={{ to: "/admin/academic/manage", label: "Open workbench", icon: Pencil }}
              secondaryAction={{ to: "/admin/analytics", label: "View analytics", icon: BarChart3 }}
            >
              <div className="grid gap-3 sm:grid-cols-2">
                <WorkflowTile icon={BookOpen} title="Setup" description="Sessions, terms, grading scales, and subjects" />
                <WorkflowTile icon={Users} title="Assignments" description="Attach teachers to class subjects" />
                <WorkflowTile icon={Pencil} title="Results" description="Record, correct, submit, and reopen scores" />
                <WorkflowTile icon={FileText} title="Report cards" description="Generate, publish, and review report cards" />
              </div>
            </DashboardFocusCard>

            <DashboardListCard
              title="Needs attention"
              description="Academic blockers and follow-ups stay visible here."
              items={attentionItems}
              emptyTitle="Academic setup looks calm"
              emptyDescription="No active setup, profile, or report-card issue is showing right now."
            />
          </section>

          <DashboardQuickActions
            title="Academic shortcuts"
            description="Direct access to the workflows admins use most often."
            actions={[
              { label: "Full workbench", description: "Setup, results, reports, search", to: "/admin/academic/manage", icon: ClipboardList, tone: "primary" },
              { label: "Classes", description: "Manage class structure", to: "/admin/classes", icon: Library, tone: "success" },
              { label: "Subjects", description: "Manage subject catalog", to: "/admin/subjects", icon: BookOpen, tone: "warning" },
              { label: "Students", description: "Review academic profiles", to: "/admin/students", icon: GraduationCap, tone: "accent" },
              { label: "Teachers", description: "Teacher account records", to: "/admin/teachers", icon: Users, tone: "primary" },
              { label: "Search records", description: "Use workbench search", to: "/admin/academic/manage", icon: FileSearch, tone: "success" },
            ]}
          />
        </>
      ) : null}
    </DashboardLayout>
  );
}

function WorkflowTile({ icon: Icon, title, description }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-surface-muted/20 px-4 py-3">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary">
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-text">{title}</p>
          <p className="mt-1 text-xs leading-5 text-text-muted">{description}</p>
        </div>
      </div>
    </div>
  );
}

export default AcademicHubOverviewPage;
